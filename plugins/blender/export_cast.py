import bpy
import bpy_types
import bmesh
import math
import os

from bpy_extras.wm_utils.progress_report import ProgressReport
from mathutils import *
from .cast import Cast, CastColor

# Minimum weight value to be considered.
WEIGHT_THRESHOLD = 0.000001


def utilityResolveObjectTarget(objects, path):
    for object in objects:
        try:
            return (object, object.path_resolve(path, False))
        except:
            continue

    return None


def utilityGetSimpleKeyValue(object, property):
    if property == "location":
        if object.parent is not None:
            return object.parent.matrix.inverted() @ object.matrix.translation
        else:
            return object.matrix_basis.translation
    elif property == "scale":
        return object.scale
    return None


def utilityGetQuatKeyValue(object):
    if object.parent is not None:
        return (object.parent.matrix.to_3x3().inverted() @ object.matrix.to_3x3()).to_quaternion()
    else:
        return object.matrix.to_quaternion()


def utilityAssignMaterialSlots(material, matNode, filepath):
    slots = {
        "Base Color": "albedo",
        "Specular": "specular",
        "Emissive Color": "emissive",
        "Emission": "emissive",
        "Roughness": "roughness",
        "Ambient Occlusion": "ao",
        "Metallic": "metal",
        "Normal": "normal"
    }

    if not material.use_nodes:
        return

    for node in material.node_tree.nodes:
        if node.type == 'TEX_IMAGE':
            if not node.image:
                continue

            file = matNode.CreateFile()

            try:
                # Attempt to build a relative path to the image based on where the cast is being saved.
                file.SetPath(os.path.relpath(
                    node.image.filepath, os.path.dirname(filepath)))
            except:
                # Fallback to the absolute path of the image.
                file.SetPath(node.image.filepath)

            for output in node.outputs:
                if output.is_linked:
                    connection = output.links[0].to_socket.name

                    if connection in slots:
                        matNode.SetSlot(slots[connection], file.Hash())


