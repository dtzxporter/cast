import bpy
import os

from bpy.props import *
from bpy_extras.io_utils import ExportHelper, ImportHelper

from .shared_cast import utilityIsVersionAtLeast

bl_info = {
    "name": "Cast Support",
    "author": "DTZxPorter",
    "version": (1, 8, 2),
    "blender": (3, 6, 0),
    "location": "File > Import",
    "description": "Import & Export Cast",
    "wiki_url": "https://github.com/dtzxporter/cast",
    "tracker_url": "https://github.com/dtzxporter/cast/issues",
    "category": "Import-Export"
}


class CastProperties(bpy.types.PropertyGroup):
    import_scenes_path: StringProperty(
        name="Path", description="Select the root directory where instance scenes are located", default="", subtype="DIR_PATH")


class CastImportScenePanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_cast_import_scene_panel"
    bl_label = "Import Scenes Path"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Cast"
    bl_context = "objectmode"

    def draw(self, context):
        self.layout.prop(context.scene.cast_properties, "import_scenes_path")


class ImportCast(bpy.types.Operator, ImportHelper):
    bl_idname = "import_scene.cast"
    bl_label = "Import Cast"
    bl_description = "Import one or more Cast files"
    bl_options = {'PRESET'}

    directory: StringProperty()

    filename_ext = ".cast"
    filter_glob: StringProperty(default="*.cast", options={'HIDDEN'})

    files: CollectionProperty(type=bpy.types.PropertyGroup)

    import_time: BoolProperty(
        name="Import At Scene Time", description="Import animations starting at the current scene time", default=False)

    import_reset: BoolProperty(
        name="Import Resets Scene", description="Imported animations will create new actions instead of blending", default=True)

    import_skin: BoolProperty(
        name="Import Bind Skin", description="Imports and binds a model to it's smooth skin", default=True)

    import_ik: BoolProperty(
        name="Import IK Handles", description="Imports and configures ik handles for the models skeleton", default=True)

    import_constraints: BoolProperty(
        name="Import Constraints", description="Imports and configures constraints for the models skeleton", default=True)

    import_blend_shapes: BoolProperty(
        name="Import Blend Shapes", description="Imports and configures blend shapes for a model", default=True)

    import_hair: BoolProperty(
        name="Import Hair", description="Imports hair definitions for models", default=True)

    import_merge: BoolProperty(
        name="Import Merge", description="Imports and merges models together with the selected armature")

    create_hair_type: EnumProperty(name="Type", description="Change the way hair definitions are imported",
                                   items=[("curve", "Create Curve Hairs", "Creates hairs as curves"),
                                          ("mesh", "Create Mesh Hairs", "Creates hairs as simple meshes")], default="curve")

    create_hair_subtype: EnumProperty(name="Mode", description="Change how hair will render",
                                      items=[("bevel", "Curves", "Curves will render naturally"),
                                             ("particle", "Particle System", "Curves will use the particle system")], default="bevel")

    def draw(self, context):
        self.layout.label(text="Import Settings")
        self.layout.prop(self, "import_time")
        self.layout.prop(self, "import_reset")
        self.layout.prop(self, "import_skin")
        self.layout.prop(self, "import_ik")
        self.layout.prop(self, "import_constraints")
        self.layout.prop(self, "import_blend_shapes")
        self.layout.prop(self, "import_hair")
        self.layout.prop(self, "import_merge")

        self.layout.separator_spacer()

        if utilityIsVersionAtLeast(4, 1):
            (header, body) = self.layout.panel("Hair Settings")

            header.enabled = self.import_hair
            header.label(text="Hair Settings")
        else:
            self.layout.label(text="Hair Settings")

            body = self.layout.column(align=False)

        if body:
            body.enabled = self.import_hair

            row = body.column(align=False)
            row.prop(self, "create_hair_type")

            row = row.column(align=False)
            row.enabled = self.create_hair_type == "curve"
            row.prop(self, "create_hair_subtype")

        self.layout.separator_spacer()

        if not context.scene.cast_properties.import_scenes_path:
            row = self.layout.column(align=False)
            row.label(text="INFO", icon="QUESTION")
            row.label(text="To import worlds select a")
            row.label(text="scene path using the Cast")
            row.label(text="menu on the right of blender.")
        else:
            row = self.layout.column(align=False)
            row.label(text="INFO", icon="QUESTION")
            row.label(text="A world scene path")
            row.label(text="has been selected and")
            row.label(text="is ready to be used.")

    def execute(self, context):
        from . import import_cast
        try:
            if self.files:
                for file in self.files:
                    file = os.path.join(self.directory, file.name)
                    import_cast.load(self, context, file)
            else:
                import_cast.load(self, context, self.filepath)

            self.report({'INFO'}, 'Cast has been loaded')
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'FINISHED'}

    @classmethod
    def poll(self, context):
        return True


