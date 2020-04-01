import bpy
import bmesh
import os
import array
import math
from mathutils import *
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
            "emissive": "Emissive",
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


def importSkeletonNode(name, skeleton):
    if skeleton is None:
        return None

    armature = bpy.data.armatures.new("Joints")
    armature.display_type = "STICK"

    skeletonObj = bpy.data.objects.new(name, armature)
    skeletonObj.show_in_front = True

    bpy.context.view_layer.active_layer_collection.collection.objects.link(
        skeletonObj)
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

    # Import skeleton for binds, materials for meshes
    skeletonObj = importSkeletonNode(modelName, model.Skeleton())
    materialArray = {key: value for (key, value) in (
        importMaterialNode(path, x) for x in model.Materials())}

    meshes = model.Meshes()
    for mesh in meshes:
        newMesh = bpy.data.meshes.new("polySurfaceMesh")
        blendMesh = bmesh.new()

        vertexColorLayer = blendMesh.loops.layers.color.new("color1")
        vertexWeightLayer = blendMesh.verts.layers.deform.new()
        vertexUVLayers = [blendMesh.loops.layers.uv.new(
            "map%d" % x) for x in range(mesh.UVLayerCount())]

        vertexPositions = mesh.VertexPositionBuffer()
        for x in range(0, len(vertexPositions), 3):
            blendMesh.verts.new(
                Vector((vertexPositions[x], vertexPositions[x + 1], vertexPositions[x + 2])))
        blendMesh.verts.ensure_lookup_table()

        faceLookupMap = [1, 2, 0]
        vertexNormalLayer = []

        vertexNormals = mesh.VertexNormalBuffer()
        vertexColors = mesh.VertexColorBuffer()
        vertexUVs = [mesh.VertexUVLayerBuffer(
            x) for x in range(mesh.UVLayerCount())]

        def vertexToFaceVertex(face):
            for x, loop in enumerate(face.loops):
                vertexIndex = faces[faceStart + faceLookupMap[x]]

                if vertexNormals is not None:
                    vertexNormalLayer.append((vertexNormals[vertexIndex * 3], vertexNormals[(
                        vertexIndex * 3) + 1], vertexNormals[(vertexIndex * 3) + 2]))

                for uvLayer in range(mesh.UVLayerCount()):
                    uv = Vector(
                        (vertexUVs[uvLayer][vertexIndex * 2], vertexUVs[uvLayer][(vertexIndex * 2) + 1]))
                    uv.y = 1.0 - uv.y

                    loop[vertexUVLayers[uvLayer]].uv = uv

                if vertexColors is not None:
                    loop[vertexColorLayer] = [
                        (vertexColors[vertexIndex] >> i & 0xff) / 255.0 for i in (24, 16, 8, 0)]

        faces = mesh.FaceBuffer()
        for faceStart in range(0, len(faces), 3):
            indices = [blendMesh.verts[faces[faceStart + faceLookupMap[0]]],
                       blendMesh.verts[faces[faceStart + faceLookupMap[1]]], blendMesh.verts[faces[faceStart + faceLookupMap[2]]]]

            try:
                newLoop = blendMesh.faces.new(indices)
            except RuntimeError:
                continue
            else:
                vertexToFaceVertex(newLoop)

        maximumInfluence = mesh.MaximumWeightInfluence()
        if maximumInfluence > 0:
            weightBoneBuffer = mesh.VertexWeightBoneBuffer()
            weightValueBuffer = mesh.VertexWeightValueBuffer()
            for x, vert in enumerate(blendMesh.verts):
                vert[vertexWeightLayer][weightBoneBuffer[x * maximumInfluence]
                                        ] = weightValueBuffer[x * maximumInfluence]

        blendMesh.to_mesh(newMesh)
        newMesh.create_normals_split()

        if len(vertexNormalLayer) > 0:
            for x, _loop in enumerate(newMesh.loops):
                newMesh.loops[x].normal = vertexNormalLayer[x]

        newMesh.validate(clean_customdata=False)
        clnors = array.array('f', [0.0] * (len(newMesh.loops) * 3))

        newMesh.loops.foreach_get("normal", clnors)
        newMesh.polygons.foreach_set(
            "use_smooth", [True] * len(newMesh.polygons))
        newMesh.normals_split_custom_set(tuple(zip(*(iter(clnors),) * 3)))
        newMesh.use_auto_smooth = True

        meshObj = bpy.data.objects.new("CastMesh", newMesh)
        bpy.context.view_layer.active_layer_collection.collection.objects.link(
            meshObj)
        bpy.context.view_layer.objects.active = meshObj

        meshMaterial = mesh.Material()
        if meshMaterial is not None:
            meshObj.data.materials.append(materialArray[meshMaterial.Name()])

        for bone in skeletonObj.pose.bones:
            meshObj.vertex_groups.new(name=bone.name)

        meshObj.parent = skeletonObj
        modifier = meshObj.modifiers.new('Armature Rig', 'ARMATURE')
        modifier.object = skeletonObj
        modifier.use_bone_envelopes = False
        modifier.use_vertex_groups = True


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
