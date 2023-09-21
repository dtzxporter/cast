#!/bin/bash

mkdir -p ./.releases/io_scene_cast
mkdir -p ./.releases/maya
mkdir -p ./.releases/upload

cp -r ./plugins/blender/* ./.releases/io_scene_cast/
cp -r ./libraries/python/* ./.releases/io_scene_cast/
cp -r ./plugins/maya/* ./.releases/maya/
cp -r ./libraries/python/* ./.releases/maya/

# TODO: This packages the parent folders with the zip files.
zip -r -q ./.releases/upload/blender_cast_plugin.zip ./.releases/io_scene_cast/
zip -r -q ./.releases/upload/maya_cast_plugin.zip ./.releases/maya/