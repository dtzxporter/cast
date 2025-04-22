import bpy


def utilityIsVersionAtLeast(major, minor):
    if bpy.app.version[0] > major:
        return True
    elif bpy.app.version[0] == major and bpy.app.version[1] >= minor:
        return True
    return False
