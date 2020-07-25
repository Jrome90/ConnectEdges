from collections import OrderedDict

import blf
import bpy
import gpu
import bgl

from gpu_extras.batch import batch_for_shader

from . bl_ui_widgets.bl_ui_widget import BL_UI_Widget
from . bl_ui_widgets.bl_ui_textbox import BL_UI_Textbox
from . bl_ui_widgets.bl_ui_label import BL_UI_Label

class TextLabel(BL_UI_Label):
    def __init__(self, x, y, width, height, text, context):
        super().__init__(x, y, width, height)

        if text is not None:
            self.text = text

        self.init(context)
    def init(self, context):
        super().init(context)

    def handle_event(self, event):
        pass

    def update(self, x, y):
        self.x_screen = x
        self.y_screen = y

        self.draw()

class TextLabelProperty(TextLabel):
    def __init__(self, x, y, width, height, context, initial_val, set_text_func, hotkey_hint=None, show_hotkeys=False):
        super().__init__(x, y, width, height, None, context)
        super().init(context)
        self.hotkey_hint = hotkey_hint
        self.show_hotkeys = show_hotkeys
        self._set_text_func = set_text_func
        self.update_text(initial_val)

    def handle_event(self, event):
        pass

    def update(self, x, y):
        self.x_screen = x
        self.y_screen = y

        self.draw()

    def update_text(self, text):
        self.text = self._set_text_func(text)
        if self.hotkey_hint is not None and self.show_hotkeys:
            self.text += " " + self.hotkey_hint


class TextLayoutPanel(object):
    def __init__(self, height, width, position):
        x, y = position
        self.x_screen = x
        self.y_screen = y
        self.vertical_spacing = 10
        self.text_objects = OrderedDict()

    def register(self, att_name, obj):
        #assert for instance type text
        name_found, obj_found = self.check_if_registered(att_name, obj)
        assert (not name_found and not obj_found), \
            "Failed to register text object. Name Exists: {0} Object Exists: {1}".format(name_found, obj_found)

        self.text_objects[att_name] = obj

    def check_if_registered(self, att_name, obj):
        name_found = False
        obj_found = False
        for key, val in self.text_objects.items():
            if key == att_name:
                name_found =True
            if val is obj:
                obj_found = True
            if name_found or obj_found:
                break

        return name_found, obj_found

    def layout(self):
        next_y = 0
        for text_obj in self.text_objects.values():
            text_obj.update(self.x_screen, self.y_screen + next_y)
            next_y += self.vertical_spacing + text_obj.height

    def draw(self):
         for text_obj in self.text_objects.values():
             text_obj.draw()

    def update_text(self,  obj, key, new_value):
        if key in self.text_objects:
            obj = self.text_objects[key]

            if isinstance(obj, TextLabelProperty):
                obj.update_text(new_value)
            else:
                obj.text = "{0}: {1}".format(key, new_value)