class ExportCast(bpy.types.Operator, ExportHelper):
    bl_idname = "export_scene.cast"
    bl_label = "Export Cast"
    bl_description = "Export a Cast file"
    bl_options = {'PRESET'}
    bl_version = bl_info["version"]

    filename_ext = ".cast"
    filter_glob: StringProperty(default="*.cast", options={'HIDDEN'})

    files: CollectionProperty(type=bpy.types.PropertyGroup)

    export_selected: BoolProperty(
        name="Export Selected", description="Whether or not to only export the selected object", default=False)

    incl_model: BoolProperty(
        name="Include Models", description="Whether or not to export model data", default=True)

    incl_animation: BoolProperty(
        name="Include Animations", description="Whether or not to export animation data", default=True)

    incl_notetracks: BoolProperty(
        name="Include Notetracks", description="Whether or not to export pose markers as notetracks", default=True)

    is_looped: BoolProperty(
        name="Looped", description="Mark the animation as looping", default=False)

    scale: FloatProperty(
        name="Scale", description="Apply a scale modifier to any meshes, bones, or animation data", default=1.0)

    up_axis: EnumProperty(
        name="Up", description="Override the up axis for this scene", items=[("y", "Y Up", "The Y axis points up"), ("z", "Z Up", "The Z axis points up")], default="y")

    def draw(self, context):
        self.layout.label(text="Export Settings")
        self.layout.prop(self, "export_selected")
        self.layout.prop(self, "incl_model")
        self.layout.prop(self, "incl_animation")
        self.layout.prop(self, "incl_notetracks")
        self.layout.prop(self, "is_looped")
        self.layout.prop(self, "scale")
        self.layout.prop(self, "up_axis")

    def execute(self, context):
        from . import export_cast
        try:
            export_cast.save(self, context, self.filepath)

            self.report({'INFO'}, 'Cast has been exported')
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

    @classmethod
    def poll(self, context):
        return True


def menu_func_cast_import(self, context):
    self.layout.operator(ImportCast.bl_idname, text="Cast (.cast)")


def menu_func_cast_export(self, context):
    self.layout.operator(ExportCast.bl_idname, text="Cast (.cast)")


def register():
    bpy.utils.register_class(ImportCast)
    bpy.utils.register_class(ExportCast)
    bpy.utils.register_class(CastProperties)
    bpy.utils.register_class(CastImportScenePanel)

    bpy.types.TOPBAR_MT_file_import.append(menu_func_cast_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_cast_export)

    bpy.types.Scene.cast_properties = PointerProperty(type=CastProperties)


def unregister():
    bpy.utils.unregister_class(ImportCast)
    bpy.utils.unregister_class(ExportCast)
    bpy.utils.unregister_class(CastImportScenePanel)
    bpy.utils.unregister_class(CastProperties)

    bpy.types.TOPBAR_MT_file_import.remove(menu_func_cast_import)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_cast_export)

    del bpy.types.Scene.cast_properties


bpy.types.PoseBone.cast_bind_pose_scale = FloatVectorProperty(
    name="Cast bind pose scale", description="Used to help cast workaround a blender issue where the bind pose scale is destroyed on EditBones.", default=(1.0, 1.0, 1.0))

if __name__ == "__main__":
    register()
