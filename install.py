import os
import zipfile
import json
import urllib.request as r
import platform
import shutil 

def is_maya():
    try:
        import maya.cmds as cmds
        return True
    except ImportError:
        return False

def is_blender():
    try:
        import bpy
        return True
    except ImportError:
        return False

def get_latest_release():
    try:
        release_url = 'https://api.github.com/repos/dtzxporter/cast/releases/latest'
        req = r.Request(release_url, headers={'User-Agent': 'Mozilla/5.0'})
        with r.urlopen(req) as response:
            release_info = json.loads(response.read())
        return release_info
    except Exception as e:
        print(f"Failed to fetch releases: {e}")
        return None

def find_asset(release_info, app_name):
    target_zip_name = f"{app_name.lower()}_cast_plugin.zip"
    for asset in release_info['assets']:
        if asset['name'].lower() == target_zip_name:
            return asset['browser_download_url']
    return None

def install_maya():
    import maya.cmds as cmds

    print("Installing Cast plugin for Maya")

    maya_version = cmds.about(version=True)

    
    plugin_dir = os.path.join(cmds.internalVar(userAppDir=True), 'plug-ins')

    system = platform.system().lower()
    if system == 'windows':
        program_files = os.environ.get('PROGRAMFILES', 'C:\\Program Files')
        potential_maya_install_dir_64 = os.path.join(program_files, 'Autodesk', f'Maya{maya_version}')
        potential_maya_install_dir_32 = os.path.join(os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)'), 'Autodesk', f'Maya{maya_version}')

        if os.path.exists(os.path.join(potential_maya_install_dir_64, 'bin', 'plug-ins')):
            plugin_dir = os.path.join(potential_maya_install_dir_64, 'bin', 'plug-ins')
        elif os.path.exists(os.path.join(potential_maya_install_dir_32, 'bin', 'plug-ins')):
            plugin_dir = os.path.join(potential_maya_install_dir_32, 'bin', 'plug-ins')

    os.makedirs(plugin_dir, exist_ok=True)
    print(f"Using plugin directory: {plugin_dir}")

    release_info = get_latest_release()
    if not release_info:
        return False

    download_url = find_asset(release_info, 'maya')
    if not download_url:
        print("No Maya plugin found.")
        return False

    zip_temp_path = os.path.join(plugin_dir, "temp_cast_maya_plugin.zip")

    try:
        print(f"Downloading Cast {release_info['tag_name']} for Maya")
        r.urlretrieve(download_url, zip_temp_path)

        with zipfile.ZipFile(zip_temp_path, 'r') as zip_ref:
            zip_ref.extractall(plugin_dir)

        os.remove(zip_temp_path)

        target_plugin_filename = 'castplugin.py'
        plugin_file_full_path = os.path.join(plugin_dir, target_plugin_filename)

        if not os.path.exists(plugin_file_full_path):
            return False

        loaded = False
        try:
            cmds.loadPlugin(target_plugin_filename)
            print(f"Successfully loaded plugin: {target_plugin_filename}")

            try:
                cmds.pluginInfo(target_plugin_filename, edit=True, autoload=True)
                print(f"Set '{target_plugin_filename}' to auto-load on startup.")
            except Exception as e:
                print(f"Could not set auto-load for '{target_plugin_filename}': {e}")
            loaded = True

        except Exception as e:
            print(f"Failed to load '{target_plugin_filename}': {e}")

        if not loaded:
            print("Plugin could not be loaded.")
            return False

        print(f"Cast plugin {release_info['tag_name']} installed for Maya")
        return True

    except Exception as e:
        print(f"Installation failed: {e}")
        if os.path.exists(zip_temp_path):
            os.remove(zip_temp_path)
        return False


def install_blender():
    import bpy

    print("Installing Cast plugin for Blender")

    addon_dir = bpy.utils.user_resource('SCRIPTS', path="addons")
    os.makedirs(addon_dir, exist_ok=True)

    release_info = get_latest_release()
    if not release_info:
        return False

    download_url = find_asset(release_info, 'blender')
    if not download_url:
        print("No Blender plugin found.")
        return False

    zip_path = os.path.join(addon_dir, "temp_cast_blender_plugin.zip")
    
    try:
        print(f"Downloading Cast {release_info['tag_name']} for Blender")
        r.urlretrieve(download_url, zip_path)

    
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(addon_dir)

        os.remove(zip_path) 

        print(f"Cast plugin {release_info['tag_name']} installed for Blender!")
        
        
        print("Attempting to enable Blender addon")
        enabled_addon = False
        try:
            
            bpy.ops.preferences.addon_refresh()
            
            
            for folder_name in os.listdir(addon_dir):
                folder_path = os.path.join(addon_dir, folder_name)

                if os.path.isdir(folder_path) and \
                   'cast' in folder_name.lower() and \
                   os.path.exists(os.path.join(folder_path, '__init__.py')):
                    
                    bpy.ops.preferences.addon_enable(module=folder_name)
                    print(f"Successfully enabled Cast addon: '{folder_name}'")
                    enabled_addon = True
                    break 
            
            if not enabled_addon:
                print("Could not enable the Cast addon.")

        except Exception as e:
            print(f"Failed to enable addon: {e}")
            return True 

        return True

    except Exception as e:
        print(f"Installation failed: {e}")
        if os.path.exists(zip_path):
            os.remove(zip_path)
        return False

def main():
    print("Cast Plugin Installer")
    print("=" * 40)

    if is_maya():
        print("Detected Maya environment")
        success = install_maya()
    elif is_blender():
        print("Detected Blender environment")
        success = install_blender()
    else:
        print("Error: This script must be run inside Maya or Blender.")
        return False

    if success:
        print("\nInstallation completed successfully!")
    else:
        print("\nInstallation failed!")

    return success

if __name__ == "__main__":
    main()