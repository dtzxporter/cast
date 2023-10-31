import bpy
import bpy_types
import bmesh
import math

from bpy_extras.wm_utils.progress_report import ProgressReport
from mathutils import *
from .cast import Cast


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
    if property == "rotation_euler":
        quat = utilityGetQuatKeyValue(object)
        euler = quat.to_euler("XYZ")
        return (math.degrees(euler[0]), math.degrees(euler[1]), math.degrees(euler[2]))
    elif property == "scale":
        return object.scale
    return None


def utilityGetQuatKeyValue(object):
    if object.parent is not None:
        return (object.parent.matrix.to_3x3().inverted() @ object.matrix.to_3x3()).to_quaternion()
    else:
        return object.matrix.to_quaternion()


def exportModel(self, context, root, armatureOrMesh):
    model = root.CreateModel()
    model.SetName(armatureOrMesh.name)

    # Build skeleton and collect meshes.
    if armatureOrMesh.type == 'ARMATURE':
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

            # TODO: Parse, inject, and set material hashes.
            materialToHash[material.name] = True

    # Build meshes, blend shapes.
    with ProgressReport(context.window_manager) as progress:
        progress.enter_substeps(len(meshes))

        for mesh in meshes:
            meshNode = model.CreateMesh()

            if not mesh.name.startswith("CastMesh"):
                meshNode.SetName(mesh.name)

            blendMesh = bmesh.new(use_operators=False)
            blendMesh.from_mesh(
                mesh.data, face_normals=False, vertex_normals=True, use_shape_key=False, shape_key_index=0)

            vertexPositions = [None] * len(blendMesh.verts)
            vertexNormals = [None] * len(blendMesh.verts)
            faceBuffer = [None] * (len(blendMesh.faces) * 3)

            for i, vert in enumerate(blendMesh.verts):
                vertexPositions[i] = (
                    vert.co.x * self.scale, vert.co.y * self.scale, vert.co.z * self.scale)
                vertexNormals[i] = (
                    vert.normal.x, vert.normal.y, vert.normal.z)

            for i, face in enumerate(blendMesh.faces):
                faceBuffer[(i * 3)] = face.loops[2].vert.index
                faceBuffer[(i * 3) +
                           1] = face.loops[0].vert.index
                faceBuffer[(i * 3) +
                           2] = face.loops[1].vert.index

            meshNode.SetVertexPositionBuffer(vertexPositions)
            meshNode.SetVertexNormalBuffer(vertexNormals)
            meshNode.SetFaceBuffer(faceBuffer)

            blendMesh.free()

            if mesh.data.shape_keys is not None:
                shapeNode = model.CreateBlendShape()
                shapeNode.SetName(mesh.data.shape_keys.name)
                shapeNode.SetBaseShape(meshNode.Hash())

                targetWeights = []

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

                    progress.step()

                shapeNode.SetTargetWeightScales(targetWeights)

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
            elif target == poseBone.rotation_quaternion.owner:
                result = curves.get(poseBone, [])
                result.append(
                    (curve, "rotation_quaternion", curve.array_index))
                curves[poseBone] = result
            elif target == poseBone.rotation_euler.owner:
                result = curves.get(poseBone, [])
                result.append(
                    (curve, "rotation_euler", curve.array_index))
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
                    "rotation_euler": ["rx", "ry", "rz"],
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
            exportModel(self, context, root, selectedObject)
        else:
            # Handle armature and it's mesh references.
            for obj in bpy.data.objects:
                if obj.type == 'ARMATURE':
                    exportModel(self, context, root, obj)
            # Handle free standing meshes.
            for obj in bpy.data.objects:
                if obj.type == 'MESH':
                    if obj.find_armature() is None:
                        exportModel(self, context, root, obj)

    cast.save(filepath)
