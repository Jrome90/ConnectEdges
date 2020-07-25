from typing import *
from traceback import print_exc
from collections import defaultdict

import bpy
import bmesh
from bpy.props import IntProperty, EnumProperty
from bmesh.types import *
from mathutils import Vector

from .ui import TextLayoutPanel, TextLabelProperty, TextLabel, TextBox
from .utils import (bmesh_face_loop_walker,
                    bmesh_edge_ring_walker,
                    bmesh_subdivide_edge,
                    scale_verts_along_edge,
                    ensure,
                    clamp,
                    get_perc_along,
                    get_addon_prefs,
                    Event)


class MESH_OT_ConnectEdges(bpy.types.Operator):
    bl_idname = "mesh.connect_edges"
    bl_label = "connect edges"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Creates new edges between adjacent pairs of selected edges"

    xsegments: IntProperty(name="Segments", default=1, min=1)
    xpinch: IntProperty(name="Pinch", default=0, min=-100, max=100)
    xeven: EnumProperty(name="Even", items=[("NO", "No", "", 1), ("IN", "Inside", "", 2), ("OUT", "Outside", "", 3)],
                        default="NO")

    # Enum value lookup
    even_enum_val = {0: 'NO', 1: 'IN', 2: 'OUT'}
    # Enum index lookup
    even_enum_idx = {val: key for key, val in even_enum_val.items()}

    # Unmodifed bmesh data used to initialize
    initial_bm = None
    draw_handle_hud = None
    hud = None
    # Event Object
    subject = None

    def __init__(self):

        # Bmesh to modify
        self.bm = None
       
        # Map each face to its selected edges
        # Once these edges are sub'd the indices are no longer considered valid
        self.edges_lookup: Dict[int, List[int]] = {}

        # Map a selected edge to it's start and end vertex coordinates
        self.edge_vert_pair = {}

        # Ordered edges->List of vertices in ccw order
        self.ordered_verts: DefaultDict[int, List[int]] = defaultdict(list)

        # Original coordinates of a vertex
        self.orig_vert_coords = {}

        self.min_length = float('INF')
        self.start_mouse_pos = Vector()
        self.prev_pinch = 0

        # Mouse movement engaged flag
        self.mouse_started = False

        # Text box references
        self.segment_input = None
        self.pinch_input = None

        # --For Selection--

        # Selection changed flag
        self.selection_changed = False

        # Store the selected edges
        self.selected_edges = set()
        # Edges ignored when selected
        self.ignore_edges = set()

        self.tagged = set()

        # Maps the currently selected edge to the original edge before it was subdivided
        self.selected_edge_lookup = {}

    @property
    def segments(self):
        return self.xsegments

    @segments.setter
    def segments(self, value):
        self.xsegments = value
        self.subject.notify(self, "Segments", value)

    @property
    def pinch(self):
        return self.xpinch

    @pinch.setter
    def pinch(self, value):
        self.xpinch = value
        self.subject.notify(self, "Pinch", value)

    @property
    def even(self):
        return self.xeven

    @even.setter
    def even(self, value):
        self.xeven = value
        self.subject.notify(self, "Even", value)

    @classmethod
    def setup(cls, context):
        context.active_object.update_from_editmode()
        mesh = context.active_object.data
        cls.initial_bm = bmesh.new()
        cls.initial_bm.from_mesh(mesh)

    @classmethod
    def poll(cls, context):
        if context.mode == 'EDIT_MESH':
            selection_mode = context.tool_settings.mesh_select_mode
            return selection_mode[1]  # Edge Mode

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        row = col.row()
        row.prop(self, "xsegments")

        row2 = col.row()
        row2.prop(self, "xpinch", slider=True)
        
    def selection_enabled(self, context):
        return get_addon_prefs(context).selection_enabled

    def execute(self, context):

        self.setup(context)
        self.selected_edges.clear()

        self.initial_bm.select_mode = {'EDGE'}
        ensure(self.initial_bm)
        for bm_edge in self.initial_bm.edges:
            if bm_edge.select:
                self.selected_edges.add(bm_edge.index)
                bm_edge.select_set(False)

        self.initial_bm.select_flush_mode()
        self.connect_edges(context)
        return {'FINISHED'}

    def init_hud(self, context):
        addon_prefs = get_addon_prefs(context)
        self.hud = TextLayoutPanel(10, 100, (100, addon_prefs.hud_offset))

        show_keys = addon_prefs.show_keys

        draw_segs = TextLabelProperty(0, 0, 50, 16, context, 
                                      self.segments, lambda new_val: "Segments: {0}".format(new_val), 
                                      hotkey_hint="(CTRL + MouseWheel)", show_hotkeys=show_keys)
        
        draw_pinch = TextLabelProperty(0, 0, 50, 16, context,
                                       self.pinch, lambda new_val: "Pinch: {0}".format(new_val), 
                                       hotkey_hint="(CTRL + Mouse)", show_hotkeys=show_keys)
        
        draw_even = TextLabelProperty(0, 0, 50, 16, context, 
                                      self.even, lambda new_val: "Even: {0}".format(new_val), 
                                      hotkey_hint="(E)", show_hotkeys=show_keys)
        
        self.hud.register("Pinch", draw_pinch)
        self.hud.register("Segments", draw_segs)
        self.hud.register("Even", draw_even)

        if show_keys:
            label = TextLabel(0, 0, 50, 16, "Accept (Enter) Cancel (ESC)", context)
            self.hud.register("label", label)

        self.hud.layout()
        self.subject = Event()
        # Register a callback
        self.subject.register(self.hud.update_text)

    def invoke(self, context, event):
        self.init_hud(context)
        self.execute(context)
        context.window_manager.modal_handler_add(self)
        args = (self, context)
        self.register_handlers(args, context)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if context.area:
            context.area.tag_redraw()

        if self.segment_input is not None and self.pinch_input is not None:

            handled = False
            if self.segment_input.handle_event(event):
                handled = True

            if self.pinch_input.handle_event(event):
                handled = True

            if not handled and event.type == 'LEFTMOUSE' and event.value == 'PRESS':
                self.close_input()

            return {'RUNNING_MODAL'}

        if self.selection_enabled(context):
            if (event.type == 'LEFTMOUSE'):
                self.selection_changed = True
                return {'PASS_THROUGH'}

        if self.selection_changed:
            context.active_object.update_from_editmode()
            mesh = context.active_object.data
            bm = bmesh.new()
            bm = bmesh.from_edit_mesh(mesh)

            selected = set()
            deselected = set()

            # Loop through all edges and get the recently selected or deselected edges
            for bm_edge in bm.edges:
                edge_idx = bm_edge.index
                if bm_edge.select and edge_idx not in self.tagged and edge_idx not in self.ignore_edges:
                    selected.add(edge_idx)

                if not bm_edge.select and edge_idx in self.tagged and edge_idx not in self.ignore_edges:
                    deselected_edge_idx = None

                    # Check to see if the deselected edge was once created by subdividing an edge
                    if edge_idx in self.selected_edge_lookup:
                        deselected_edge_idx = self.selected_edge_lookup[edge_idx]
                    else:
                        deselected_edge_idx = edge_idx

                    deselected.add(deselected_edge_idx)

            if selected or deselected:
                if len(selected) == 1 and not (event.shift):
                    edges = [loop.edge.index for loop in bmesh_edge_ring_walker(self.initial_bm.edges[selected.pop()])]
                    selected.update(edges)

                self.selected_edges.update(selected)
                self.selected_edges.difference_update(deselected)
                self.selection_changed = False
                
                return self.connect_edges(context)

        if self.mouse_started and event.type == 'MOUSEMOVE' and not event.alt:
            delta_x = event.mouse_x - self.start_mouse_pos.x
            self.pinch = clamp(-100, self.prev_pinch + int(delta_x / 2), 100)

            self.pinch_edges(context=context, update=True)

        if event.ctrl and not event.alt:
            if not self.mouse_started and event.value == 'PRESS':
                self.start_mouse_pos.x = event.mouse_x
                self.start_mouse_pos.y = event.mouse_y

                self.mouse_started = not self.mouse_started

            if event.type == 'WHEELUPMOUSE':
                self.segments += 1
                return self.connect_edges(context)

            elif event.type == 'WHEELDOWNMOUSE':
                self.segments -= 1
                return self.connect_edges(context)

        elif self.mouse_started and not event.ctrl:
            self.prev_pinch = self.pinch
            self.mouse_started = not self.mouse_started

        elif event.type == 'RIGHTMOUSE' and event.value == 'PRESS':
            mouse_pos = Vector((event.mouse_x, event.mouse_y))
            self.open_input(mouse_pos, context)

        elif event.type == 'MIDDLEMOUSE':
            return {'PASS_THROUGH'}

        elif event.type == 'WHEELUPMOUSE':
            return {'PASS_THROUGH'}

        elif event.type == 'WHEELDOWNMOUSE':
            return {'PASS_THROUGH'}

        elif event.type == 'E' and event.value == 'PRESS':
            # Get the index associated with a value
            enum_idx = self.even_enum_idx[self.even]
            # Get the value associated with an index
            value = self.even_enum_val[(enum_idx + 1) % len(self.even_enum_val)]
            self.even = value
            self.pinch_edges(context, update=True)

        elif event.type == 'RET' and event.value == 'PRESS':
            self.finish(context)
            return {'FINISHED'}

        elif event.type == 'ESC':  # Cancel
            self.cancelled(context)
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def finish(self, context):
        mesh = context.active_object.data
        bmesh.update_edit_mesh(mesh)
        bpy.ops.mesh.select_all(action='DESELECT')

        self.clear()
        self.bm.free()
        self.initial_bm.free()
        self.unregister_handlers(context)

    def cancelled(self, context):
        self.clear()
        self.bm.free()

        self.selection_changed = False
        self.unregister_handlers(context)

        mesh = context.active_object.data
        
        # Restore the edit mesh to the intial state
        bpy.ops.object.mode_set(mode='OBJECT')
        self.initial_bm.to_mesh(mesh)
        bpy.ops.object.mode_set(mode='EDIT')
        self.initial_bm.free()

    def open_input(self, mouse_pos, context):
        self.segment_input = TextBox(context, 0, 0, 100, 30, "Segments", 3)
        self.segment_input.text = str(self.segments)
        self.segment_input.text_size = 18
        self.segment_input.set_location(mouse_pos.x + 20, context.area.height - mouse_pos.y + 20)
        self.segment_input.set_text_changed(self.on_segment_input_changed)

        self.pinch_input = TextBox(context, 0, 0, 100, 30, "Pinch", 4)
        self.pinch_input.text = str(self.pinch)
        self.pinch_input.text_size = 18
        self.pinch_input.set_location(mouse_pos.x + 20, context.area.height - mouse_pos.y + 54)
        self.pinch_input.set_text_changed(self.on_pinch_input_changed)

    def close_input(self):
        self.segment_input = None
        self.pinch_input = None

    def on_segment_input_changed(self, textbox, context, event):
        if textbox.text:
            try:
                self.segments = int(textbox.text)
            except ValueError:
                self.report({'ERROR'}, "Please Enter An Integer Value!")

            self.connect_edges(context)

    def on_pinch_input_changed(self, textbox, context, event):
        if textbox.text and textbox.text != "-":
            pinch = 0
            try:
                pinch = int(textbox.text)
            except ValueError:
                self.report({'ERROR'}, "Please Enter An Integer Value!")

            if 100 >= pinch >= -100:
                self.prev_pinch = pinch
                self.pinch = pinch
            else:
                self.report({'ERROR'}, "Please Enter a Number Between -100 and 100!")

            self.pinch_edges(context=context, update=True)

    def draw_input(self):
        if self.segment_input is not None:
            self.segment_input.draw()
            self.pinch_input.draw()

    def draw_callback_hud(self, op, context):
        self.draw_input()
        if self.hud is not None:
            self.hud.draw()

    def register_handlers(self, args, context):
        self.draw_handle_hud = bpy.types.SpaceView3D.draw_handler_add(
            self.draw_callback_hud, args, "WINDOW", "POST_PIXEL")

    def unregister_handlers(self, context):
        if self.draw_handle_hud is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self.draw_handle_hud, "WINDOW")
            del self.draw_handle_hud

    def clear(self):
        """ Clear all the data. """

        self.ordered_verts.clear()
        self.ignore_edges.clear()
        self.selected_edge_lookup.clear()

        self.edges_lookup.clear()
        self.tagged.clear()
        self.edge_vert_pair.clear()
        self.orig_vert_coords.clear()

    def create_geometry(self):
        def order_verts_on_edge(start_co, end_co, verts):
            bm.verts.ensure_lookup_table()
            verts.sort(key=lambda x: get_perc_along(start_co, end_co, bm.verts[x].co))

        bm = self.bm
        num_segs = self.segments

        subdivided_edges = set()
        for face_idx, edges in self.edges_lookup.items():
            bm.faces.ensure_lookup_table()
            for next_loop in bmesh_face_loop_walker(bm.faces[face_idx]):
                next_edge = next_loop.edge
                bm.edges.ensure_lookup_table()
                next_edge_idx = next_edge.index

                start = next_loop.vert
                end = next_loop.edge.other_vert(next_loop.vert)

                # Subdivide the edge if it was selected and hasn't been subdivided yet
                if next_edge_idx not in subdivided_edges and next_edge_idx in self.selected_edges:
                    ret = bmesh_subdivide_edge(bm, bm.edges[next_edge_idx], num_segs)

                    bm.edges.index_update()
                    new_verts = []
                    for bm_element in ret:
                        if isinstance(bm_element, BMVert):
                            new_verts.append(bm_element.index)
                            self.orig_vert_coords[bm_element.index] = bm_element.co.copy()

                        elif isinstance(bm_element, BMEdge):
                            self.tagged.add(bm_element.index)
                            self.selected_edge_lookup[bm_element.index] = next_edge_idx
                            bm_element.select = True
                            #self.bm.select_flush_mode()

                    order_verts_on_edge(start.co, end.co, new_verts)

                    # The edge was sudivivded. Add it to the set.
                    subdivided_edges.add(next_edge_idx)
                    self.ordered_verts[next_edge_idx] = new_verts

                # The edge has already been subdivided.
                # We still need to order the vertices in the ccw direction for the current face
                elif next_edge_idx in self.selected_edges:
                    order_verts_on_edge(start.co, end.co, self.ordered_verts[next_edge_idx])

            edgenet = []
            connected_vert_pairs = set()
            for i in range(0, len(edges)):
                # List of indices from vertices that were created from subdividing the edge
                edge_a = self.ordered_verts[edges[i]]
                edge_b = self.ordered_verts[edges[(i + 1) % len(edges)]]

                n = int(num_segs / 2) + (num_segs % 2)
                for j in range(0, n):
                    vert1_idx = edge_b[j]
                    vert2_idx = edge_a[-(j + 1)]

                    # Make sure to only create one edge per vertex pair
                    vert_pair = frozenset([vert1_idx, vert2_idx])
                    if vert_pair not in connected_vert_pairs:
                        bm.verts.ensure_lookup_table()
                        bm_vert_a = bm.verts[edge_b[j]]
                        bm_vert_b = bm.verts[edge_a[-(j + 1)]]

                        bm_edge = bm.edges.new([bm_vert_a, bm_vert_b])

                        bm.edges.index_update()
                        edgenet.append(bm_edge)
                        connected_vert_pairs.add(vert_pair)

                        self.tagged.add(bm_edge.index)
                        self.ignore_edges.add(bm_edge.index)

            bm.faces.ensure_lookup_table()
            bm_face = bm.faces[face_idx]
            # Add the rest of the edges
            edgenet.extend(bm_face.edges)
            bmesh.utils.face_split_edgenet(bm_face, edgenet)

    def pinch_edges(self, context=None, update=False):
        def calc_scale_factor(min_edge_len, edge_len, inside, scale_factor):
            """ Calculates the scale factor for an edge so that the distances are all the same.
                Bounded by the min edge length.

                Args:
                    min_edge_len: The smallest edge length that is used to do the calculations.
                    edge_len: Length of the current edge we are calculating the scale factor for.
                    inside: If true, use the distance from the mid point to the farthest point as the limiting factor.
                    otherwise use the distance from the farthest point to the end point.
                    scale_factor: The scale factor value used to compute the new scale factor value
            """
            length = min_edge_len
            # Distance from the midpoint to the farthest point
            dist_from_mid = ((length / 2 * (num_segs - 1)) / (num_segs + 1)) * scale_factor

            l = edge_len
            # Distance from the midpoint to the farthest point on the edge we are computing the scale factor for.
            dist_from_mid2 = (l / 2 * (num_segs - 1)) / (num_segs + 1)

            desired_dist = 0.0
            if not inside:
                # Distance from farthest point to the end point
                dist_to_end = (length / 2 - dist_from_mid)

                # Distance from the the farthest point on the edge to the end point.
                dist_to_end2 = (l / 2) - dist_from_mid2

                # The difference between the edge we are calculating for and the edge we are bound by
                dist_difference = dist_to_end2 - dist_to_end

                desired_dist = dist_from_mid2 + dist_difference
            else:
                desired_dist = dist_from_mid

            return desired_dist / dist_from_mid2

        bm = self.bm
        num_segs = self.segments

        moved = {}
        bm.verts.ensure_lookup_table()
        for edges in self.edges_lookup.values():
            for i in range(0, len(edges)):
                edge_idx = edges[i]

                # Don't move vertices if they have already been moved
                if edge_idx not in moved:
                    verts = self.ordered_verts[edge_idx]

                    if update:
                        for vert in verts:
                            bm_vert = bm.verts[vert]
                            bm_vert.co = self.orig_vert_coords[vert]

                    start = self.edge_vert_pair[edge_idx][0]
                    end = self.edge_vert_pair[edge_idx][1]

                    scale_factor = 1
                    if num_segs > 1:

                        if self.pinch >= 0:
                            scale_factor = clamp(1, 1 + (0.01 * self.pinch / ((num_segs - 1) / 2)), 1 + (
                                (2 / (num_segs - 1))))
                        else:
                            scale_factor = clamp(0, 1 + (0.01 * self.pinch), 1)

                        even = self.even
                        inside = True
                        if even != 'NO':
                            if even == 'OUT':
                                inside = False
                            else:
                                inside = True

                            l = (start - end).length
                            scale_factor = calc_scale_factor(self.min_length, l, inside, scale_factor)

                    scale_verts_along_edge(bm, verts, start, end, scale_factor)

                moved[edge_idx] = True

        if update:
            assert context is not None, "Context was None when trying to update after pinching edges!"
            mesh = context.active_object.data
            bmesh.update_edit_mesh(mesh)

        return

    def connect_edges(self, context) -> str:
        def do_connect_edges():
            def order_selected_edges_ccw(bm):
                self.min_length = float('INF')
                bm.faces.ensure_lookup_table()
                for face_idx in self.edges_lookup.keys():
                    ordered_edges = []

                    loop_walker = bmesh_face_loop_walker(bm.faces[face_idx])
                    for next_loop in loop_walker:
                        bm_edge = next_loop.edge
                        edge_idx = bm_edge.index

                        if bm_edge.index in self.tagged:
                            ordered_edges.append(edge_idx)

                            first_vert_co = next_loop.vert.co
                            other_vert_co = bm_edge.other_vert(next_loop.vert).co
                            self.edge_vert_pair[edge_idx] = [first_vert_co.copy(), other_vert_co.copy()]

                            edge_len = (first_vert_co - other_vert_co).length_squared
                            if edge_len < self.min_length:
                                self.min_length = edge_len

                    self.edges_lookup[face_idx] = ordered_edges

                self.min_length = self.min_length ** 0.5

            # Restore the initial state of the mesh data
            mesh = context.active_object.data
            bpy.ops.object.mode_set(mode='OBJECT')
            self.initial_bm.to_mesh(mesh)
            bpy.ops.object.mode_set(mode='EDIT')

            self.bm = bmesh.from_edit_mesh(mesh)
            
            bm = self.bm
            self.clear()
            selected_edges = self.selected_edges
            bm.select_mode = {'EDGE'}

            bm.edges.ensure_lookup_table()
            if len(selected_edges) > 1:
                for edge_idx in selected_edges:
                    bm_edge = bm.edges[edge_idx]

                    for bm_face in bm_edge.link_faces:
                        if bm_face.index not in self.edges_lookup:
                            self.edges_lookup[bm_face.index] = [bm_edge.index]
                        else:
                            self.edges_lookup[bm_face.index].append(bm_edge.index)

                    bm_edge.select= True
                    #self.bm.select_flush_mode()
                    self.tagged.add(bm_edge.index)

                # Filter out faces with only one selected edge
                self.edges_lookup = {face: edges for (face, edges) in self.edges_lookup.items() if len(edges) > 1}
            elif len(selected_edges) == 1:
                # Select the only edge
                bm.edges[selected_edges.pop()].select = True
                

            order_selected_edges_ccw(bm)

            self.create_geometry()

            self.pinch_edges()
            # self.bm.verts.index_update()
            # self.bm.edges.index_update()
            # self.bm.faces.index_update()
            # for edge in self.bm.edges:
            #     if edge.select:
            #         print("Selected: {}".format(edge.index))
            self.bm.select_flush_mode()
            bmesh.update_edit_mesh(mesh, True)


        try:
            do_connect_edges()
        except BaseException:
            self.report({'ERROR'}, "Something went wrong. See console for more info.")
            print_exc()

            self.cancelled(context)
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}