def exportModel(self, context, root, armatureOrMesh, filepath):
    model = root.CreateModel()
    model.SetName(armatureOrMesh.name)

    boneToIndex = {}
    boneToHash = {}

    # Build skeleton and collect meshes.
    if armatureOrMesh.type == 'ARMATURE':
        skeleton = model.CreateSkeleton()

        bpy.context.view_layer.objects.active = armatureOrMesh
        bpy.ops.object.mode_set(mode='EDIT')

        for i, bone in enumerate(armatureOrMesh.data.edit_bones):
            boneToIndex[bone.name] = i

        for bone in armatureOrMesh.data.edit_bones:
            boneNode = skeleton.CreateBone()
            boneNode.SetName(bone.name)
            boneToHash[bone.name] = boneNode.Hash()

            if bone.parent is not None:
                mat = (bone.parent.matrix.inverted() @ bone.matrix)
            else:
                mat = bone.matrix

            (position, rotation, scale) = mat.decompose()

            if bone.parent is not None:
                boneNode.SetParentIndex(boneToIndex[bone.parent.name])
            else:
                boneNode.SetParentIndex(-1)

            boneNode.SetLocalPosition(
                (position.x * self.scale, position.y * self.scale, position.z * self.scale))
            boneNode.SetLocalRotation(
                (rotation.x, rotation.y, rotation.z, rotation.w))
            boneNode.SetScale((scale.x, scale.y, scale.z))

            (position, rotation, _) = bone.matrix.decompose()

            boneNode.SetWorldPosition(
                (position.x * self.scale, position.y * self.scale, position.z * self.scale))
            boneNode.SetWorldRotation(
                (rotation.x, rotation.y, rotation.z, rotation.w))

        bpy.ops.object.mode_set(mode='POSE')

        meshes = [x for x in bpy.data.objects if x.type == 'MESH' and armatureOrMesh in [
            m.object for m in x.modifiers if m.type == 'ARMATURE']]
    else:
        meshes = [armatureOrMesh]

    materialToHash = {}

    # Collect, aggregate and build materials.
    for mesh in meshes:
        for material in mesh.data.materials:
            if material.name in materialToHash:
                continue

            matNode = model.CreateMaterial()
            matNode.SetName(material.name)
            matNode.SetType("pbr")

            utilityAssignMaterialSlots(material, matNode, filepath)

            materialToHash[material.name] = matNode.Hash()

    # Build meshes, blend shapes.
    with ProgressReport(context.window_manager) as progress:
        progress.enter_substeps(len(meshes))

        for mesh in meshes:
            meshNode = model.CreateMesh()

            if not mesh.name.startswith("CastMesh"):
                meshNode.SetName(mesh.name)

            if mesh.active_material is not None:
                meshNode.SetMaterial(materialToHash[mesh.active_material.name])

            deformers = [x for x in mesh.modifiers if x.type == 'ARMATURE']

            if len(deformers) > 0 and deformers[0].use_deform_preserve_volume:
                meshNode.SetSkinningMethod("quaternion")

            blendMesh = bmesh.new(use_operators=False)
            blendMesh.from_mesh(
                mesh.data, face_normals=False, vertex_normals=True, use_shape_key=False, shape_key_index=0)

            vertexPositions = [None] * len(blendMesh.verts)
            vertexNormals = [None] * len(blendMesh.verts)
            faceBuffer = [None] * (len(blendMesh.faces) * 3)

            uvLayers = []
            colors = []

            # Collect the uv layers for this mesh, making the active the first.
            if blendMesh.loops.layers.uv.active is not None:
                uvLayers.append(blendMesh.loops.layers.uv.active)

                # Add the other layers after the active one.
                for layer in blendMesh.loops.layers.uv.values():
                    if layer != uvLayers[0]:
                        uvLayers.append(layer)

            vertexUVLayers = [[None] * len(blendMesh.verts) for _ in uvLayers]

            # Collect the color layer for this mesh, we only support one, the active one.
            if blendMesh.verts.layers.float_color.active is not None:
                colors.append(blendMesh.verts.layers.float_color.active)
            elif blendMesh.verts.layers.color.active is not None:
                colors.append(blendMesh.verts.layers.color.active)
            elif blendMesh.loops.layers.float_color.active is not None:
                colors.append(blendMesh.loops.layers.float_color.active)
            elif blendMesh.loops.layers.color.active is not None:
                colors.append(blendMesh.loops.layers.color.active)

            vertexColorLayers = [[None] * len(blendMesh.verts) for _ in colors]

            vertexMaxInfluence = 0

            for i, vert in enumerate(blendMesh.verts):
                vertexPositions[i] = (
                    vert.co.x * self.scale, vert.co.y * self.scale, vert.co.z * self.scale)
                vertexNormals[i] = (
                    vert.normal.x, vert.normal.y, vert.normal.z)

                vertexLoopCount = len(vert.link_loops)

                # Calculate the maximum influence for this vertex.
                maximumInfluence = 0

                if blendMesh.verts.layers.deform.active is not None:
                    for weight in vert[blendMesh.verts.layers.deform.active].values():
                        if weight > WEIGHT_THRESHOLD:
                            maximumInfluence += 1

                vertexMaxInfluence = max(vertexMaxInfluence, maximumInfluence)

                # Calculate the average uv coords for each face that shares this vertex.
                for uvLayer, uvLayerLoop in enumerate(uvLayers):
                    uv = Vector((0.0, 0.0))

                    for loop in vert.link_loops:
                        uv += loop[uvLayerLoop].uv / vertexLoopCount

                    vertexUVLayers[uvLayer][i] = (uv.x, 1.0 - uv.y)

                # Calculate per-vert/per-face vertex colors.
                if blendMesh.verts.layers.float_color.active is not None \
                        or blendMesh.verts.layers.color.active is not None:
                    color = vert[colors[0]]

                    vertexColorLayers[0][i] = CastColor.toInteger(
                        (color.x, color.y, color.z, color.w))
                elif blendMesh.loops.layers.float_color.active is not None \
                        or blendMesh.loops.layers.color.active is not None:
                    color = Vector((0.0, 0.0, 0.0, 0.0))

                    for loop in vert.link_loops:
                        color += loop[colors[0]] / vertexLoopCount

                    vertexColorLayers[0][i] = CastColor.toInteger(
                        (color.x, color.y, color.z, color.w))

            if blendMesh.verts.layers.deform.active is not None and maximumInfluence > 0:
                meshNode.SetMaximumWeightInfluence(vertexMaxInfluence)

                vertexGroups = [x.name for x in mesh.vertex_groups]

                vertexWeightValueBuffer = [
                    0.0] * (len(blendMesh.verts) * vertexMaxInfluence)
                vertexWeightBoneBuffer = [
                    0] * (len(blendMesh.verts) * vertexMaxInfluence)

                for i, vert in enumerate(blendMesh.verts):
                    weights = vert[blendMesh.verts.layers.deform.active]
                    slot = 0

                    for vgroup, weight in weights.items():
                        if weight > WEIGHT_THRESHOLD:
                            vertexWeightValueBuffer[(
                                i * vertexMaxInfluence) + slot] = weight
                            vertexWeightBoneBuffer[(
                                i * vertexMaxInfluence) + slot] = boneToIndex[vertexGroups[vgroup]]

                            slot += 1

                meshNode.SetVertexWeightValueBuffer(vertexWeightValueBuffer)
                meshNode.SetVertexWeightBoneBuffer(vertexWeightBoneBuffer)

            for i, face in enumerate(blendMesh.faces):
                faceBuffer[(i * 3)] = face.loops[2].vert.index
                faceBuffer[(i * 3) +
                           1] = face.loops[0].vert.index
                faceBuffer[(i * 3) +
                           2] = face.loops[1].vert.index

            meshNode.SetVertexPositionBuffer(vertexPositions)
            meshNode.SetVertexNormalBuffer(vertexNormals)

            for uvLayer, vertexUVs in enumerate(vertexUVLayers):
                meshNode.SetVertexUVLayerBuffer(uvLayer, vertexUVs)

            meshNode.SetUVLayerCount(len(vertexUVLayers))

            for colorLayer, vertexColors in enumerate(vertexColorLayers):
                meshNode.SetVertexColorBuffer(colorLayer, vertexColors)

            meshNode.SetColorLayerCount(len(vertexColorLayers))

            meshNode.SetFaceBuffer(faceBuffer)

            blendMesh.free()

            if mesh.data.shape_keys is not None:
                shapeNode = model.CreateBlendShape()
                shapeNode.SetName(mesh.data.shape_keys.name)
                shapeNode.SetBaseShape(meshNode.Hash())

                targetWeights = []
                targetShapes = []

                progress.enter_substeps(
                    len(mesh.data.shape_keys.key_blocks) - 1)

                for i, target in [(i, x) for i, x in enumerate(mesh.data.shape_keys.key_blocks) if x != mesh.data.shape_keys.reference_key]:
                    meshNode = model.CreateMesh()
                    meshNode.SetName(target.name)

                    blendMesh = bmesh.new(use_operators=False)
                    blendMesh.from_mesh(
                        mesh.data, face_normals=False, vertex_normals=True, use_shape_key=True, shape_key_index=i)

                    # Just set the new positions, which is the only supported blender operation at the moment.
                    for i, vert in enumerate(blendMesh.verts):
                        vertexPositions[i] = (
                            vert.co.x * self.scale, vert.co.y * self.scale, vert.co.z * self.scale)

                    meshNode.SetVertexPositionBuffer(vertexPositions)
                    meshNode.SetVertexNormalBuffer(vertexNormals)
                    meshNode.SetFaceBuffer(faceBuffer)

                    blendMesh.free()
                    targetWeights.append(target.slider_max)
                    targetShapes.append(meshNode.Hash())

                    progress.step()

                if len(targetWeights) > 0:
                    shapeNode.SetTargetWeightScales(targetWeights)
                    shapeNode.SetTargetShapes(targetShapes)

                progress.leave_substeps()

            progress.step()

        progress.leave_substeps()


