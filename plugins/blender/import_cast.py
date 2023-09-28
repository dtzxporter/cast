import bpy
import bmesh
import os
import array
import time
import math
from mathutils import *
from bpy_extras.io_utils import unpack_list
from bpy_extras.image_utils import load_image
from .cast import Cast, Model, Animation, Curve, NotificationTrack, Mesh, Skeleton, Bone, Material, File


def utilityBuildPath(root, asset):
    if os.path.isabs(asset):
        return asset

    root = os.path.dirname(root)
    return os.path.join(root, asset)


def utilityAssignBSDFMaterialSlots(material, slots, path):
    # We will two shaders, one for metalness and one for specular
    if "metal" in slots:
        # Principled is default shader node
        shader = material.node_tree.nodes["Principled BSDF"]
        switcher = {
            "albedo": "Base Color",
            "diffuse": "Base Color",
            "specular": "Specular",
            "metal": "Metallic",
            "roughness": "Roughness",
            "normal": "Normal",
            "emissive": "Emission"
        }
    else:
        # We need to create the specular node, removing principled first
        material.node_tree.nodes.remove(
            material.node_tree.nodes["Principled BSDF"])
        material_output = material.node_tree.nodes.get('Material Output')
        shader = material.node_tree.nodes.new('ShaderNodeEeveeSpecular')
        material.node_tree.links.new(
            material_output.inputs[0], shader.outputs[0])
        switcher = {
            "albedo": "Base Color",
            "diffuse": "Base Color",
            "specular": "Specular",
            "roughness": "Roughness",
            "emissive": "Emissive Color",
            "normal": "Normal",
            "ao": "Ambient Occlusion"
        }

    # Loop and connect the slots
    for slot in slots:
        connection = slots[slot]
        if not connection.__class__ is File:
            continue
        if not slot in switcher:
            continue

        texture = material.node_tree.nodes.new("ShaderNodeTexImage")
        try:
            texture.image = bpy.data.images.load(
                utilityBuildPath(path, connection.Path()))
        except RuntimeError:
            pass

        material.node_tree.links.new(
            shader.inputs[switcher[slot]], texture.outputs["Color"])


def importSkeletonNode(name, skeleton, collection):
    if skeleton is None or len(skeleton.Bones()) == 0:
        return None

    armature = bpy.data.armatures.new("Joints")
    armature.display_type = "STICK"

    skeletonObj = bpy.data.objects.new(name, armature)
    skeletonObj.show_in_front = True

    collection.objects.link(skeletonObj)
    bpy.context.view_layer.objects.active = skeletonObj
    bpy.ops.object.mode_set(mode='EDIT')

    bones = skeleton.Bones()
    handles = [None] * len(bones)
    matrices = {}

    for i, bone in enumerate(bones):
        newBone = armature.edit_bones.new(bone.Name())
        newBone.tail = 0, 0.05, 0  # I am sorry but blender sucks

        tempQuat = bone.LocalRotation()  # Also sucks, WXYZ? => XYZW master race
        matRotation = Quaternion(
            (tempQuat[3], tempQuat[0], tempQuat[1], tempQuat[2])).to_matrix().to_4x4()
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
    return skeletonObj


def importMaterialNode(path, material):
    # If you already created the material, ignore this
    materialNew = bpy.data.materials.get(material.Name())
    if materialNew is not None:
        return material.Name(), materialNew

    materialNew = bpy.data.materials.new(name=material.Name())
    materialNew.use_nodes = True

    # Blender really only wants a BSDF shader node
    # so we're gonna give it one
    utilityAssignBSDFMaterialSlots(materialNew, material.Slots(), path)

    return material.Name(), materialNew


