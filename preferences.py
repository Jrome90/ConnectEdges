from bpy.types import AddonPreferences
from bpy.props import BoolProperty

class ConnectEdgesPreferences(AddonPreferences):
    # this must match the add-on name, use '__package__'
    # when defining this in a submodule of a python package.
    bl_idname = __package__

    selection_enabled: BoolProperty(name="Enable Selection", default=False, 
                                    description="Enable selection while the operator is running")
    show_keys: BoolProperty(name="Display Hotkeys", default=True, description="Display the hotkeys in the HUD")

    def draw(self, context):
        preferences = context.preferences
        addon_prefs = preferences.addons[__package__].preferences

        layout = self.layout
        if addon_prefs.selection_enabled:
            layout.label(text="Warning: Selection can be slow with high poly meshes. Selecting while the operator runs will break both adjust last op and repeat last op for that operator session", icon = 'ERROR')
        layout.prop(self, "selection_enabled")
        layout.prop(self, "show_keys")