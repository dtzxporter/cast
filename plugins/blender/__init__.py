import bpy
import bpy_extras.io_utils

from bpy.types import Operator, AddonPreferences
from bpy.props import *
from bpy_extras.io_utils import ExportHelper, ImportHelper
from bpy.utils import register_class
from bpy.utils import unregister_class

bl_info = {
    "name": "Cast Support",
    "author": "DTZxPorter",
    "version": (0, 90, 5),
    "blender": (2, 90, 0),
    "location": "File > Import",
    "description": "Import Cast",
    "wiki_url": "https://github.com/dtzxporter/cast",
    "tracker_url": "https://github.com/dtzxporter/cast/issues",
    "category": "Import-Export"
}


class ImportCast(bpy.types.Operator, ImportHelper):
    bl_idname = "import_scene.cast"
    bl_label = "Import Cast"
    bl_description = "Import one or more Cast files"
    bl_options = {'PRESET'}

    filename_ext = ".cast"
    filter_glob: StringProperty(default="*.cast", options={'HIDDEN'})

    files: CollectionProperty(type=bpy.types.PropertyGroup)

    def execute(self, context):
        from . import import_cast
        result = import_cast.load(
            self, context, **self.as_keywords(ignore=("filter_glob", "files")))
        if result:
            self.report({'INFO'}, 'Cast has been loaded')
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, 'Failed to load Cast')
            return {'CANCELLED'}

    @classmethod
    def poll(self, context):
        return True


def menu_func_cast_import(self, context):
    self.layout.operator(ImportCast.bl_idname, text="Cast (.cast)")


def register():
    bpy.utils.register_class(ImportCast)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_cast_import)


def unregister():
    bpy.utils.unregister_class(ImportCast)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_cast_import)


if __name__ == "__main__":
    register()