def exportAction(self, context, root, objects, action):
    animation = root.CreateAnimation()
    animation.SetName(action.name)
    animation.SetFramerate(30.0)
    animation.SetLooping(self.is_looped)

    curves = {}

    with ProgressReport(context.window_manager) as progress:
        progress.enter_substeps(len(action.fcurves))

        # First pass will gather the curves we need to include in the animation and the properties they are keyed to.
        # This is because for curves like rotation_quaternion, we need all of the curves in one cast curve.
        for curve in action.fcurves:
            result = utilityResolveObjectTarget(objects, curve.data_path)

            if result is None:
                continue
            else:
                (object, target) = result

            # Right now, only support bone keys. Eventually, we will also check for BlendShape keys, and visibility keys.
            if type(target.data) != bpy_types.PoseBone:
                continue

            poseBone = target.data

            if target == poseBone.location.owner:
                result = curves.get(poseBone, [])
                result.append(
                    (curve, "location", curve.array_index))
                curves[poseBone] = result
            elif target == poseBone.rotation_quaternion.owner or target == poseBone.rotation_euler.owner:
                result = curves.get(poseBone, [])
                result.append(
                    (curve, "rotation_quaternion", curve.array_index))
                curves[poseBone] = result
            elif target == poseBone.scale.owner:
                result = curves.get(poseBone, [])
                result.append(
                    (curve, "scale", curve.array_index))
                curves[poseBone] = result

            progress.step()

        progress.leave_substeps()
        progress.enter_substeps(len(curves.keys()))

        # Iterate on the target/curves and generate the proper cast curves.
        for target, curves in curves.items():
            # We must handle quaternions separately, and key them together.
            rotationQuaternion = [
                x for x in curves if x[1] == "rotation_quaternion"]

            if len(rotationQuaternion) > 0:
                curveNode = animation.CreateCurve()
                curveNode.SetNodeName(target.name)
                curveNode.SetKeyPropertyName("rq")
                curveNode.SetMode("absolute")

                keyframes = []

                for curve in rotationQuaternion:
                    keyframes.extend([int(x.co[0])
                                      for x in curve[0].keyframe_points])

                keyframes = list(set(keyframes))

                curveNode.SetKeyFrameBuffer(keyframes)

                keyvalues = []

                for keyframe in keyframes:
                    quat = utilityGetQuatKeyValue(target)
                    keyvalues.append((quat.x, quat.y, quat.z, quat.w))

                curveNode.SetVec4KeyValueBuffer(keyvalues)

            for (curve, property, index) in curves:
                switcherProperty = {
                    "location": ["tx", "ty", "tz"],
                    "scale": ["sx", "sy", "sz"]
                }

                if property not in switcherProperty:
                    continue

                curveNode = animation.CreateCurve()
                curveNode.SetNodeName(target.name)
                curveNode.SetKeyPropertyName(switcherProperty[property][index])
                curveNode.SetMode("absolute")

                keyframes = [int(x.co[0]) for x in curve.keyframe_points]

                curveNode.SetKeyFrameBuffer(keyframes)

                keyvalues = []

                if property == "location":
                    scale = self.scale
                else:
                    scale = 1.0

                for keyframe in keyframes:
                    context.scene.frame_set(keyframe)
                    keyvalues.append(utilityGetSimpleKeyValue(
                        target, property)[index] * scale)

                curveNode.SetFloatKeyValueBuffer(keyvalues)

            progress.step()

        progress.leave_substeps()

        # Pull in the pose_markers as notetracks based on their name:[frames].
        if self.incl_notetracks:
            notetracks = {}

            for poseMarker in action.pose_markers:
                if poseMarker.name in notetracks:
                    notetracks[poseMarker.name].append(int(poseMarker.frame))
                else:
                    notetracks[poseMarker.name] = [int(poseMarker.frame)]

            # Generate the notetrack curves.
            for name, frames in notetracks.items():
                track = animation.CreateNotification()
                track.SetName(name)
                track.SetKeyFrameBuffer(frames)


