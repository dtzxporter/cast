import bpy
import bmesh
import os
import array
import time
import math
from mathutils import *
from bpy_extras.io_utils import unpack_list
from .cast import Cast, Model, Animation, Curve, NotificationTrack, Mesh, Skeleton, Bone, Material, File

PRINCIPLED_BSDF = bpy.app.translations.pgettext_data("Principled BSDF")
SPECULAR_BSDF = bpy.app.translations.pgettext_data("ShaderNodeEeveeSpecular")


def utilityBuildPath(root, asset):
    if os.path.isabs(asset):
        return asset

    root = os.path.dirname(root)
    return os.path.join(root, asset)


def utilityAssignBSDFMaterialSlots(material, slots, path):
    # We will two shaders, one for metalness and one for specular
    if "metal" in slots:
        # Principled is default shader node
        shader = material.node_tree.nodes[PRINCIPLED_BSDF]
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
            material.node_tree.nodes[PRINCIPLED_BSDF])
        material_output = material.node_tree.nodes.get("Material Output")
        shader = material.node_tree.nodes.new(SPECULAR_BSDF)
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


def utilityGetOrCreateCurve(fcurves, poseBones, name, curve):
    if not name in poseBones:
        return None

    bone = poseBones[name]

    return fcurves.new(data_path="pose.bones[\"%s\"].%s" %
                       (bone.name, curve[0]), index=curve[1], action_group=bone.name)


def utilityImportQuatTrackData(tracks, poseBones, name, property, frameStart, frameBuffer, valueBuffer, mode):
    smallestFrame = 0
    largestFrame = 0

    if not name in poseBones:
        return (smallestFrame, largestFrame)

    bone = poseBones[name]

    if mode == "absolute" or mode == "relative" or mode is None:
        for i in range(0, len(valueBuffer), 4):
            frame = frameBuffer[int(i / 4)] + frameStart

            bone.matrix_basis.identity()

            if frame < smallestFrame:
                smallestFrame = frame
            if frame > largestFrame:
                largestFrame = frame

            # We have to convert the keyframe value to the delta of the rest position,
            # blender keyframes apply over the rest position in the scene.
            frameRotationMatrix = Quaternion(
                (valueBuffer[i + 3], valueBuffer[i], valueBuffer[i + 1], valueBuffer[i + 2])).to_matrix().to_3x3()

            if bone.parent is None:
                mat = frameRotationMatrix.to_4x4()
            else:
                mat = (bone.parent.matrix.to_3x3() @
                       frameRotationMatrix).to_4x4()

            bone.matrix = mat

            if tracks[0] is not None:
                tracks[0].keyframe_points.insert(frame,
                                                 value=bone.rotation_quaternion.x, options={'FAST'})
            if tracks[1] is not None:
                tracks[1].keyframe_points.insert(frame,
                                                 value=bone.rotation_quaternion.y, options={'FAST'})
            if tracks[2] is not None:
                tracks[2].keyframe_points.insert(frame,
                                                 value=bone.rotation_quaternion.z, options={'FAST'})
            if tracks[3] is not None:
                tracks[3].keyframe_points.insert(frame,
                                                 value=bone.rotation_quaternion.w, options={'FAST'})
    else:
        # I need to get some samples of these before attempting this again.
        raise Exception(
            "Additive animations are currently not supported in blender.")

    # Reset temporary matrices used to calculate the keyframe rotations.
    bone.matrix_basis.identity()

    for track in tracks:
        if track is not None:
            track.update()

    return (smallestFrame, largestFrame)


def utilityImportSingleTrackData(tracks, poseBones, name, property, frameStart, frameBuffer, valueBuffer, mode):
    smallestFrame = 0
    largestFrame = 0

    if tracks[0] is None:
        return (smallestFrame, largestFrame)

    if not name in poseBones:
        return (smallestFrame, largestFrame)

    bone = poseBones[name]

    # Translation properties are based on the scene value, so we have to compute the delta and key that
    # instead of the keyframe value. It also requires us to have the other components, hence splat.
    if property in ["tx", "ty", "tz"]:
        reset = bone.matrix.to_translation()

        if bone.parent is None:
            splat = Vector((0, 0, 0))
        else:
            splat = (bone.parent.matrix.inverted() @ bone.matrix).translation
        splatIndex = tracks[0].array_index

        for i, x in enumerate(frameBuffer):
            frame = x + frameStart

            bone.matrix_basis.identity()
            bone.matrix.translation = reset

            if frame < smallestFrame:
                smallestFrame = frame
            if frame > largestFrame:
                largestFrame = frame

            splat[splatIndex] = valueBuffer[i]

            if mode == "absolute" or mode is None:
                if bone.parent is None:
                    bone.matrix_basis.translation = splat
                else:
                    bone.matrix.translation = bone.parent.matrix @ splat
            elif mode == "relative":
                bone.matrix_basis.translation = bone.bone.matrix @ splat
            else:
                raise Exception(
                    "Additive animations are currently not supported in blender.")

            tracks[0].keyframe_points.insert(
                frame, value=bone.location[splatIndex], options={'FAST'})
    # Scale isn't based on the scene value, it's per-bone and defaults to 1.0.
    elif property in ["sx", "sy", "sz"]:
        for i, x in enumerate(frameBuffer):
            frame = x + frameStart

            if frame < smallestFrame:
                smallestFrame = frame
            if frame > largestFrame:
                largestFrame = frame

            tracks[0].keyframe_points.insert(
                frame, value=valueBuffer[i], options={'FAST'})
    else:
        raise Exception("Unsupported curve property: %s" % (property))

    # Reset temporary matrices used to calculate the keyframes.
    bone.matrix_basis.identity()

    tracks[0].update()

    return (smallestFrame, largestFrame)


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
        rotation = Quaternion(
            (tempQuat[3], tempQuat[0], tempQuat[1], tempQuat[2]))

        translation = Vector(bone.LocalPosition())

        if bone.Scale() is not None:
            scale = Vector(bone.Scale())
        else:
            scale = None

        matrices[bone.Name()] = Matrix.LocRotScale(
            translation, rotation, scale)
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


