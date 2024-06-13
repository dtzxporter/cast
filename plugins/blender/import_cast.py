import bpy
import os
import array
import sys

from mathutils import *
from bpy_extras.io_utils import unpack_list
from .cast import Cast, CastColor, Model, Animation, Instance, File

PRINCIPLED_BSDF = bpy.app.translations.pgettext_data("Principled BSDF")
SPECULAR_BSDF = bpy.app.translations.pgettext_data("ShaderNodeEeveeSpecular")
BLENDER_VERSION = bpy.app.version


def utilityBuildPath(root, asset):
    if os.path.isabs(asset):
        return asset

    root = os.path.dirname(root)
    return os.path.join(root, asset)


def utilityStashCurveComponent(component, curve, name, index):
    if name in component:
        component[name][index] = curve
    else:
        value = [None] * 3
        value[index] = curve
        component[name] = value


def utilityIsVersionAtLeast(major, minor):
    if BLENDER_VERSION[0] > major:
        return True
    elif BLENDER_VERSION[0] == major and BLENDER_VERSION[1] >= minor:
        return True
    return False


def utilityClearKeyframePoints(fcurve):
    if utilityIsVersionAtLeast(4, 0):
        return fcurve.keyframe_points.clear()

    for keyframe in reversed(fcurve.keyframe_points.values()):
        fcurve.keyframe_points.remove(keyframe)