def importModelNode(model, path):
    # Extract the name of this model from the path
    modelName = os.path.splitext(os.path.basename(path))[0]

    # Create a collection for our objects
    collection = bpy.data.collections.new(modelName)
    bpy.context.scene.collection.children.link(collection)

    # Import skeleton for binds, materials for meshes
    skeletonObj = importSkeletonNode(modelName, model.Skeleton(), collection)
    materialArray = {key: value for (key, value) in (
        importMaterialNode(path, x) for x in model.Materials())}

    # For mesh import performance, unlink from scene until we're done
    bpy.context.scene.collection.children.unlink(collection)

    meshes = model.Meshes()
    for mesh in meshes:
        newMesh = bpy.data.meshes.new("polySurfaceMesh")
        meshObj = bpy.data.objects.new(mesh.Name() or "CastMesh", newMesh)

        vertexPositions = mesh.VertexPositionBuffer()
        newMesh.vertices.add(int(len(vertexPositions) / 3))
        newMesh.vertices.foreach_set("co", vertexPositions)

        faces = mesh.FaceBuffer()
        faceIndicesCount = len(faces)
        facesCount = faceIndicesCount / 3

        # Remap face indices to match blender's winding order
        faces = unpack_list([(faces[x + 1], faces[x + 2], faces[x + 0])
                             for x in range(0, faceIndicesCount, 3)])

        newMesh.loops.add(faceIndicesCount)
        newMesh.polygons.add(int(facesCount))

        newMesh.loops.foreach_set("vertex_index", faces)
        newMesh.polygons.foreach_set(
            "loop_start", [x for x in range(0, faceIndicesCount, 3)])
        newMesh.polygons.foreach_set(
            "loop_total", [3 for _ in range(0, faceIndicesCount, 3)])
        newMesh.polygons.foreach_set(
            "material_index", [0 for _ in range(0, faceIndicesCount, 3)])

        for i in range(mesh.UVLayerCount()):
            uvBuffer = mesh.VertexUVLayerBuffer(i)
            newMesh.uv_layers.new(do_init=False)
            newMesh.uv_layers[i].data.foreach_set("uv", unpack_list(
                [(uvBuffer[x * 2], 1.0 - uvBuffer[(x * 2) + 1]) for x in faces]))

        vertexColors = mesh.VertexColorBuffer()
        if vertexColors is not None:
            newMesh.vertex_colors.new(do_init=False)
            newMesh.vertex_colors[0].data.foreach_set("color", unpack_list([((vertexColors[x] >> 0 & 0xff) / 255.0, (vertexColors[x]
                                                                                                                     >> 8 & 0xff) / 255.0, (vertexColors[x] >> 16 & 0xff) / 255.0, (vertexColors[x] >> 24 & 0xff) / 255.0) for x in faces]))

        vertexNormals = mesh.VertexNormalBuffer()
        newMesh.create_normals_split()
        newMesh.loops.foreach_set("normal", unpack_list(
            [(vertexNormals[x * 3], vertexNormals[(x * 3) + 1], vertexNormals[(x * 3) + 2]) for x in faces]))

        newMesh.validate(clean_customdata=False)
        clnors = array.array('f', [0.0] * (len(newMesh.loops) * 3))
        newMesh.loops.foreach_get("normal", clnors)

        newMesh.polygons.foreach_set(
            "use_smooth", [True] * len(newMesh.polygons))

        newMesh.normals_split_custom_set(tuple(zip(*(iter(clnors),) * 3)))
        newMesh.use_auto_smooth = True

        meshMaterial = mesh.Material()
        if meshMaterial is not None:
            newMesh.materials.append(materialArray[meshMaterial.Name()])

        if skeletonObj is not None:
            boneGroups = []
            for bone in model.Skeleton().Bones():
                boneGroups.append(meshObj.vertex_groups.new(name=bone.Name()))

            meshObj.parent = skeletonObj
            modifier = meshObj.modifiers.new('Armature Rig', 'ARMATURE')
            modifier.object = skeletonObj
            modifier.use_bone_envelopes = False
            modifier.use_vertex_groups = True

            maximumInfluence = mesh.MaximumWeightInfluence()
            if maximumInfluence > 1:  # Slower path for complex weights
                weightBoneBuffer = mesh.VertexWeightBoneBuffer()
                weightValueBuffer = mesh.VertexWeightValueBuffer()

                for x in range(len(newMesh.vertices)):
                    for j in range(maximumInfluence):
                        index = j + (x * maximumInfluence)
                        value = weightValueBuffer[index]

                        if (value > 0.0):
                            boneGroups[weightBoneBuffer[index]].add(
                                (x,), value, "REPLACE")
            elif maximumInfluence > 0:  # Fast path for simple weighted meshes
                weightBoneBuffer = mesh.VertexWeightBoneBuffer()
                for x in range(len(newMesh.vertices)):
                    boneGroups[weightBoneBuffer[x]].add((x,), 1.0, "REPLACE")

        collection.objects.link(meshObj)

    # Relink the collection after the mesh is built
    bpy.context.view_layer.active_layer_collection.collection.children.link(
        collection)


def importRootNode(node, path):
    for child in node.ChildrenOfType(Model):
        importModelNode(child, path)
    # for child in node.ChildrenOfType(Animation):
    #     importAnimationNode(child, path)


def importCast(path):
    cast = Cast.load(path)

    for root in cast.Roots():
        importRootNode(root, path)


def load(self, context, filepath=""):
    importCast(filepath)

    bpy.context.view_layer.update()
    return True