def importCurveNode(node, fcurves, poseBones, path, startFrame):
    propertySwitcher = {
        "rq": [("rotation_quaternion", 1), ("rotation_quaternion", 2), ("rotation_quaternion", 3), ("rotation_quaternion", 0)],
        "rx": [("rotation_euler", 0)],
        "ry": [("rotation_euler", 1)],
        "rz": [("rotation_euler", 2)],
        "tx": [("location", 0)],
        "ty": [("location", 1)],
        "tz": [("location", 2)],
        "sx": [("scale", 0)],
        "sy": [("scale", 1)],
        "sz": [("scale", 2)],
    }
    trackSwitcher = {
        "rq": utilityImportQuatTrackData,
        "rx": utilityImportSingleTrackData,
        "ry": utilityImportSingleTrackData,
        "rz": utilityImportSingleTrackData,
        "tx": utilityImportSingleTrackData,
        "ty": utilityImportSingleTrackData,
        "tz": utilityImportSingleTrackData,
        "sx": utilityImportSingleTrackData,
        "sy": utilityImportSingleTrackData,
        "sz": utilityImportSingleTrackData,
    }

    nodeName = node.NodeName()
    propertyName = node.KeyPropertyName()

    if not propertyName in propertySwitcher:
        return (0, 0)

    keyFrameBuffer = node.KeyFrameBuffer()
    keyValueBuffer = node.KeyValueBuffer()

    tracks = [utilityGetOrCreateCurve(
        fcurves, poseBones, nodeName, x) for x in propertySwitcher[propertyName]]

    return trackSwitcher[propertyName](tracks, poseBones, nodeName, propertyName, startFrame, keyFrameBuffer, keyValueBuffer, node.Mode())


def importNotificationTrackNode(node, action):
    frameBuffer = node.KeyFrameBuffer()

    for x in frameBuffer:
        notetrack = action.pose_markers.new(node.Name())
        notetrack.frame = x


def importAnimationNode(node, path):
    # The object which the animation node should be applied to.
    selectedObject = bpy.context.object
    # Check that the selected object is an 'ARMATURE'.
    if selectedObject is None or selectedObject.type != 'ARMATURE':
        raise Exception(
            "You must select an armature to apply the animation to.")

    # Extract the name of this anim from the path
    animName = os.path.splitext(os.path.basename(path))[0]

    try:
        selectedObject.animation_data.action
    except:
        selectedObject.animation_data_create()

    # Ensure that all pose bones have rotation quaternion values.
    for bone in selectedObject.pose.bones.data.bones:
        bone.rotation_mode = 'QUATERNION'

    bpy.ops.object.mode_set(mode='POSE')

    action = bpy.data.actions.new(animName)
    selectedObject.animation_data.action = action
    selectedObject.animation_data.action.use_fake_user = True

    scene = bpy.context.scene
    scene.render.fps = int(node.Framerate())

    # We need to determine the proper time to import the curves, for example
    # the user may want to import at the current scene time, and that would require
    # fetching once here, then passing to the curve importer.
    wantedSmallestFrame = 0
    wantedLargestFrame = 1

    curves = node.Curves()

    # Create a list of pose bones that match the curves..
    poseBones = {}

    for x in curves:
        for bone in selectedObject.pose.bones:
            if x.NodeName().lower() == bone.name.lower():
                poseBones[x.NodeName()] = bone

    for x in curves:
        (smallestFrame, largestFrame) = importCurveNode(
            x, action.fcurves, poseBones, path, 0)
        if smallestFrame < wantedSmallestFrame:
            wantedSmallestFrame = smallestFrame
        if largestFrame > wantedLargestFrame:
            wantedLargestFrame = largestFrame

    for x in node.Notifications():
        (smallestFrame, largestFrame) = importNotificationTrackNode(x, action)
        if smallestFrame < wantedSmallestFrame:
            wantedSmallestFrame = smallestFrame
        if largestFrame > wantedLargestFrame:
            wantedLargestFrame = largestFrame

    # Set the animation segment
    scene.frame_current = 0
    scene.frame_start = wantedSmallestFrame
    scene.frame_end = wantedLargestFrame

    bpy.context.evaluated_depsgraph_get().update()
    bpy.ops.object.mode_set(mode='POSE')


def importRootNode(node, path):
    for child in node.ChildrenOfType(Model):
        importModelNode(child, path)
    for child in node.ChildrenOfType(Animation):
        importAnimationNode(child, path)


def importCast(path):
    cast = Cast.load(path)

    for root in cast.Roots():
        importRootNode(root, path)


def load(self, context, filepath=""):
    importCast(filepath)

    bpy.context.view_layer.update()