def utilityAssignBSDFMaterialSlots(material, slots, path):
    # We will two shaders, one for metalness and one for specular
    if "metal" in slots:
        # Principled is default shader node
        shader = material.node_tree.nodes[PRINCIPLED_BSDF]
        switcher = {
            "albedo": "Base Color",
            "diffuse": "Base Color",
            "specular": "Specular IOR Level" if utilityIsVersionAtLeast(4, 0) else "Specular",
            "metal": "Metallic",
            "roughness": "Roughness",
            "gloss": "Roughness",
            "normal": "Normal",
            "emissive": "Emission Color" if utilityIsVersionAtLeast(4, 0) else "Emission",
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
            "gloss": "Roughness",
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

        if slot == "normal":
            if texture.image is not None:
                texture.image.colorspace_settings.name = "Non-Color"

            normalMap = material.node_tree.nodes.new("ShaderNodeNormalMap")
            material.node_tree.links.new(
                normalMap.inputs["Color"], texture.outputs["Color"])
            material.node_tree.links.new(
                shader.inputs[switcher[slot]], normalMap.outputs["Normal"])
        elif slot == "gloss":
            invert = material.node_tree.nodes.new("ShaderNodeInvert")
            material.node_tree.links.new(
                invert.inputs["Color"], texture.outputs["Color"])
            material.node_tree.links.new(
                shader.inputs[switcher[slot]], invert.outputs["Color"])
        else:
            material.node_tree.links.new(
                shader.inputs[switcher[slot]], texture.outputs["Color"])


def utilityGetOrCreateCurve(fcurves, poseBones, name, curve):
    if not name in poseBones:
        return None

    bone = poseBones[name]

    return fcurves.find(data_path="pose.bones[\"%s\"].%s" %
                        (bone.name, curve[0]), index=curve[1]) or fcurves.new(data_path="pose.bones[\"%s\"].%s" %
                                                                              (bone.name, curve[0]), index=curve[1], action_group=bone.name)


def utilityResolveCurveModeOverride(bone, mode, overrides, isTranslate=False, isRotate=False, isScale=False):
    if not overrides:
        return mode

    for parent in bone.parent_recursive:
        for override in overrides:
            if isTranslate and not override.OverrideTranslationCurves():
                continue
            elif isRotate and not override.OverrideRotationCurves():
                continue
            elif isScale and not override.OverrideScaleCurves():
                continue

            if parent.name == override.NodeName():
                return override.Mode()


def utilityGetBindposeScale(poseBone):
    bindPoseScale = Matrix.LocRotScale(None, None, Vector((1.0, 1.0, 1.0)))

    if poseBone is not None:
        bindPoseScale = bindPoseScale @ Matrix.LocRotScale(None, None, Vector(
            getattr(poseBone, "cast_bind_pose_scale", (1.0, 1.0, 1.0))))

    return bindPoseScale


def importSkeletonConstraintNode(self, skeleton, skeletonObj, poses):
    if skeleton is None:
        return

    for constraint in skeleton.Constraints():
        constraintBone = poses[constraint.ConstraintBone().Name()]
        targetBone = poses[constraint.TargetBone().Name()]

        type = constraint.ConstraintType()

        if type == "pt":
            ct = constraintBone.constraints.new("COPY_LOCATION")
            ct.use_offset = constraint.MaintainOffset()
        elif type == "or":
            ct = constraintBone.constraints.new("COPY_ROTATION")
            if constraint.MaintainOffset():
                ct.mix_mode = 'OFFSET'
        elif type == "sc":
            ct = constraintBone.constraints.new("COPY_SCALE")
            ct.use_offset = constraint.MaintainOffset()
        else:
            continue

        ct.owner_space = 'LOCAL'
        ct.target_space = 'LOCAL'

        if constraint.Name() is not None:
            ct.name = constraint.Name()

        ct.use_x = not constraint.SkipX()
        ct.use_y = not constraint.SkipY()
        ct.use_z = not constraint.SkipZ()

        ct.target = targetBone.id_data
        ct.subtarget = targetBone.name

        # We have to configure this after setting a target because the enum
        # option isn't available unless orient is supportd by the target itself.
        if type == "or":
            ct.target_space = 'LOCAL_OWNER_ORIENT'


def importSkeletonIKNode(self, skeleton, skeletonObj, poses):
    if skeleton is None:
        return

    for handle in skeleton.IKHandles():
        startBone = poses[handle.EndBone().Name()]
        endBone = poses[handle.StartBone().Name()]

        ik = startBone.constraints.new("IK")

        if handle.Name() is not None:
            ik.name = handle.Name()

        # We need to create the ik constraint for the start bone, and set the chain length
        # so that it makes it to end end bone (Walk the parent tree and count.)
        ik.chain_count = 0
        ik.use_tail = True

        bone = startBone

        while True:
            ik.chain_count += 1
            bone = bone.parent

            if bone is None:
                break
            elif bone.name == endBone.name:
                ik.chain_count += 1
                break

        targetBone = handle.TargetBone()

        if targetBone is not None:
            target = poses[targetBone.Name()]

            ik.target = target.id_data
            ik.subtarget = target.name
            ik.use_location = True

            if handle.UseTargetRotation():
                ik.use_rotation = True

        poleVectorBone = handle.PoleVectorBone()

        if poleVectorBone is not None:
            poleVector = poses[poleVectorBone.Name()]

            ik.pole_target = target.id_data
            ik.pole_subtarget = poleVector.name

        poleBone = handle.PoleBone()

        if poleBone is not None:
            # Warn until we figure out how to emulate this effectively.
            self.report(
                {"WARNING"}, "Unable to setup %s fully due to blender not supporting pole (twist) bones." % ik.name)


def importSkeletonNode(name, skeleton, collection):
    if skeleton is None:
        return (None, None)

    armature = bpy.data.armatures.new("Joints")
    armature.display_type = "STICK"

    skeletonObj = bpy.data.objects.new(name, armature)
    skeletonObj.show_in_front = True

    collection.objects.link(skeletonObj)
    bpy.context.view_layer.objects.active = skeletonObj
    bpy.ops.object.mode_set(mode='EDIT')

    bones = skeleton.Bones()
    handles = [None] * len(bones)
    poses = {}
    matrices = {}
    scales = {}

    for i, bone in enumerate(bones):
        newBone = armature.edit_bones.new(bone.Name())
        newBone.tail = 0, 0.0025, 0  # I am sorry but blender sucks

        tempQuat = bone.LocalRotation()  # Also sucks, WXYZ? => XYZW master race
        rotation = Quaternion(
            (tempQuat[3], tempQuat[0], tempQuat[1], tempQuat[2]))

        translation = Vector(bone.LocalPosition())

        scale = Vector(bone.Scale() or (1.0, 1.0, 1.0))

        matrices[newBone.name] = Matrix.LocRotScale(
            translation, rotation, None)
        scales[newBone.name] = scale
        handles[i] = newBone

    for i, bone in enumerate(bones):
        if bone.ParentIndex() > -1:
            handles[i].parent = handles[bone.ParentIndex()]

    bpy.context.view_layer.objects.active = skeletonObj
    bpy.ops.object.mode_set(mode='POSE')

    for bone in skeletonObj.pose.bones:
        bone.cast_bind_pose_scale = scales[bone.name]

        bone.matrix_basis.identity()
        bone.matrix = matrices[bone.name]

        poses[bone.name] = bone

    bpy.ops.pose.armature_apply()
    return (skeletonObj, poses)


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


def importModelNode(self, model, path):
    # Extract the name of this model from the path
    modelName = model.Name() or os.path.splitext(os.path.basename(path))[0]

    # Create a collection for our objects
    collection = bpy.data.collections.new(modelName)
    bpy.context.scene.collection.children.link(collection)

    # Import skeleton for binds, materials for meshes
    (skeletonObj, poses) = importSkeletonNode(
        modelName, model.Skeleton(), collection)
    materialArray = {key: value for (key, value) in (
        importMaterialNode(path, x) for x in model.Materials())}

    # For mesh import performance, unlink from scene until we're done
    bpy.context.scene.collection.children.unlink(collection)

    meshes = model.Meshes()
    meshHandles = {}

    for mesh in meshes:
        newMesh = bpy.data.meshes.new("polySurfaceMesh")
        meshObj = bpy.data.objects.new(mesh.Name() or "CastMesh", newMesh)

        # Store for later creating blend shapes if necessary.
        meshHandles[mesh.Hash()] = (meshObj, newMesh)

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
            newMesh.vertex_colors[0].data.foreach_set(
                "color", unpack_list([CastColor.fromInteger(vertexColors[x]) for x in faces]))

        vertexNormals = mesh.VertexNormalBuffer()
        if vertexNormals is not None:
            if utilityIsVersionAtLeast(4, 1):
                newMesh.validate(clean_customdata=False)

                newMesh.normals_split_custom_set_from_vertices(
                    tuple(zip(*(iter(vertexNormals),) * 3)))
            else:
                newMesh.create_normals_split()
                newMesh.loops.foreach_set("normal", unpack_list(
                    [(vertexNormals[x * 3], vertexNormals[(x * 3) + 1], vertexNormals[(x * 3) + 2]) for x in faces]))

                newMesh.validate(clean_customdata=False)
                clnors = array.array('f', [0.0] * (len(newMesh.loops) * 3))
                newMesh.loops.foreach_get("normal", clnors)

                newMesh.polygons.foreach_set(
                    "use_smooth", [True] * len(newMesh.polygons))

                newMesh.normals_split_custom_set(
                    tuple(zip(*(iter(clnors),) * 3)))
                newMesh.use_auto_smooth = True
        else:
            newMesh.validate(clean_customdata=False)

        meshMaterial = mesh.Material()
        if meshMaterial is not None:
            newMesh.materials.append(materialArray[meshMaterial.Name()])

        if skeletonObj is not None and self.import_skin:
            boneGroups = []
            for bone in model.Skeleton().Bones():
                boneGroups.append(meshObj.vertex_groups.new(name=bone.Name()))

            meshObj.parent = skeletonObj
            modifier = meshObj.modifiers.new('Armature Rig', 'ARMATURE')
            modifier.object = skeletonObj
            modifier.use_bone_envelopes = False
            modifier.use_vertex_groups = True

            skinningMethod = mesh.SkinningMethod()

            if skinningMethod == "linear":
                modifier.use_deform_preserve_volume = False
            elif skinningMethod == "quaternion":
                modifier.use_deform_preserve_volume = True

            maximumInfluence = mesh.MaximumWeightInfluence()
            if maximumInfluence > 1:  # Slower path for complex weights
                weightBoneBuffer = mesh.VertexWeightBoneBuffer()
                weightValueBuffer = mesh.VertexWeightValueBuffer()

                for x in range(len(newMesh.vertices)):
                    for j in range(maximumInfluence):
                        index = j + (x * maximumInfluence)

                        boneGroups[weightBoneBuffer[index]].add(
                            (x,), weightValueBuffer[index], "ADD")
            elif maximumInfluence > 0:  # Fast path for simple weighted meshes
                weightBoneBuffer = mesh.VertexWeightBoneBuffer()
                for x in range(len(newMesh.vertices)):
                    boneGroups[weightBoneBuffer[x]].add((x,), 1.0, "REPLACE")

        collection.objects.link(meshObj)

    blendShapes = model.BlendShapes()

    for blendShape in blendShapes:
        # We need one base shape and 1+ target shapes
        if blendShape.BaseShape() is None or blendShape.BaseShape().Hash() not in meshHandles:
            continue
        if blendShape.TargetShapes() is None:
            continue

        baseShape = meshHandles[blendShape.BaseShape().Hash()]
        targetShapes = [meshHandles[x.Hash()]
                        for x in blendShape.TargetShapes() if x.Hash() in meshHandles]
        targetWeightScales = blendShape.TargetWeightScales() or []
        targetWeightScaleCount = len(targetWeightScales)

        basis = baseShape[0].shape_key_add(name="Basis")
        basis.interpolation = "KEY_LINEAR"

        for i, shape in enumerate(targetShapes):
            if len(basis.data) != len(shape[1].vertices):
                self.report(
                    {'WARNING'}, "Unable to create blend shape \"%s\" with a different number of vertices." % shape[0].name)
                continue

            newShape = baseShape[0].shape_key_add(
                name=shape[0].name, from_mix=False)
            newShape.interpolation = "KEY_LINEAR"

            if i < targetWeightScaleCount:
                if targetWeightScales[i] > 10.0:
                    self.report(
                        {'WARNING'}, "Clamping blend shape \"%s\" scale to 10.0." % shape[0].name)
                newShape.slider_max = min(10.0, targetWeightScales[i])

            for v, value in enumerate(shape[1].vertices):
                newShape.data[v].co = value.co

            shape[0].hide_viewport = True

    # Import any ik handles now that the meshes are bound because the constraints may effect the bind pose.
    if self.import_ik:
        importSkeletonIKNode(self, model.Skeleton(), skeletonObj, poses)

    # Import any constraints after ik.
    if self.import_constraints:
        importSkeletonConstraintNode(
            self, model.Skeleton(), skeletonObj, poses)

    # Relink the collection after the mesh is built
    bpy.context.view_layer.active_layer_collection.collection.children.link(
        collection)


def importRotCurveNode(node, nodeName, fcurves, poseBones, path, startFrame, overrides):
    smallestFrame = sys.maxsize
    largestFrame = 0

    if not nodeName in poseBones:
        return (smallestFrame, largestFrame)

    bone = poseBones[nodeName]
    mode = utilityResolveCurveModeOverride(
        bone, node.Mode(), overrides, isRotate=True)

    tracks = [utilityGetOrCreateCurve(fcurves, poseBones, nodeName, x) for x in [
        ("rotation_quaternion", 0), ("rotation_quaternion", 1), ("rotation_quaternion", 2), ("rotation_quaternion", 3)]]

    keyFrameBuffer = node.KeyFrameBuffer()
    keyValueBuffer = node.KeyValueBuffer()

    # https://devtalk.blender.org/t/quaternion-interpolation/15883
    # Blender interpolates rotations as-if they are separate components.
    # This logic is of course, broken, so we must interpolate ourselves.
    rotations = []
    keyframes = []

    if len(keyFrameBuffer) > 0:
        minFrame = min(keyFrameBuffer)
        maxFrame = max(keyFrameBuffer)

        existing = {}

        for i in range(0, len(keyValueBuffer), 4):
            existing[keyFrameBuffer[int(i / 4)]] = Quaternion(
                (keyValueBuffer[i + 3], keyValueBuffer[i], keyValueBuffer[i + 1], keyValueBuffer[i + 2]))

        lastKeyframeValue = None
        lastKeyframeFrame = None
        nextKeyframeValue = None
        nextKeyframeFrame = None

        for frame in range(minFrame, maxFrame + 1):
            if frame in existing:
                value = existing[frame]

                lastKeyframeValue = value
                lastKeyframeFrame = frame

                rotations.append(value)
                keyframes.append(frame)
                continue

            if lastKeyframeValue is None or lastKeyframeFrame is None:
                continue

            if nextKeyframeFrame is None or nextKeyframeFrame <= frame:
                for nextFrame in range(frame + 1, maxFrame + 1):
                    if nextFrame in existing:
                        nextKeyframeValue = existing[nextFrame]
                        nextKeyframeFrame = nextFrame
                        break

            if nextKeyframeFrame is not None and nextKeyframeFrame > frame:
                rotations.append(lastKeyframeValue.slerp(
                    nextKeyframeValue, (frame - lastKeyframeFrame) / (nextKeyframeFrame - lastKeyframeFrame)))
                keyframes.append(frame)
                continue

    # Rotation keyframes in blender are independent from other data.
    for i in range(0, len(keyframes)):
        rotation = rotations[i].to_matrix().to_3x3()

        frame = keyframes[i] + startFrame

        smallestFrame = min(frame, smallestFrame)
        largestFrame = max(frame, largestFrame)

        if mode == "absolute" or mode is None:
            bone.matrix_basis.identity()

            if bone.parent is not None:
                bone.matrix = (bone.parent.matrix.to_3x3() @ rotation).to_4x4()
            else:
                bone.matrix = rotation.to_4x4()

            for axis, track in enumerate(tracks):
                track.keyframe_points.insert(
                    frame, value=bone.rotation_quaternion[axis], options={'FAST'})
        elif mode == "relative":
            rotation = rotation.to_quaternion()

            for axis, track in enumerate(tracks):
                track.keyframe_points.insert(
                    frame, value=rotation[axis], options={'FAST'})
        else:
            # I need to get some samples of these before attempting this again.
            raise Exception(
                "Additive animations are currently not supported in blender.")

    # Reset temporary matrices used to calculate the keyframe locations.
    bone.matrix_basis.identity()

    for track in tracks:
        track.update()

    return (smallestFrame, largestFrame)


def importScaleCurveNodes(nodes, nodeName, fcurves, poseBones, path, startFrame, overrides):
    smallestFrame = sys.maxsize
    largestFrame = 0

    if not nodeName in poseBones:
        return (smallestFrame, largestFrame)

    bone = poseBones[nodeName]
    mode = None

    for node in nodes:
        if node is not None:
            mode = node.Mode()

    mode = utilityResolveCurveModeOverride(bone, mode, overrides, isScale=True)

    tracks = [utilityGetOrCreateCurve(fcurves, poseBones, nodeName, x) for x in [
        ("scale", 0), ("scale", 1), ("scale", 2)]]

    # This works around the issue where EditBone.matrix destroys the scale which means that
    # a model which has an non-1.0 scale when the bind pose is applied will not scale correctly.
    bindPoseInvMatrix = utilityGetBindposeScale(bone).inverted()

    # Scale keyframes are independant from other data.
    for axis, node in enumerate(nodes):
        if node is None:
            continue

        keyFrameBuffer = node.KeyFrameBuffer()
        keyValueBuffer = node.KeyValueBuffer()

        scale = Vector((1.0, 1.0, 1.0))

        for i, frame in enumerate(keyFrameBuffer):
            if mode == "absolute" or mode is None:
                scale[axis] = keyValueBuffer[i]

                value = (bindPoseInvMatrix @
                         Matrix.LocRotScale(None, None, scale)).to_scale()

                tracks[axis].keyframe_points.insert(
                    frame, value=value[axis], options={'FAST'})
            elif mode == "relative":
                tracks[axis].keyframe_points.insert(
                    frame, value=keyValueBuffer[i], options={'FAST'})
            else:
                # I need to get some samples of these before attempting this again.
                raise Exception(
                    "Additive animations are currently not supported in blender.")

    # Reset temporary matrices used to calculate the keyframe locations.
    bone.matrix_basis.identity()

    for track in tracks:
        track.update()

    return (smallestFrame, largestFrame)


def importLocCurveNodes(nodes, nodeName, fcurves, poseBones, path, startFrame, overrides):
    smallestFrame = sys.maxsize
    largestFrame = 0

    if not nodeName in poseBones:
        return (smallestFrame, largestFrame)

    bone = poseBones[nodeName]
    mode = None

    for node in nodes:
        if node is not None:
            mode = node.Mode()

    mode = utilityResolveCurveModeOverride(
        bone, mode, overrides, isTranslate=True)

    tracks = [utilityGetOrCreateCurve(fcurves, poseBones, nodeName, x) for x in [
        ("location", 0), ("location", 1), ("location", 2)]]

    lastFrame = 0

    # Location keyframes in blender are post-rotation, and as such, require all components in order to animate properly.
    for axis, node in enumerate(nodes):
        if node is None:
            if bone.parent is None:
                tracks[axis].keyframe_points.insert(
                    0, value=bone.matrix.translation[axis], options={'FAST'})
            else:
                tracks[axis].keyframe_points.insert(
                    0, value=(bone.parent.matrix.inverted() @ bone.matrix).translation[axis], options={'FAST'})
        else:
            keyFrameBuffer = node.KeyFrameBuffer()
            keyValueBuffer = node.KeyValueBuffer()

            for i, frame in enumerate(keyFrameBuffer):
                tracks[axis].keyframe_points.insert(
                    frame, value=keyValueBuffer[i], options={'FAST'})
                lastFrame = max(lastFrame, frame)

    keyFrameBuffer = []
    keyValueBuffer = []

    # Now, we need to bake the curves into sampled keyframes that collectively animate the transform.
    for frame in range(0, lastFrame + 1):
        keyFrameBuffer.append(frame)
        keyValueBuffer.append((tracks[0].evaluate(
            frame), tracks[1].evaluate(frame), tracks[2].evaluate(frame)))

    # Now, we need to actually generate keyframes for each of the tracks based on the mode.
    for track in tracks:
        utilityClearKeyframePoints(track)

    for i, frame in enumerate(keyFrameBuffer):
        offset = Vector(keyValueBuffer[i])

        frame = frame + startFrame

        smallestFrame = min(frame, smallestFrame)
        largestFrame = max(frame, largestFrame)

        if mode == "absolute" or mode is None:
            if bone.parent is not None:
                bone.matrix.translation = bone.parent.matrix @ offset
            else:
                bone.matrix.translation = offset
        elif mode == "relative":
            bone.matrix_basis.translation = bone.bone.matrix.inverted() @ offset
        else:
            # I need to get some samples of these before attempting this again.
            raise Exception(
                "Additive animations are currently not supported in blender.")

        for axis, track in enumerate(tracks):
            track.keyframe_points.insert(
                frame, value=bone.location[axis], options={'FAST'})

    # Reset temporary matrices used to calculate the keyframe locations.
    bone.matrix_basis.identity()

    for track in tracks:
        track.update()

    return (smallestFrame, largestFrame)


def importNotificationTrackNode(node, action, frameStart):
    smallestFrame = sys.maxsize
    largestFrame = 0

    frameBuffer = node.KeyFrameBuffer()

    for frame in frameBuffer:
        frame = frame + frameStart

        notetrack = action.pose_markers.new(node.Name())
        notetrack.frame = frame

        smallestFrame = min(frame, smallestFrame)
        largestFrame = max(frame, largestFrame)

    return (smallestFrame, largestFrame)


def importAnimationNode(self, node, path):
    # The object which the animation node should be applied to.
    selectedObject = bpy.context.object
    # Check that the selected object is an 'ARMATURE'.
    if selectedObject is None or selectedObject.type != 'ARMATURE':
        raise Exception(
            "You must select an armature to apply the animation to.")

    # Extract the name of this anim from the path.
    animName = node.Name() or os.path.splitext(os.path.basename(path))[0]

    try:
        selectedObject.animation_data.action
    except:
        selectedObject.animation_data_create()

    # Ensure that all pose bones have rotation quaternion values.
    for bone in selectedObject.pose.bones.data.bones:
        bone.rotation_mode = 'QUATERNION'

    bpy.ops.object.mode_set(mode='POSE')

    if self.import_reset:
        action = bpy.data.actions.new(animName)
    else:
        action = selectedObject.animation_data.action or bpy.data.actions.new(
            animName)

    selectedObject.animation_data.action = action
    selectedObject.animation_data.action.use_fake_user = True

    scene = bpy.context.scene
    scene.render.fps = int(node.Framerate())

    # We need to determine the proper time to import the curves, for example
    # the user may want to import at the current scene time, and that would require
    # fetching once here, then passing to the curve importer.
    wantedSmallestFrame = sys.maxsize
    wantedLargestFrame = 1

    if self.import_time:
        startFrame = scene.frame_current
    else:
        startFrame = 0

    curves = node.Curves()
    curveModeOverrides = node.CurveModeOverrides()

    # Create a list of pose bones that match the curves..
    poseBones = {}

    for x in curves:
        for bone in selectedObject.pose.bones:
            if x.NodeName().lower() == bone.name.lower():
                poseBones[x.NodeName()] = bone

    # Create a list of the separate location and scale curves because their curves are separate.
    locCurves = {}
    scaleCurves = {}

    for x in curves:
        nodeName = x.NodeName()
        property = x.KeyPropertyName()

        if property == "rq":
            (smallestFrame, largestFrame) = importRotCurveNode(
                x, nodeName, action.fcurves, poseBones, path, startFrame, curveModeOverrides)
            wantedSmallestFrame = min(smallestFrame, wantedSmallestFrame)
            wantedLargestFrame = max(largestFrame, wantedLargestFrame)
        elif property == "tx":
            utilityStashCurveComponent(locCurves, x, nodeName, 0)
        elif property == "ty":
            utilityStashCurveComponent(locCurves, x, nodeName, 1)
        elif property == "tz":
            utilityStashCurveComponent(locCurves, x, nodeName, 2)
        elif property == "sx":
            utilityStashCurveComponent(scaleCurves, x, nodeName, 0)
        elif property == "sy":
            utilityStashCurveComponent(scaleCurves, x, nodeName, 1)
        elif property == "sz":
            utilityStashCurveComponent(scaleCurves, x, nodeName, 2)

    for nodeName, x in locCurves.items():
        (smallestFrame, largestFrame) = importLocCurveNodes(
            x, nodeName, action.fcurves, poseBones, path, startFrame, curveModeOverrides)
        wantedSmallestFrame = min(smallestFrame, wantedSmallestFrame)
        wantedLargestFrame = max(largestFrame, wantedLargestFrame)

    for nodeName, x in scaleCurves.items():
        (smallestFrame,  largestFrame) = importScaleCurveNodes(
            x, nodeName, action.fcurves, poseBones, path, startFrame, curveModeOverrides)
        wantedSmallestFrame = min(smallestFrame, wantedSmallestFrame)
        wantedLargestFrame = max(largestFrame, wantedLargestFrame)

    for x in node.Notifications():
        (smallestFrame, largestFrame) = importNotificationTrackNode(
            x, action, startFrame)
        wantedSmallestFrame = min(smallestFrame, wantedSmallestFrame)
        wantedLargestFrame = max(largestFrame, wantedLargestFrame)

    # Set the animation segment
    if wantedSmallestFrame == sys.maxsize:
        wantedSmallestFrame = 0

    scene.frame_start = wantedSmallestFrame
    scene.frame_end = wantedLargestFrame
    scene.frame_current = wantedSmallestFrame

    bpy.context.evaluated_depsgraph_get().update()
    bpy.ops.object.mode_set(mode='POSE')


def importInstanceNodes(self, nodes, context, path):
    rootPath = context.scene.cast_properties.import_scenes_path

    if len(rootPath) == 0:
        raise Exception("Unable to import instances without a root directory!")

    uniqueInstances = {}

    for instance in nodes:
        refs = os.path.join(rootPath, instance.ReferenceFile().Path())

        if refs in uniqueInstances:
            uniqueInstances[refs].append(instance)
        else:
            uniqueInstances[refs] = [instance]

    name = os.path.splitext(os.path.basename(path))[0]

    # Used to contain the original imported scene, will be set to hidden once completed.
    baseGroup = bpy.data.collections.new("%s_scenes" % name)
    # Used to contain every instance.
    instanceGroup = bpy.data.collections.new("%s_instances" % name)

    for instancePath, instances in uniqueInstances.items():
        try:
            bpy.ops.import_scene.cast(filepath=instancePath)
        except:
            self.report(
                {'WARNING'}, "Instance: %s failed to import or not found, skipping..." % instancePath)
            continue

        base = bpy.context.view_layer.active_layer_collection.collection.children[-1]
        bpy.context.view_layer.active_layer_collection.collection.children.unlink(
            base)

        baseGroup.children.link(base)

        for instance in instances:
            newInstance = bpy.data.objects.new(instance.Name(), None)
            newInstance.instance_type = 'COLLECTION'
            newInstance.instance_collection = base

            position = instance.Position()
            rotation = instance.Rotation()
            scale = instance.Scale()

            newInstance.location = Vector(position)
            newInstance.rotation_mode = 'QUATERNION'
            newInstance.rotation_quaternion = Quaternion(
                (rotation[3], rotation[0], rotation[1], rotation[2]))
            newInstance.scale = Vector(scale)

            instanceGroup.objects.link(newInstance)

    baseGroup.hide_viewport = True

    # Link the groups to the scene at the end for performance.
    bpy.context.view_layer.active_layer_collection.collection.children.link(
        baseGroup)
    bpy.context.view_layer.active_layer_collection.collection.children.link(
        instanceGroup)


def importCast(self, context, path):
    cast = Cast.load(path)

    instances = []

    for root in cast.Roots():
        for child in root.ChildrenOfType(Model):
            importModelNode(self, child, path)
        for child in root.ChildrenOfType(Animation):
            importAnimationNode(self, child, path)
        for child in root.ChildrenOfType(Instance):
            instances.append(child)

    if len(instances) > 0:
        importInstanceNodes(self, instances, context, path)


def load(self, context, filepath=""):
    importCast(self, context, filepath)

    bpy.context.view_layer.update()
