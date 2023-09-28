#!/bin/bash

mkdir -p ./.releases/io_scene_cast
mkdir -p ./.releases/maya
mkdir -p ./.releases/upload

cp -r ./plugins/blender/* ./.releases/io_scene_cast/
cp -r ./libraries/python/* ./.releases/io_scene_cast/
cp -r ./plugins/maya/* ./.releases/maya/
cp -r ./libraries/python/* ./.releases/maya/

ditto -c -k --sequesterRsrc --keepParent ./.releases/io_scene_cast/ ./.releases/upload/blender_cast_plugin.zip
ditto -c -k --sequesterRsrc ./.releases/maya/ ./.releases/upload/maya_cast_plugin.zip