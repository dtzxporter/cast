New-Item -Force -Path "./" -Name ".releases" -ItemType "directory"
New-Item -Force -Path "./.releases" -Name "io_scene_cast" -ItemType "directory"
New-Item -Force -Path "./.releases" -Name "maya" -ItemType "directory"
New-Item -Force -Path "./.releases" -Name "upload" -ItemType "directory"

Copy-item -Force -Recurse -Verbose "./plugins/blender/*" "./.releases/io_scene_cast/"
Copy-item -Force -Recurse -Verbose "./libraries/python/*" "./.releases/io_scene_cast/"
Copy-item -Force -Recurse -Verbose "./plugins/maya/*" "./.releases/maya/"
Copy-item -Force -Recurse -Verbose "./libraries/python/*" "./.releases/maya/"

Compress-Archive -Force -Path "./.releases/io_scene_cast" -DestinationPath "./.releases/upload/blender_cast_plugin.zip"
Compress-Archive -Force -Path "./.releases/maya/*.py" -DestinationPath "./.releases/upload/maya_cast_plugin.zip"