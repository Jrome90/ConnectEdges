# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

bl_info = {
    "name" : "Connect Edges",
    "author" : "Jrome",
    "description" : "Creates new edges between adjacent pairs of selected edges",
    "blender" : (2, 90, 0),
    "version" : (0, 2, 0),
    "location" : "Mesh > Edge > Connect Edges",
    "warning" : "",
    "category" : "Mesh"
}

# 

if "bpy" in locals():
    import importlib
    importlib.reload(connect_edges)
    importlib.reload(preferences)
else:

    from . import (
        connect_edges,
        preferences
    )

import bpy


def menu_draw(self, context):
    layout = self.layout
    layout.separator()
    layout.operator_context = "INVOKE_DEFAULT"
    layout.operator(connect_edges.MESH_OT_ConnectEdges.bl_idname, text='Connect Edges')


addon_keymaps = []
def register():
    
    bpy.utils.register_class(connect_edges.MESH_OT_ConnectEdges)
    bpy.utils.register_class(preferences.ConnectEdgesPreferences)

    bpy.types.VIEW3D_MT_edit_mesh_edges.append(menu_draw)
    bpy.types.VIEW3D_MT_edit_mesh_context_menu.append(menu_draw)

    # handle the keymap
    kc = bpy.context.window_manager.keyconfigs.addon
    km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')

    kmi = km.keymap_items.new("mesh.connect_edges", 'C', 'PRESS', alt=True, repeat=False)

    addon_keymaps.append((km, kmi))


def unregister():
   
    bpy.utils.unregister_class(connect_edges.MESH_OT_ConnectEdges)
    bpy.utils.unregister_class(preferences.ConnectEdgesPreferences)

    bpy.types.VIEW3D_MT_edit_mesh_edges.remove(menu_draw)
    bpy.types.VIEW3D_MT_edit_mesh_context_menu.remove(menu_draw)

    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)

    addon_keymaps.clear()