class TextBox(BL_UI_Textbox):

    def __init__(self, context, x, y, width, height, label, max_input_chars=100, text_color=(0.988, 0.988, 0.988, 1),
                 caret_color=(0.384, 0.384, 0.941, 1)):
        super().__init__(x, y, width, height)
        self.init(context)
        self.label = label
        self.max_input_chars = max_input_chars
        self.text_color = text_color
        self.carret_color = caret_color

        self._has_keyboard_focus = False

    def update(self, x, y):
        BL_UI_Widget.update(self, x, y)

        if self.has_label:
            self.update_label()

        self._textpos = [x, y]

    def update_label(self):
        y_screen_flip = self.get_area_height() - self.y_screen

        size = blf.dimensions(0, self._label)

        self._label_width = size[0]*2.2 + 12

        # bottom left, top left, top right, bottom right
        vertices_outline = (
                    (self.x_screen, y_screen_flip), 
                    (self.x_screen + self.width + self._label_width, y_screen_flip), 
                    (self.x_screen + self.width + self._label_width, y_screen_flip - self.height),
                    (self.x_screen, y_screen_flip - self.height))
                    
        self.batch_outline = batch_for_shader(self.shader, 'LINE_LOOP', {"pos" : vertices_outline})

        indices = ((0, 1, 2), (2, 3, 1))

        lb_x = self.x_screen + self.width

        # bottom left, top left, top right, bottom right
        vertices_label_bg = (
                    (lb_x, y_screen_flip), 
                    (lb_x + self._label_width, y_screen_flip), 
                    (lb_x, y_screen_flip - self.height),
                    (lb_x + self._label_width, y_screen_flip - self.height))
                    
        self.batch_label_bg = batch_for_shader(self.shader, 'TRIS', {"pos" : vertices_label_bg}, indices=indices)

    def get_carret_pos_px(self):
        size_all = blf.dimensions(0, self._text)
        size_to_carret = blf.dimensions(0, self._text[:self._carret_pos])
        return self.x_screen + (self.width / 2.0) - (size_all[0] / 2.0) + size_to_carret[0] + 5

    def update_carret(self):
        y_screen_flip = self.get_area_height() - self.y_screen

        x = self.get_carret_pos_px()

        text_height = blf.dimensions(0, self._label)[0]
        # bottom left, top left, top right, bottom right
        vertices = (
            (x, y_screen_flip - 6),
            (x, (y_screen_flip - self.height) + 6)
        )

        self.batch_carret = batch_for_shader(
            self.shader, 'LINES', {"pos": vertices})

    def draw(self):
        BL_UI_Widget.draw(self)

        area_height = self.get_area_height()

        # Draw text
        self.draw_text(area_height)

        self.shader.bind()
        self.shader.uniform_float("color", self._carret_color)
        bgl.glEnable(bgl.GL_LINE_SMOOTH)
        bgl.glLineWidth(2)

        if self.batch_carret is not None:
            self.batch_carret.draw(self.shader)

        if self.has_label:
            self.shader.uniform_float("color", self._label_color)
            bgl.glLineWidth(1)
            self.batch_outline.draw(self.shader)

            self.batch_label_bg.draw(self.shader)

            size = blf.dimensions(0, self._label)

            textpos_y = area_height - self.y_screen - (self.height + size[1]) / 2.0
            blf.position(0, self.x_screen + self.width + (self._label_width / 2.0) - (size[0]  / 2.0), textpos_y + 1, 0)

            r, g, b, a = self._label_text_color
            blf.color(0, r, g, b, a)

            blf.draw(0, self._label)

    def text_input(self, event):
        if self._has_keyboard_focus:
            index = self._carret_pos

            if event.ascii != '' and len(self._text) < self.max_input_chars:
                self._text = self._text[:index] + event.ascii + self._text[index:]
                self._carret_pos += 1
            elif event.type == 'BACK_SPACE':
                if self._carret_pos > 0:
                    self._text = self._text[:index-1] + self._text[index:]
                    self._carret_pos -= 1

            elif event.type == 'DEL':
                if self._carret_pos < len(self._text):
                    self._text = self._text[:index] + self._text[index+1:]

            elif event.type == 'LEFT_ARROW':
                if self._carret_pos > 0:
                    self._carret_pos -= 1

            elif event.type == 'RIGHT_ARROW':
                if self._carret_pos < len(self._text):
                    self._carret_pos += 1

            elif event.type == 'HOME':
                self._carret_pos = 0

            elif event.type == 'END':
                self._carret_pos = len(self._text)
            self.update_carret()

            try:
                self.text_changed_func(self, self.context, event)
            except AssertionError as e:
                print("Assert: " + str(e))
            except BaseException as e:
                print(str(e))

            return True

    def set_text_changed(self, text_changed_func):
        self.text_changed_func = text_changed_func

    def mouse_down(self, x, y):
        if self.is_in_rect(x, y):
            self.update_carret()
            self._has_keyboard_focus = True
            return True
        else:
            self._has_keyboard_focus = False
            self.batch_carret = None

        return False

    def mouse_move(self, x, y):
        pass

    def mouse_up(self, x, y):
        pass