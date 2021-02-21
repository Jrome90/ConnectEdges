import bpy 

from bpy.types import AddonPreferences
from bpy.props import BoolProperty, IntProperty, FloatProperty, EnumProperty

from bpy.app.translations import contexts as i18n_contexts

import rna_keymap_ui

class ConnectEdgesPreferences(AddonPreferences):
    # this must match the add-on name, use '__package__'
    # when defining this in a submodule of a python package.
    bl_idname = __package__

    tabs : EnumProperty(name="Tabs",
    items = [("GENERAL", "General", ""),
        ("KEYMAPS", "Keymaps", ""),
        ("HELP", "Help", ""),],
    default="GENERAL")

    selection_enabled: BoolProperty(name="Enable Selection", default=False, 
                                    description="Enable selection while the operator is running")

    show_hud: BoolProperty(name="Display the HUD", default=True, description="Display the HUD in the viewport.")

    show_keys: BoolProperty(name="Display Hotkeys", default=False, description="Display the hotkeys in the HUD")

    hud_offset_x: IntProperty(name="HUD offset x", default=70, min=0, description="Offset the HUD in the X direction", subtype='PIXEL')
    hud_offset_y: IntProperty(name="HUD offset y", default=100, min=0, description="Offset the HUD in the Y direction", subtype='PIXEL')

    hud_scale_fac: IntProperty(name="HUD text scale", default=100, min=0, max=1000, description="Scale up the HUD text", subtype='PERCENTAGE')
    # hud_use_ui_scale: BoolProperty(name="use DPI scale", default=False, description="Size multiplier to use when drawing custom user interface elements,\
    #      so that they are scaled correctly on screens with different DPI. This value is based on operating system DPI settings and Blender display scale")

    def draw(self, context):

        layout = self.layout
        row = layout.row()
        row.prop(self, "tabs", expand=True)

        box = layout.box()

        if self.tabs == "GENERAL":
            self.draw_general(context, box)

        elif self.tabs == "KEYMAPS":
            self.draw_keymaps(context, box)

        elif self.tabs == "HELP":
            self.draw_help(context, box)

    def draw_general(self, context, layout):
        preferences = context.preferences
        addon_prefs = preferences.addons[__package__].preferences

        
        if addon_prefs.selection_enabled:
            layout.label(text="Warning: Selection can be slow with high poly meshes. Selecting while the operator runs will break both adjust last op and repeat last op for that operator session", icon = 'ERROR')
        layout.prop(self, "selection_enabled")

        layout.prop(self, "show_hud")
        if addon_prefs.show_hud:
            layout.prop(self, "show_keys")
            layout.prop(self, "hud_offset_x")
            layout.prop(self, "hud_offset_y")
            layout.prop(self, "hud_scale_fac")
    
    def draw_keymaps(self, context, layout):

        wm = context.window_manager
        kc = wm.keyconfigs.user

        layout.label(text="Operator:")

        km_name = self.get_operator_keymaps()
        km = kc.keymaps.get(km_name)
        if km:
            self.draw_km(kc, km, layout)
    
    def draw_help(self, context, layout):
        layout.label(text="Spacebar or Left mouse click: Confirm operator. (Left mouse click only works when selection is disabled)")
        layout.label(text="Escape: Cancel the operator")
        layout.label(text="CTRL + Middle Mouse: Increase/Decrease the number of segments.")
        layout.label(text="CTRL + Mouse Move: Increase/Decrease the pinch value.")
        layout.label(text="Right Click: Open numerical input box.")
        layout.label(text="E: Change the even setting.")
        layout.label(text="     Even (In): The distance between all created edges are the same.")
        layout.label(text="     Even (Out): The distance between the outer edges are the same.")
        layout.label(text="     Even (None): The distance between the edges is based on the edge length of the newly connected edges.")

    @staticmethod
    def get_operator_keymaps():

        km_name = 'Mesh'
        return km_name

    @staticmethod
    def draw_km(kc, km, layout):
        layout.context_pointer_set("keymap", km)

        row = layout.row()
        row.prop(km, "show_expanded_items", text="", emboss=False)
        row.label(text=km.name, text_ctxt=i18n_contexts.id_windowmanager)

        if km.show_expanded_items:
            col = layout.column()

            for kmi in km.keymap_items:
                if "connect_edges" in kmi.idname:
                    rna_keymap_ui.draw_kmi(["ADDON", "USER", "DEFAULT"], kc, km, kmi, col, 0)