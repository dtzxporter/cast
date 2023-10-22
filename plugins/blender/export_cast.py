import bpy
import bmesh
import bpy_types
from bpy_extras.wm_utils.progress_report import ProgressReport
import os
import array
import time
import math
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


def exportAction(self, context, root, objects, action):
    animation = root.CreateAnimation()
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
        if self.export_selected and (selectedObject is None or selectedObject.type != 'ARMATURE'):
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

    cast.save(filepath)