def save(self, context, filepath=""):
    # The currently selected object.
    selectedObject = bpy.context.object

    cast = Cast()
    root = cast.CreateRoot()

    meta = root.CreateMetadata()
    meta.SetSoftware("Cast v%d.%d%d for Blender v%d.%d.%d" %
                     (self.bl_version[0], self.bl_version[1], self.bl_version[2],
                      bpy.app.version[0], bpy.app.version[1], bpy.app.version[2]))

    if self.up_axis:
        meta.SetUpAxis(self.up_axis)

    if self.incl_animation:
        # Check that the selected object is an 'ARMATURE' if we're exporting selected animations.
        if self.export_selected and (selectedObject is not None and selectedObject.type != 'ARMATURE'):
            raise Exception(
                "You must select an armature to export animation data for.")

        # Export either the armature's action, or all of the actions in the scene.
        if self.export_selected:
            exportAction(self, context, root, [selectedObject],
                         selectedObject.animation_data.action)
        else:
            for action in bpy.data.actions:
                exportAction(self, context, root, list(
                    bpy.data.objects), action)

    if self.incl_model:
        # Check that selected object is an 'ARMATURE' or mesh if we're exporting selected models.
        if self.export_selected and (selectedObject is None or (selectedObject.type != 'ARMATURE' and selectedObject.type != 'MESH')):
            raise Exception(
                "You must select an armature or mesh to export model data for.")

        # Export either the armature and it's meshes, the mesh, or all of the armature's / meshes in the scene.
        if self.export_selected:
            exportModel(self, context, root, selectedObject, filepath)
        else:
            # Handle armature and it's mesh references.
            for obj in bpy.data.objects:
                if obj.type == 'ARMATURE':
                    exportModel(self, context, root, obj, filepath)
            # Handle free standing meshes.
            for obj in bpy.data.objects:
                if obj.type == 'MESH':
                    if obj.find_armature() is None:
                        exportModel(self, context, root, obj, filepath)

    cast.save(filepath)
