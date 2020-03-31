import bpy
import bmesh
import os
import array
import math
from mathutils import *
from bpy_extras.image_utils import load_image
from .cast import Cast, Model, Animation, Curve, NotificationTrack, Mesh, Skeleton, Bone, Material, File

def importSkeletonNode(skeleton):
    if skeleton is None:
        return (None, None)

    armature = bpy.data.armatures.new("Joints")
    armature.display_type = "STICK"

    skeletonObj = bpy.data.objects.new("Root", armature)
    skeletonObj.show_in_front = True

    bpy.context.view_layer.active_layer_collection.collection.objects.link(skeletonObj)
    bpy.context.view_layer.objects.active = skeletonObj

    bpy.ops.object.mode_set(mode='EDIT')

    bones = skeleton.Bones()
    handles = [None] * len(bones)
    matrices = {}

    for i, bone in enumerate(bones):
        newBone = armature.edit_bones.new(bone.Name())
        newBone.tail = 0, 0.05, 0 # I am sorry but blender sucks

        matRotation = Quaternion(bone.LocalRotation()).to_matrix().to_4x4()
        matTranslation = Matrix.Translation(Vector(bone.LocalPosition()))

        matrices[bone.Name()] = matTranslation @ matRotation
        handles[i] = newBone

    for i, bone in enumerate(bones):
        if bone.ParentIndex() > -1:
            handles[i].parent = handles[bone.ParentIndex()]

    bpy.context.view_layer.objects.active = skeletonObj
    bpy.ops.object.mode_set(mode='POSE')

    for bone in skeletonObj.pose.bones:
        bone.matrix_basis.identity()
        bone.matrix = matrices[bone.name]

    bpy.ops.pose.armature_apply()




def importModelNode(model, path):
    # Import skeleton for binds, materials for meshes
    importSkeletonNode(model.Skeleton())

def importRootNode(node, path):
    for child in node.ChildrenOfType(Model):
        importModelNode(child, path)
    # for child in node.ChildrenOfType(Animation):
    #     importAnimationNode(child, path)


def importCast(path):
    cast = Cast()
    cast.load(path)

    for root in cast.Roots():
        importRootNode(root, path)


def load(self, context, filepath=""):
    # Parse and load cast nodes
    importCast(filepath)

    # Update the scene, reset view mode before returning.
    bpy.context.view_layer.update()
    bpy.ops.object.mode_set(mode="OBJECT")
    return True