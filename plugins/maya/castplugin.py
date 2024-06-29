import os
import json
import math
import sys

import maya.mel as mel
import maya.cmds as cmds
import maya.OpenMaya as OpenMaya
import maya.OpenMayaAnim as OpenMayaAnim
import maya.OpenMayaMPx as OpenMayaMPx


from cast import Cast, CastColor, Model, Animation, Instance, File

# Support Python 3.0+
try:
    if xrange is None:
        xrange = range
except NameError:
    xrange = range

# Used for various configuration
sceneSettings = {
    "importAtTime": False,
    "importSkin": True,
    "importReset": False,
    "importIK": True,
    "importConstraints": True,
    "exportAnim": True,
    "exportModel": True,
}

# Shared version number
version = "1.55"


def utilityAbout():
    cmds.confirmDialog(message="A Cast import and export plugin for Autodesk Maya. Cast is open-sourced model and animation container supported across various toolchains.\n\n- Developed by DTZxPorter\n- Version %s" % version,
                       button=['OK'], defaultButton='OK', title="About Cast")


def utilityResetCursor():
    try:
        from PySide2 import QtWidgets

        overrideCursor = QtWidgets.QApplication.overrideCursor()

        if overrideCursor is not None:
            QtWidgets.QApplication.restoreOverrideCursor()
            return True

        return False
    except:
        return False


def utilitySetWaitCursor():
    try:
        from PySide2 import QtGui, QtWidgets, QtCore

        QtWidgets.QApplication.setOverrideCursor(
            QtGui.QCursor(QtCore.Qt.WaitCursor))
    except:
        pass


def utilityGetNotetracks():
    if not cmds.objExists("CastNotetracks"):
        cmds.rename(cmds.spaceLocator(), "CastNotetracks")

    if not cmds.objExists("CastNotetracks.Notetracks"):
        cmds.addAttr("CastNotetracks", longName="Notetracks",
                     dataType="string", storable=True)
        cmds.setAttr("CastNotetracks.Notetracks", "{}", type="string")

    return json.loads(cmds.getAttr("CastNotetracks.Notetracks"))


def utilityClearNotetracks():
    if cmds.objExists("CastNotetracks"):
        cmds.delete("CastNotetracks")

    notetracks = cmds.textScrollList(
        "CastNotetrackList", query=True, allItems=True)

    if notetracks:
        for note in notetracks:
            cmds.textScrollList("CastNotetrackList",
                                edit=True, removeItem=note)


def utilityCreateNotetrack():
    frame = int(cmds.currentTime(query=True))

    if cmds.promptDialog(title="Cast - Create Notification", message="Enter in the new notification name:\t\t  ") != "Confirm":
        return

    name = cmds.promptDialog(query=True, text=True)

    if utilityAddNotetrack(name, frame):
        notifications = []
        notetracks = utilityGetNotetracks()

        for note in notetracks:
            for frame in notetracks[note]:
                notifications.append((frame, note))

        sortedNotifications = []

        for notification in sorted(notifications, key=lambda note: note[0]):
            sortedNotifications.append("[%d\t] %s" %
                                       (notification[0], notification[1]))
        cmds.textScrollList("CastNotetrackList", edit=True, removeAll=True)
        cmds.textScrollList("CastNotetrackList", edit=True,
                            append=sortedNotifications)


def utilityAddNotetrack(name, frame):
    current = utilityGetNotetracks()

    if name not in current:
        current[name] = []

    result = False

    if frame not in current[name]:
        current[name].append(frame)
        result = True

    cmds.setAttr("CastNotetracks.Notetracks",
                 json.dumps(current), type="string")

    return result


def utilityRemoveSelectedNotetracks():
    existing = utilityGetNotetracks()
    selected = cmds.textScrollList(
        "CastNotetrackList", query=True, selectItem=True)

    if not selected:
        return

    for select in selected:
        name = select[select.find(" ") + 1:]
        frame = int(select[:select.find(" ")].replace(
            "[", "").replace("]", "").replace("\t", ""))

        if name not in existing:
            continue
        if frame not in existing[name]:
            continue

        existing[name].remove(frame)

    cmds.textScrollList("CastNotetrackList", edit=True, removeItem=selected)

    cmds.setAttr("CastNotetracks.Notetracks",
                 json.dumps(existing), type="string")


def utilityEditNotetracks():
    if cmds.control("CastNotetrackEditor", exists=True):
        cmds.deleteUI("CastNotetrackEditor")

    window = cmds.window("CastNotetrackEditor",
                         title="Cast - Edit Notifications")
    windowLayout = cmds.formLayout("CastNotetrackEditor_Form")

    notetrackControl = cmds.text(
        label="Frame:                   Notification:", annotation="Current scene notifications")

    notifications = []
    notetracks = utilityGetNotetracks()

    for note in notetracks:
        for frame in notetracks[note]:
            notifications.append((frame, note))

    sortedNotifications = []

    for notification in sorted(notifications, key=lambda note: note[0]):
        sortedNotifications.append("[%d\t] %s" %
                                   (notification[0], notification[1]))

    notetrackListControl = cmds.textScrollList(
        "CastNotetrackList", append=sortedNotifications, allowMultiSelection=True)

    addNotificationControl = cmds.button(label="Add Notification",
                                         command=lambda x: utilityCreateNotetrack(),
                                         annotation="Add a notification at the current scene time")
    removeNotificationControl = cmds.button(label="Remove Selected",
                                            annotation="Removes the selected notifications",
                                            command=lambda x: utilityRemoveSelectedNotetracks())
    clearAllNotificationsControl = cmds.button(
        label="Clear All", annotation="Removes all notifications", command=lambda x: utilityClearNotetracks())

    cmds.formLayout(windowLayout, edit=True,
                    attachForm=[
                        (notetrackControl, "top", 10),
                        (notetrackControl, "left", 10),
                        (notetrackListControl, "left", 10),
                        (notetrackListControl, "right", 10),
                        (addNotificationControl, "left", 10),
                        (addNotificationControl, "bottom", 10),
                        (removeNotificationControl, "bottom", 10),
                        (clearAllNotificationsControl, "bottom", 10)
                    ],
                    attachControl=[
                        (notetrackListControl, "top", 5, notetrackControl),
                        (notetrackListControl, "bottom", 5, addNotificationControl),
                        (removeNotificationControl, "left",
                         5, addNotificationControl),
                        (clearAllNotificationsControl,
                         "left", 5, removeNotificationControl)
                    ])

    cmds.showWindow(window)


def utilityRemoveNamespaces():
    namespaceController = OpenMaya.MNamespace()
    namespaces = namespaceController.getNamespaces(True)

    for namespace in namespaces:
        if namespace not in [":UI", ":shared"]:
            try:
                mel.eval(
                    "namespace -removeNamespace \"%s\" -mergeNamespaceWithRoot;" % namespace)
            except RuntimeError:
                pass


def utilitySetToggleItem(name, value=False):
    if name in sceneSettings:
        sceneSettings[name] = bool(
            cmds.menuItem(name, query=True, checkBox=True))

    utilitySaveSettings()


def utilityLerp(a, b, time):
    return (a + time * (b - a))


def utilitySlerp(qa, qb, t):
    qm = OpenMaya.MQuaternion()

    cosHalfTheta = qa.w * qb.w + qa.x * qb.x + qa.y * qb.y + qa.z * qb.z

    if abs(cosHalfTheta) >= 1.0:
        qm.w = qa.w
        qm.x = qa.x
        qm.y = qa.y
        qm.z = qa.z

        return qa

    halfTheta = math.acos(cosHalfTheta)
    sinHalfTheta = math.sqrt(1.0 - cosHalfTheta * cosHalfTheta)

    if math.fabs(sinHalfTheta) < 0.001:
        qm.w = qa.w * 0.5 + qb.w * 0.5
        qm.x = qa.x * 0.5 + qb.x * 0.5
        qm.y = qa.y * 0.5 + qb.y * 0.5
        qm.z = qa.z * 0.5 + qb.z * 0.5

        return qm

    ratioA = math.sin((1 - t) * halfTheta) / sinHalfTheta
    ratioB = math.sin(t * halfTheta) / sinHalfTheta

    qm.w = qa.w * ratioA + qb.w * ratioB
    qm.x = qa.x * ratioA + qb.x * ratioB
    qm.y = qa.y * ratioA + qb.y * ratioB
    qm.z = qa.z * ratioA + qb.z * ratioB

    return qm


def utilityResolveCurveModeOverride(name, mode, overrides, isTranslate=False, isRotate=False, isScale=False):
    if not overrides:
        return mode

    try:
        parentTree = cmds.ls(name, long=True)[0].split('|')[1:-1]

        if not parentTree:
            return mode

        for parentName in parentTree:
            if parentName.find(":") >= -1:
                parentName = parentName[parentName.find(":") + 1:]

            for override in overrides:
                if isTranslate and not override.OverrideTranslationCurves():
                    continue
                elif isRotate and not override.OverrideRotationCurves():
                    continue
                elif isScale and not override.OverrideScaleCurves():
                    continue

                if parentName == override.NodeName():
                    return override.Mode()

        return mode
    except IndexError:
        return mode
    except RuntimeError:
        return mode


def utilityQueryToggleItem(name):
    if name in sceneSettings:
        return sceneSettings[name]
    return False


def utilityLoadSettings():
    global sceneSettings

    currentPath = os.path.dirname(os.path.realpath(
        cmds.pluginInfo("castplugin", q=True, p=True)))
    settingsPath = os.path.join(currentPath, "cast.cfg")

    try:
        file = open(settingsPath, "r")
        text = file.read()
        file.close()

        diskSettings = json.loads(text.decode("utf-8"))
    except:
        diskSettings = {}

    for key in diskSettings:
        if key in sceneSettings:
            sceneSettings[key] = diskSettings[key]

    utilitySaveSettings()


def utilitySaveSettings():
    global sceneSettings

    currentPath = os.path.dirname(os.path.realpath(
        cmds.pluginInfo("castplugin", q=True, p=True)))
    settingsPath = os.path.join(currentPath, "cast.cfg")

    try:
        file = open(settingsPath, "w")
        file.write(json.dumps(sceneSettings).encode("utf-8"))
        file.close()
    except:
        pass


def utilityCreateProgress(status="", maximum=0):
    instance = mel.eval("$tmp = $gMainProgressBar")
    cmds.progressBar(instance, edit=True, beginProgress=True,
                     isInterruptable=False, status=status, maxValue=max(1, maximum))
    return instance


def utilitySetVisibility(object, visible):
    dag = OpenMaya.MFnDagNode(object)
    while not cmds.attributeQuery("visibility", node=dag.fullPathName(), exists=True):
        try:
            parent = dag.parent(0)
            dag = OpenMaya.MFnDagNode(parent)
        except RuntimeError:
            return
    cmds.setAttr("%s.visibility" % dag.fullPathName(), visible)


def utilityStepProgress(instance):
    try:
        cmds.progressBar(instance, edit=True, step=1)
    except RuntimeError:
        pass


def utilityEndProgress(instance):
    try:
        cmds.progressBar(instance, edit=True, endProgress=True)
    except RuntimeError:
        pass


def utilityRemoveMenu():
    if cmds.control("CastMenu", exists=True):
        cmds.deleteUI("CastMenu", menu=True)


def utilityCreateMenu():
    cmds.setParent(mel.eval("$tmp = $gMainWindow"))
    menu = cmds.menu("CastMenu", label="Cast", tearOff=True)

    animMenu = cmds.menuItem(label="Animation", subMenu=True)

    cmds.menuItem("importAtTime", label="Import At Scene Time", annotation="Import animations starting at the current scene time",
                  checkBox=utilityQueryToggleItem("importAtTime"), command=lambda x: utilitySetToggleItem("importAtTime"))

    cmds.menuItem("importReset", label="Import Resets Scene", annotation="Importing animations clears all existing animations in the scene",
                  checkBox=utilityQueryToggleItem("importReset"), command=lambda x: utilitySetToggleItem("importReset"))

    cmds.menuItem(divider=True)

    cmds.menuItem("exportAnim", label="Export Animations", annotation="Include animations when exporting",
                  checkBox=utilityQueryToggleItem("exportAnim"), command=lambda x: utilitySetToggleItem("exportAnim"))

    cmds.menuItem(divider=True)

    cmds.menuItem("editNotetracks", label="Edit Notifications",
                  annotation="Edit the animations notifications", command=lambda x: utilityEditNotetracks())

    cmds.setParent(animMenu, menu=True)
    cmds.setParent(menu, menu=True)

    cmds.menuItem(label="Model", subMenu=True)

    cmds.menuItem("importSkin", label="Import Bind Skin", annotation="Imports and binds a model to it's smooth skin",
                  checkBox=utilityQueryToggleItem("importSkin"), command=lambda x: utilitySetToggleItem("importSkin"))

    cmds.menuItem("importIK", label="Import IK Handles", annotation="Imports and configures ik handles for the models skeleton",
                  checkBox=utilityQueryToggleItem("importIK"), command=lambda x: utilitySetToggleItem("importIK"))

    cmds.menuItem("importConstraints", label="Import Constraints", annotation="Imports and configures constraints for the models skeleton",
                  checkBox=utilityQueryToggleItem("importConstraints"), command=lambda x: utilitySetToggleItem("importConstraints"))

    cmds.menuItem(divider=True)

    cmds.menuItem("exportModel", label="Export Models", annotation="Include models when exporting",
                  checkBox=utilityQueryToggleItem("exportModel"), command=lambda x: utilitySetToggleItem("exportModel"))

    cmds.setParent(animMenu, menu=True)
    cmds.setParent(menu, menu=True)
    cmds.menuItem(divider=True)

    cmds.menuItem(label="Remove Namespaces", annotation="Removes all namespaces in the scene",
                  command=lambda x: utilityRemoveNamespaces())

    cmds.menuItem(divider=True)

    cmds.menuItem(label="Reset Scene", annotation="Resets the scene, removing the current animation curves",
                  command=lambda x: utilityClearAnimation())
    cmds.menuItem(label="About", annotation="View information about this plugin",
                  command=lambda x: utilityAbout())


def utilityClearAnimation():
    cmds.delete(all=True, c=True)

    for jointPath in cmds.ls(type="joint", long=True):
        try:
            selectList = OpenMaya.MSelectionList()
            selectList.add(jointPath)

            dagPath = OpenMaya.MDagPath()
            selectList.getDagPath(0, dagPath)

            restPosition = utilityGetSavedNodeData(dagPath)

            transform = OpenMaya.MFnTransform(dagPath)
            transform.set(restPosition)
        except RuntimeError:
            pass
        except ValueError:
            pass


def utilityCreateSkinCluster(newMesh, bones=[], maxWeightInfluence=1, skinningMethod="linear"):
    skinParams = [x for x in bones]
    skinParams.append(newMesh.fullPathName())

    try:
        newSkin = cmds.skinCluster(
            *skinParams, tsb=True, mi=maxWeightInfluence, nw=False)
    except RuntimeError:
        return None

    selectList = OpenMaya.MSelectionList()
    selectList.add(newSkin[0])

    clusterObject = OpenMaya.MObject()
    selectList.getDependNode(0, clusterObject)

    cluster = OpenMayaAnim.MFnSkinCluster(clusterObject)

    if skinningMethod == "linear":
        cmds.setAttr("%s.skinningMethod" % cluster.name(), 0)
    elif skinningMethod == "quaternion":
        cmds.setAttr("%s.skinningMethod" % cluster.name(), 1)

    return cluster


def utilityBuildPath(root, asset):
    if os.path.isabs(asset):
        return asset

    root = os.path.dirname(root)
    return os.path.join(root, asset)


def utilitySetCurveInterpolation(curvePath, mode="none"):
    try:
        cmds.rotationInterpolation(curvePath, convert=mode)
    except RuntimeError:
        pass


def utilityGetCurveInterpolation(curvePath):
    try:
        cmds.rotationInterpolation(curvePath, q=True)
    except RuntimeError:
        return "none"


def utilityAssignStingrayPBSSlots(materialInstance, slots, path):
    switcher = {
        "albedo": "TEX_color_map",
        "diffuse": "TEX_color_map",
        "normal": "TEX_normal_map",
        "metal": "TEX_metallic_map",
        "roughness": "TEX_roughness_map",
        "gloss": "TEX_roughness_map",
        "emissive": "TEX_emissive_map",
        "ao": "TEX_ao_map"
    }
    booleans = {
        "albedo": "use_color_map",
        "diffuse": "use_color_map",
        "normal": "use_normal_map",
        "metal": "use_metallic_map",
        "roughness": "use_roughness_map",
        "gloss": "use_roughness_map",
        "emissive": "use_emissive_map",
        "ao": "use_ao_map"
    }

    for slot in slots:
        connection = slots[slot]
        if not connection.__class__ is File:
            continue

        # Import the file by creating the node
        fileNode = cmds.shadingNode("file", name=(
            "%s_%s" % (materialInstance, slot)), asTexture=True)
        cmds.setAttr(("%s.fileTextureName" % fileNode), utilityBuildPath(
            path, connection.Path()), type="string")

        texture2dNode = cmds.shadingNode("place2dTexture", name=(
            "place2dTexture_%s_%s" % (materialInstance, slot)), asUtility=True)
        cmds.connectAttr(("%s.outUV" % texture2dNode),
                         ("%s.uvCoord" % fileNode))

        mel.eval("shaderfx -sfxnode %s -update" % materialInstance)

        # If we don't have a map for this material, skip to next one
        if not slot in switcher:
            continue

        # We have a slot, lets connect it
        cmds.connectAttr(("%s.outColor" % fileNode), ("%s.%s" %
                                                      (materialInstance, switcher[slot])), force=True)
        cmds.setAttr("%s.%s" % (materialInstance, booleans[slot]), 1)


def utilityAssignGenericSlots(materialInstance, slots, path):
    switcher = {
        "albedo": "color",
        "diffuse": "color",
        "normal": "normalCamera",
    }

    for slot in slots:
        connection = slots[slot]
        if not connection.__class__ is File:
            continue

        # Import the file by creating the node
        fileNode = cmds.shadingNode("file", name=(
            "%s_%s" % (materialInstance, slot)), asTexture=True)
        cmds.setAttr(("%s.fileTextureName" % fileNode), utilityBuildPath(
            path, connection.Path()), type="string")

        texture2dNode = cmds.shadingNode("place2dTexture", name=(
            "place2dTexture_%s_%s" % (materialInstance, slot)), asUtility=True)
        cmds.connectAttr(("%s.outUV" % texture2dNode),
                         ("%s.uvCoord" % fileNode))

        # If we don't have a map for this material, skip to next one
        if not slot in switcher:
            continue

        # We have a slot, lets connect it
        cmds.connectAttr(("%s.outColor" % fileNode), ("%s.%s" %
                                                      (materialInstance, switcher[slot])), force=True)


def utilityCreateMaterial(name, type, slots={}, path=""):
    switcher = {
        None: "lambert",
        "lambert": "lambert",
        "phong": "phong",
        "pbr": "StingrayPBS"
    }

    loader = {
        "lambert": utilityAssignGenericSlots,
        "phong": utilityAssignGenericSlots,
        "StingrayPBS": utilityAssignStingrayPBSSlots
    }

    if not type in switcher:
        type = None

    mayaShaderType = switcher[type]
    if cmds.getClassification(mayaShaderType) == [u'']:
        mayaShaderType = switcher[None]

    materialInstance = cmds.shadingNode(
        mayaShaderType, asShader=True, name=name)

    loader[mayaShaderType](materialInstance, slots, path)

    return materialInstance


def utilityGetTrackEndTime(track):
    numKeyframes = track.numKeys()

    if numKeyframes > 0:
        return track.time(numKeyframes - 1)
    else:
        return OpenMaya.MTime()


def utilityGetRestData(restTransform, component):
    if component == "rotation":
        return restTransform.eulerRotation()
    elif component == "rotation_quaternion":
        return restTransform.rotation()
    elif component == "translation":
        return restTransform.getTranslation(OpenMaya.MSpace.kTransform)
    elif component == "scale":
        scale = OpenMaya.MScriptUtil()
        scale.createFromList([1.0, 1.0, 1.0], 3)
        scalePtr = scale.asDoublePtr()

        restTransform.getScale(scalePtr)

        return (OpenMaya.MScriptUtil.getDoubleArrayItem(scalePtr, 0), OpenMaya.MScriptUtil.getDoubleArrayItem(scalePtr, 1), OpenMaya.MScriptUtil.getDoubleArrayItem(scalePtr, 2))
    else:
        raise Exception("Invalid component was specified!")


def utilityGetSavedNodeData(dagPath):
    # At this point we must have the attribute, as it's always called from the save function.
    restTransform = cmds.getAttr(
        "%s.castRestPosition" % dagPath.fullPathName())

    # Convert to matrix, then back to transformation matrix.
    restTransformMatrix = OpenMaya.MMatrix()
    restTransformMatrixDoubles = OpenMaya.MScriptUtil()
    restTransformMatrixDoubles.createMatrixFromList(
        restTransform, restTransformMatrix)

    # Make the transformation matrix.
    restTransform = OpenMaya.MTransformationMatrix(restTransformMatrix)

    return restTransform


def utilitySaveNodeData(dagPath):
    # Check if we already had the bone saved, if there is a runtime error, we already have it saved.
    if cmds.objExists("%s.castRestPosition" % dagPath.fullPathName()):
        return utilityGetSavedNodeData(dagPath)

    # Create the new attribute.
    cmds.addAttr(dagPath.fullPathName(), longName="castRestPosition",
                 attributeType="matrix", storable=True, writable=True, readable=True)

    # Grab the transform first
    transform = OpenMaya.MFnTransform(dagPath)

    restTransform = transform.transformation()
    restTransformMatrix = restTransform.asMatrix()

    # Convert matrix to double array.
    restDoubles = [0.0] * 16

    for x in xrange(4):
        restDoubles[x *
                    4] = OpenMaya.MScriptUtil.getDoubleArrayItem(restTransformMatrix[x], 0)
        restDoubles[(
            x * 4) + 1] = OpenMaya.MScriptUtil.getDoubleArrayItem(restTransformMatrix[x], 1)
        restDoubles[(
            x * 4) + 2] = OpenMaya.MScriptUtil.getDoubleArrayItem(restTransformMatrix[x], 2)
        restDoubles[(
            x * 4) + 3] = OpenMaya.MScriptUtil.getDoubleArrayItem(restTransformMatrix[x], 3)

    # Set the attribute.
    cmds.setAttr("%s.castRestPosition" %
                 dagPath.fullPathName(), restDoubles, type="matrix")

    # Required to handle relative transforms.
    return restTransform


def utilityGetOrCreateCurve(name, property, curveType):
    if not cmds.objExists("%s.%s" % (name, property)):
        return None

    try:
        selectList = OpenMaya.MSelectionList()
        selectList.add(name)

        nodePath = OpenMaya.MDagPath()
        selectList.getDagPath(0, nodePath)
    except RuntimeError:
        cmds.warning("Unable to animate %s[%s] due to a name conflict in the scene" % (
            name, property))
        return None

    restTransform = utilitySaveNodeData(nodePath)

    propertyPlug = OpenMaya.MFnDependencyNode(
        nodePath.node()).findPlug(property, False)
    propertyPlug.setKeyable(True)
    propertyPlug.setLocked(False)

    inputSources = OpenMaya.MPlugArray()
    propertyPlug.connectedTo(inputSources, True, False)

    if inputSources.length() == 0:
        # There is no curve attached to this node, so we can
        # make a new one on top of the property
        newCurve = OpenMayaAnim.MFnAnimCurve()
        newCurve.create(propertyPlug, curveType)
        return (newCurve, restTransform)
    elif inputSources[0].node().hasFn(OpenMaya.MFn.kAnimCurve):
        # There is an existing curve on this node, we need to
        # grab the curve, but then reset the rotation interpolation
        newCurve = OpenMayaAnim.MFnAnimCurve()
        newCurve.setObject(inputSources[0].node())

        # If we have a rotation curve, it's interpolation must be reset before keying
        if property in ["rx", "ry", "rz"] and utilityGetCurveInterpolation(newCurve.name()) != "none":
            utilitySetCurveInterpolation(newCurve.name())

        # Return the existing curve
        return (newCurve, restTransform)

    return None


def utilityImportQuatTrackData(tracks, property, timeUnit, frameStart, frameBuffer, valueBuffer, mode, blendWeight):
    timeBuffer = OpenMaya.MTimeArray()

    smallestFrame = OpenMaya.MTime(sys.maxsize, timeUnit)
    largestFrame = OpenMaya.MTime(0, timeUnit)

    # We must have three tracks here
    if None in tracks:
        return (smallestFrame, largestFrame)

    valuesX = OpenMaya.MDoubleArray(len(frameBuffer), 0.0)
    valuesY = OpenMaya.MDoubleArray(len(frameBuffer), 0.0)
    valuesZ = OpenMaya.MDoubleArray(len(frameBuffer), 0.0)

    for frame in frameBuffer:
        time = OpenMaya.MTime(frame, timeUnit) + frameStart

        smallestFrame = min(time, smallestFrame)
        largestFrame = max(time, largestFrame)

        timeBuffer.append(time)

    if mode == "absolute" or mode is None:
        for i in xrange(0, len(valueBuffer), 4):
            slot = int(i / 4)
            euler = OpenMaya.MQuaternion(
                valueBuffer[i], valueBuffer[i + 1], valueBuffer[i + 2], valueBuffer[i + 3]).asEulerRotation()

            valuesX[slot] = euler.x
            valuesY[slot] = euler.y
            valuesZ[slot] = euler.z
    elif mode == "additive":
        for i in xrange(0, len(valueBuffer), 4):
            slot = int(i / 4)

            frame = timeBuffer[slot]

            sampleX = tracks[0][0].evaluate(frame)
            sampleY = tracks[1][0].evaluate(frame)
            sampleZ = tracks[2][0].evaluate(frame)

            additiveQuat = OpenMaya.MEulerRotation(
                sampleX, sampleY, sampleZ).asQuaternion()
            frameQuat = OpenMaya.MQuaternion(
                valueBuffer[i], valueBuffer[i + 1], valueBuffer[i + 2], valueBuffer[i + 3])

            euler = utilitySlerp(
                additiveQuat, (frameQuat * additiveQuat), blendWeight).asEulerRotation()

            valuesX[slot] = euler.x
            valuesY[slot] = euler.y
            valuesZ[slot] = euler.z
    elif mode == "relative":
        rest = utilityGetRestData(tracks[0][1], "rotation_quaternion")

        for i in xrange(0, len(valueBuffer), 4):
            slot = int(i / 4)
            frame = OpenMaya.MQuaternion(
                valueBuffer[i], valueBuffer[i + 1], valueBuffer[i + 2], valueBuffer[i + 3])

            euler = (rest * frame).asEulerRotation()

            valuesX[slot] = euler.x
            valuesY[slot] = euler.y
            valuesZ[slot] = euler.z

    if timeBuffer.length() <= 0:
        return (smallestFrame, largestFrame)

    tracks[0][0].addKeys(timeBuffer,
                         valuesX,
                         OpenMayaAnim.MFnAnimCurve.kTangentLinear,
                         OpenMayaAnim.MFnAnimCurve.kTangentLinear)

    tracks[1][0].addKeys(timeBuffer,
                         valuesY,
                         OpenMayaAnim.MFnAnimCurve.kTangentLinear,
                         OpenMayaAnim.MFnAnimCurve.kTangentLinear)

    tracks[2][0].addKeys(timeBuffer,
                         valuesZ,
                         OpenMayaAnim.MFnAnimCurve.kTangentLinear,
                         OpenMayaAnim.MFnAnimCurve.kTangentLinear)

    return (smallestFrame, largestFrame)


def utilityImportSingleTrackData(tracks, property, timeUnit, frameStart, frameBuffer, valueBuffer, mode, blendWeight):
    timeBuffer = OpenMaya.MTimeArray()

    smallestFrame = OpenMaya.MTime(sys.maxsize, timeUnit)
    largestFrame = OpenMaya.MTime(0, timeUnit)

    # We must have one track here
    if None in tracks:
        return (smallestFrame, largestFrame)

    track = tracks[0][0]
    restTransform = tracks[0][1]

    for frame in frameBuffer:
        time = OpenMaya.MTime(frame, timeUnit) + frameStart

        smallestFrame = min(time, smallestFrame)
        largestFrame = max(time, largestFrame)

        timeBuffer.append(time)

    # Default track mode is absolute meaning that the
    # values are what they should be in the curve already
    if mode == "absolute" or mode is None:
        curveValueBuffer = OpenMaya.MDoubleArray(len(valueBuffer), 0.0)

        for i, value in enumerate(valueBuffer):
            curveValueBuffer[i] = value
    # Additive curves are applied to any existing curve value in the scene
    # so we will add it to the sample at the given time
    elif mode == "additive":
        curveValueBuffer = OpenMaya.MDoubleArray(len(valueBuffer), 0.0)

        for i, value in enumerate(valueBuffer):
            sample = track.evaluate(timeBuffer[i])

            curveValueBuffer[i] = utilityLerp(
                sample, sample + value, blendWeight)
    # Relative curves are applied against the resting position value in the scene
    # we will add it to the rest position
    elif mode == "relative":
        curveValueBuffer = OpenMaya.MDoubleArray(len(valueBuffer), 0.0)

        restSwitcher = {
            "tx": lambda: utilityGetRestData(restTransform, "translation")[0],
            "ty": lambda: utilityGetRestData(restTransform, "translation")[1],
            "tz": lambda: utilityGetRestData(restTransform, "translation")[2],
            "sx": lambda: utilityGetRestData(restTransform, "scale")[0],
            "sy": lambda: utilityGetRestData(restTransform, "scale")[1],
            "sz": lambda: utilityGetRestData(restTransform, "scale")[2],
        }

        if property in restSwitcher:
            rest = restSwitcher[property]()
        else:
            rest = 0.0

        for i, value in enumerate(valueBuffer):
            curveValueBuffer[i] = rest + value

    if timeBuffer.length() <= 0:
        return (smallestFrame, largestFrame)

    track.addKeys(timeBuffer,
                  curveValueBuffer,
                  OpenMayaAnim.MFnAnimCurve.kTangentLinear,
                  OpenMayaAnim.MFnAnimCurve.kTangentLinear)

    return (smallestFrame, largestFrame)


def importSkeletonConstraintNode(skeleton, handles, paths, indexes, jointTransform):
    if skeleton is None:
        return

    for constraint in skeleton.Constraints():
        targetBone = paths[indexes[constraint.TargetBone().Hash()]]
        constraintBone = paths[indexes[constraint.ConstraintBone().Hash()]]

        type = constraint.ConstraintType()
        skip = []

        if constraint.SkipX():
            skip.append("x")
        if constraint.SkipY():
            skip.append("y")
        if constraint.SkipZ():
            skip.append("z")

        if type == "pt":
            cmds.pointConstraint(targetBone, constraintBone,
                                 name=constraint.Name() or "CastPointConstraint", maintainOffset=constraint.MaintainOffset(), skip=skip)
        elif type == "or":
            cmds.orientConstraint(targetBone, constraintBone,
                                  name=constraint.Name() or "CastOrientConstraint", maintainOffset=constraint.MaintainOffset(), skip=skip)
        elif type == "sc":
            cmds.scaleConstraint(targetBone, constraintBone,
                                 name=constraint.Name() or "CastScaleConstraint", maintainOffset=constraint.MaintainOffset(), skip=skip)


def importSkeletonIKNode(skeleton, handles, paths, indexes, jointTransform):
    if skeleton is None:
        return

    bones = skeleton.Bones()

    for handle in skeleton.IKHandles():
        startBone = handles[indexes[handle.StartBone().Hash()]]
        endBone = handles[indexes[handle.EndBone().Hash()]]

        # For every bone in the chain, we need to copy the `rotate` to `jointOrient` because
        # the ik solver is going to override the value for `rotate.`
        stopBonePath = paths[indexes[handle.StartBone().Hash()]]
        currentBonePath = paths[indexes[handle.EndBone().Hash()]]
        currentBone = handle.EndBone()

        while True:
            bone = handles[indexes[currentBone.Hash()]]
            boneRotation = OpenMaya.MQuaternion()

            bone.getRotation(boneRotation)
            bone.setOrientation(boneRotation)
            bone.setRotation(OpenMaya.MQuaternion())

            if currentBonePath == stopBonePath:
                break
            if currentBone.ParentIndex() > -1:
                currentBonePath = paths[currentBone.ParentIndex()]
                currentBone = bones[currentBone.ParentIndex()]
            else:
                break

        startBonePath = OpenMaya.MDagPath()
        endBonePath = OpenMaya.MDagPath()

        startBone.getPath(startBonePath)
        endBone.getPath(endBonePath)

        ikHandle = OpenMayaAnim.MFnIkHandle()
        ikHandle.create(startBonePath, endBonePath)
        ikHandle.setName(handle.Name() or "CastIKHandle")

        # For whatever reason, if we don't "turn it on and off again" it doesn't work...
        cmds.ikHandle(ikHandle.fullPathName(), e=True, solver="ikSCsolver")
        cmds.ikHandle(ikHandle.fullPathName(), e=True, solver="ikRPsolver")

        targetBone = handle.TargetBone()

        if targetBone is not None:
            cmds.parent(ikHandle.fullPathName(),
                        paths[indexes[targetBone.Hash()]])

            if handle.UseTargetRotation():
                cmds.orientConstraint(
                    paths[indexes[targetBone.Hash()]], endBonePath.fullPathName())
        else:
            cmds.parent(ikHandle.fullPathName(), jointTransform.fullPathName())

        cmds.setAttr("%s.poleVector" % ikHandle.fullPathName(), 0, 0, 0)
        cmds.setAttr("%s.twist" % ikHandle.fullPathName(), 0)

        poleVectorBone = handle.PoleVectorBone()

        if poleVectorBone is not None:
            cmds.connectAttr(
                "%s.translate" % paths[indexes[poleVectorBone.Hash()]],
                "%s.poleVector" % ikHandle.fullPathName())

        poleBone = handle.PoleBone()

        if poleBone is not None:
            cmds.connectAttr(
                "%s.rotateX" % paths[indexes[poleBone.Hash()]],
                "%s.twist" % ikHandle.fullPathName())

        cmds.setAttr("%s.translate" % ikHandle.fullPathName(), 0, 0, 0)
        cmds.setAttr("%s.rotate" % ikHandle.fullPathName(), 0, 0, 0)


def importSkeletonNode(skeleton):
    if skeleton is None:
        return (None, None, None, None)

    bones = skeleton.Bones()
    handles = [None] * len(bones)
    paths = [None] * len(bones)
    indexes = {}

    jointTransform = OpenMaya.MFnTransform()
    jointNode = jointTransform.create()
    jointTransform.setName("Joints")

    progress = utilityCreateProgress("Importing skeleton...", len(bones) * 3)

    for i, bone in enumerate(bones):
        newBone = OpenMayaAnim.MFnIkJoint()
        newBone.create(jointNode)
        newBone.setName(bone.Name())
        handles[i] = newBone
        indexes[bone.Hash()] = i

        utilityStepProgress(progress)

    for i, bone in enumerate(bones):
        if bone.ParentIndex() > -1:
            cmds.parent(handles[i].fullPathName(),
                        handles[bone.ParentIndex()].fullPathName())

        utilityStepProgress(progress)

    for i, bone in enumerate(bones):
        newBone = handles[i]
        paths[i] = newBone.fullPathName()

        if bone.SegmentScaleCompensate() is not None:
            segmentScale = bone.SegmentScaleCompensate()
            scalePlug = newBone.findPlug("segmentScaleCompensate")
            if scalePlug is not None:
                scalePlug.setBool(bool(segmentScale))

        if bone.LocalPosition() is not None:
            localPos = bone.LocalPosition()
            localRot = bone.LocalRotation()

            newBone.setTranslation(OpenMaya.MVector(
                localPos[0], localPos[1], localPos[2]), OpenMaya.MSpace.kTransform)
            newBone.setRotation(OpenMaya.MQuaternion(
                localRot[0], localRot[1], localRot[2], localRot[3]))

        if bone.Scale() is not None:
            scale = bone.Scale()

            scaleUtility = OpenMaya.MScriptUtil()
            scaleUtility.createFromList([scale[0], scale[1], scale[2]], 3)

            newBone.setScale(scaleUtility.asDoublePtr())

        utilityStepProgress(progress)
    utilityEndProgress(progress)

    return (handles, paths, indexes, jointTransform)


def importMaterialNode(path, material):
    # If you already created the material, ignore this
    if cmds.objExists("%sSG" % material.Name()):
        return material.Name()

    # Create the material and assign slots
    materialNew = utilityCreateMaterial(
        material.Name(), material.Type(), material.Slots(), path)

    # Create the shader group that connects to a surface
    materialGroup = cmds.sets(
        renderable=True, empty=True, name=("%sSG" % materialNew))

    # Connect shader -> surface
    cmds.connectAttr(("%s.outColor" % materialNew),
                     ("%s.surfaceShader" % materialGroup), force=True)

    return materialNew


def importModelNode(model, path):
    # Import skeleton for binds, materials for meshes
    (handles, paths, indexes, jointTransform) = importSkeletonNode(model.Skeleton())
    materials = {x.Name(): importMaterialNode(path, x)
                 for x in model.Materials()}

    # Import the meshes
    meshTransform = OpenMaya.MFnTransform()
    meshNode = meshTransform.create()
    meshTransform.setName(
        model.Name() or os.path.splitext(os.path.basename(path))[0])

    meshes = model.Meshes()
    progress = utilityCreateProgress("Importing meshes...", len(meshes))
    meshHandles = {}

    for mesh in meshes:
        newMeshTransform = OpenMaya.MFnTransform()
        newMeshNode = newMeshTransform.create(meshNode)
        newMeshTransform.setName(mesh.Name() or "CastMesh")

        faces = list(mesh.FaceBuffer())
        facesRemoved = 0

        # Remove any degenerate faces before giving it to the mesh.
        for i in xrange(len(faces) - 3, -1, -3):
            remove = False

            if faces[i] == faces[i + 1]:
                facesRemoved += 1
                remove = True
            elif faces[i] == faces[i + 2]:
                facesRemoved += 1
                remove = True
            elif faces[i + 1] == faces[i + 2]:
                facesRemoved += 1
                remove = True

            if remove:
                del faces[i + 2]
                del faces[i + 1]
                del faces[i]

        # Warn the user that this took place.
        if facesRemoved > 0:
            cmds.warning("Removed %d degenerate faces from %s" %
                         (facesRemoved, newMeshTransform.name()))

        # Triangle count / vertex count
        faceCount = int(mesh.FaceCount()) - facesRemoved
        vertexCount = int(mesh.VertexCount())

        scriptUtil = OpenMaya.MScriptUtil()
        scriptUtil.createFromList(faces, len(faces))

        faceBuffer = OpenMaya.MIntArray(scriptUtil.asIntPtr(), len(faces))
        faceCountBuffer = OpenMaya.MIntArray(faceCount, 3)

        vertexPositions = mesh.VertexPositionBuffer()
        scriptUtil = OpenMaya.MScriptUtil()
        scriptUtil.createFromList([x for y in (vertexPositions[i:i + 3] + tuple([1.0]) * (i < len(
            vertexPositions) - 2) for i in xrange(0, len(vertexPositions), 3)) for x in y], vertexCount)

        vertexPositionBuffer = OpenMaya.MFloatPointArray(
            scriptUtil.asFloat4Ptr(), vertexCount)

        newMesh = OpenMaya.MFnMesh()
        # Store the mesh for reference in other nodes later
        meshHandles[mesh.Hash()] = newMesh.create(vertexCount, faceCount, vertexPositionBuffer,
                                                  faceCountBuffer, faceBuffer, newMeshNode)
        newMesh.setName(mesh.Name() or "CastShape")

        scriptUtil = OpenMaya.MScriptUtil()
        scriptUtil.createFromList(
            [x for x in xrange(vertexCount)], vertexCount)

        vertexIndexBuffer = OpenMaya.MIntArray(
            scriptUtil.asIntPtr(), vertexCount)

        # Each channel after position / faces is optional
        # meaning we should completely ignore null buffers here
        # even though you *should* have them

        vertexNormals = mesh.VertexNormalBuffer()
        if vertexNormals is not None:
            scriptUtil = OpenMaya.MScriptUtil()
            scriptUtil.createFromList(
                [x for x in vertexNormals], len(vertexNormals))

            vertexNormalBuffer = OpenMaya.MVectorArray(
                scriptUtil.asFloat3Ptr(), int(len(vertexNormals) / 3))

            newMesh.setVertexNormals(vertexNormalBuffer, vertexIndexBuffer)

        vertexColors = mesh.VertexColorBuffer()
        if vertexColors is not None:
            scriptUtil = OpenMaya.MScriptUtil()
            scriptUtil.createFromList(
                [x for xs in [CastColor.fromInteger(x) for x in vertexColors] for x in xs], len(vertexColors) * 4)

            vertexColorBuffer = OpenMaya.MColorArray(
                scriptUtil.asFloat4Ptr(), len(vertexColors))

            newMesh.setVertexColors(vertexColorBuffer, vertexIndexBuffer)

        uvLayerCount = mesh.UVLayerCount()

        scriptUtil = OpenMaya.MScriptUtil()
        scriptUtil.createFromList([x for x in xrange(len(faces))], len(faces))

        faceIndexBuffer = OpenMaya.MIntArray(
            scriptUtil.asIntPtr(), len(faces))

        # Set a material, or default
        meshMaterial = mesh.Material()
        try:
            if meshMaterial is not None:
                cmds.sets(newMesh.fullPathName(), forceElement=(
                    "%sSG" % materials[meshMaterial.Name()]))
            else:
                cmds.sets(newMesh.fullPathName(),
                          forceElement="initialShadingGroup")
        except RuntimeError:
            pass

        for i in xrange(uvLayerCount):
            uvLayer = mesh.VertexUVLayerBuffer(i)
            scriptUtil = OpenMaya.MScriptUtil()
            scriptUtil.createFromList([y for xs in [uvLayer[faces[x] * 2:faces[x] * 2 + 1]
                                                    for x in xrange(len(faces))] for y in xs], len(faces))

            uvUBuffer = OpenMaya.MFloatArray(
                scriptUtil.asFloatPtr(), len(faces))

            scriptUtil = OpenMaya.MScriptUtil()
            scriptUtil.createFromList([1 - y for xs in [uvLayer[faces[x] * 2 + 1:faces[x] * 2 + 2]
                                                        for x in xrange(len(faces))] for y in xs], len(faces))

            uvVBuffer = OpenMaya.MFloatArray(
                scriptUtil.asFloatPtr(), len(faces))

            if i > 0:
                newUVName = newMesh.createUVSetWithName(
                    ("map%d" % (i + 1)))
            else:
                newUVName = newMesh.currentUVSetName()

            newMesh.setCurrentUVSetName(newUVName)
            newMesh.setUVs(
                uvUBuffer, uvVBuffer, newUVName)
            newMesh.assignUVs(
                faceCountBuffer, faceIndexBuffer, newUVName)

        maximumInfluence = mesh.MaximumWeightInfluence()
        skinningMethod = mesh.SkinningMethod()

        if maximumInfluence > 0 and sceneSettings["importSkin"]:
            weightBoneBuffer = mesh.VertexWeightBoneBuffer()
            weightValueBuffer = mesh.VertexWeightValueBuffer()
            weightedBones = list({paths[x] for x in weightBoneBuffer})
            weightedBonesCount = len(weightedBones)

            skinCluster = utilityCreateSkinCluster(
                newMesh, weightedBones, maximumInfluence, skinningMethod)

            weightedRemap = {paths.index(
                x): i for i, x in enumerate(weightedBones)}

            clusterAttrBase = skinCluster.name() + ".weightList[%d]"
            clusterAttrArray = (".weights[0:%d]" % (weightedBonesCount - 1))

            weightedValueBuffer = [0.0] * (weightedBonesCount)

            for i in xrange(vertexCount):
                if weightedBonesCount == 1:
                    clusterAttrPayload = clusterAttrBase % i + ".weights[0]"
                    weightedValueBuffer[0] = 1.0
                else:
                    clusterAttrPayload = clusterAttrBase % i + clusterAttrArray

                    for j in xrange(maximumInfluence):
                        weightIndex = j + (i * maximumInfluence)
                        weightBone = weightBoneBuffer[weightIndex]
                        weightValue = weightValueBuffer[weightIndex]

                        weightedValueBuffer[weightedRemap[weightBone]
                                            ] += weightValue

                cmds.setAttr(clusterAttrPayload, *weightedValueBuffer)
                weightedValueBuffer = [0.0] * (weightedBonesCount)

        utilityStepProgress(progress)
    utilityEndProgress(progress)

    blendShapes = model.BlendShapes()
    blendShapesByBaseShape = {}

    # Merge the blend shapes together by their base shapes, so we only create one deformer per base.
    for blendShape in blendShapes:
        baseShapeHash = blendShape.BaseShape().Hash()

        if baseShapeHash not in meshHandles:
            continue
        if baseShapeHash not in blendShapesByBaseShape:
            blendShapesByBaseShape[baseShapeHash] = [blendShape]
        else:
            blendShapesByBaseShape[baseShapeHash].append(blendShape)

    progress = utilityCreateProgress("Importing shapes...", len(blendShapes))

    # Iterate over blend shapes by base shapes.
    for blendShapes in blendShapesByBaseShape.values():
        baseShape = meshHandles[blendShapes[0].BaseShape().Hash()]
        baseShapeDagNode = OpenMaya.MFnDagNode(baseShape)
        baseShapeTransform = OpenMaya.MFnDagNode(baseShapeDagNode.parent(0))

        # Create the target shapes.
        targetShapes = [cmds.duplicate(
            baseShapeDagNode.fullPathName(), ic=True) for _ in blendShapes]

        # Create the deformer on the abse shape.
        blendDeformer = OpenMayaAnim.MFnBlendShapeDeformer()
        blendDeformer.create(baseShape)

        # Create the targets in the deformer and set the new vertex data.
        for i, (targetShape, blendShape) in enumerate(zip(targetShapes, blendShapes)):
            # Place the new shape key under the base shape so that the key name will be unique to that mesh.
            cmds.parent(targetShape[0], baseShapeTransform.fullPathName())
            newShape = cmds.rename(targetShape[0], blendShape.Name())

            # Get the actual mesh name.
            newShapeShapes = cmds.listRelatives(
                newShape, shapes=True, fullPath=True)

            # Grab a handle to the new shape, which will be our target mesh.
            selectList = OpenMaya.MSelectionList()
            selectList.add(newShapeShapes[0])

            # Get the mesh object.
            targetShape = OpenMaya.MObject()
            selectList.getDependNode(0, targetShape)
            targetMesh = OpenMaya.MFnMesh(targetShape)

            # Rename the actual mesh to the key name.
            cmds.rename(newShapeShapes[0], blendShape.Name())

            # Set the shape positions.
            indices = blendShape.TargetShapeVertexIndices()
            positions = blendShape.TargetShapeVertexPositions()

            if not indices or not positions:
                cmds.warning(
                    "Ignoring blend shape \"%s\" for mesh \"%s\" no indices or positions specified." % (blendShape.Name(), baseShapeDagNode.name()))
                utilityStepProgress(progress)
                continue

            vertexPositions = OpenMaya.MFloatPointArray()

            targetMesh.getPoints(vertexPositions)

            for index, vertexIndex in enumerate(indices):
                vertexPositions.set(
                    vertexIndex, positions[index * 3], positions[(index * 3) + 1], positions[(index * 3) + 2], 1.0)

            targetMesh.setPoints(vertexPositions)

            blendDeformer.addTarget(baseShape, i, targetShape,
                                    max(0.0, blendShape.TargetWeightScale() or 1.0))
            blendTargetParent = OpenMaya.MFnDagNode(targetShape).parent(0)

            # Prevent rendering of the target mesh shapes.
            utilitySetVisibility(blendTargetParent, False)
            utilityStepProgress(progress)
    utilityEndProgress(progress)

    # Import any ik handles now that the meshes are bound because the constraints may
    # effect the bind pose of the joints causing the meshes to deform incorrectly.
    if sceneSettings["importIK"]:
        importSkeletonIKNode(model.Skeleton(), handles,
                             paths, indexes, jointTransform)

    # Import any additional constraints.
    if sceneSettings["importConstraints"]:
        importSkeletonConstraintNode(
            model.Skeleton(), handles, paths, indexes, jointTransform)


def importCurveNode(node, path, timeUnit, startFrame, overrides):
    propertySwitcher = {
        "rq": ["rx", "ry", "rz"],
        "tx": ["tx"],
        "ty": ["ty"],
        "tz": ["tz"],
        "sx": ["sx"],
        "sy": ["sy"],
        "sz": ["sz"],
        "vb": ["v"]
    }
    typeSwitcher = {
        "rq": OpenMayaAnim.MFnAnimCurve.kAnimCurveTA,
        "tx": OpenMayaAnim.MFnAnimCurve.kAnimCurveTL,
        "ty": OpenMayaAnim.MFnAnimCurve.kAnimCurveTL,
        "tz": OpenMayaAnim.MFnAnimCurve.kAnimCurveTL,
        "sx": OpenMayaAnim.MFnAnimCurve.kAnimCurveTL,
        "sy": OpenMayaAnim.MFnAnimCurve.kAnimCurveTL,
        "sz": OpenMayaAnim.MFnAnimCurve.kAnimCurveTL,
        "vb": OpenMayaAnim.MFnAnimCurve.kAnimCurveTU
    }
    trackSwitcher = {
        "rq": utilityImportQuatTrackData,
        "tx": utilityImportSingleTrackData,
        "ty": utilityImportSingleTrackData,
        "tz": utilityImportSingleTrackData,
        "sx": utilityImportSingleTrackData,
        "sy": utilityImportSingleTrackData,
        "sz": utilityImportSingleTrackData,
        "vb": utilityImportSingleTrackData
    }

    nodeName = node.NodeName()
    propertyName = node.KeyPropertyName()

    smallestFrame = OpenMaya.MTime(sys.maxsize, timeUnit)
    largestFrame = OpenMaya.MTime(0, timeUnit)

    if not propertyName in propertySwitcher:
        return (smallestFrame, largestFrame)

    tracks = [utilityGetOrCreateCurve(
        nodeName, x, typeSwitcher[propertyName]) for x in propertySwitcher[propertyName]]

    if tracks is None:
        return (smallestFrame, largestFrame)

    keyFrameBuffer = node.KeyFrameBuffer()
    keyValueBuffer = node.KeyValueBuffer()

    # Resolve any override if necessary.
    nodeMode = node.Mode()

    if propertyName in ["tx", "ty", "tz"]:
        nodeMode = utilityResolveCurveModeOverride(
            nodeName, nodeMode, overrides, isTranslate=True)
    elif propertyName in ["rq"]:
        nodeMode = utilityResolveCurveModeOverride(
            nodeName, nodeMode, overrides, isRotate=True)
    elif propertyName in ["sx", "sy", "sz"]:
        nodeMode = utilityResolveCurveModeOverride(
            nodeName, nodeMode, overrides, isScale=True)

    (smallestFrame, largestFrame) = trackSwitcher[propertyName](
        tracks, propertyName, timeUnit, startFrame, keyFrameBuffer, keyValueBuffer, nodeMode, node.AdditiveBlendWeight())

    # Make sure we have at least one quaternion track to set the interpolation mode to
    if propertyName == "rq":
        for track in tracks:
            if track is not None:
                utilitySetCurveInterpolation(track[0].name(), "quaternion")

    # Return the frame sizes [s, l] so we can adjust the scene times
    return (smallestFrame, largestFrame)


def importNotificationTrackNode(node, timeUnit, frameStart):
    smallestFrame = OpenMaya.MTime(sys.maxsize, timeUnit)
    largestFrame = OpenMaya.MTime(0, timeUnit)

    frameBuffer = node.KeyFrameBuffer()

    for frame in frameBuffer:
        time = OpenMaya.MTime(frame, timeUnit) + frameStart

        smallestFrame = min(time, smallestFrame)
        largestFrame = max(time, largestFrame)

        utilityAddNotetrack(node.Name(), int(time.value()))

    # Return the frame sizes [s, l] so we can adjust the scene times
    return (smallestFrame, largestFrame)


def importAnimationNode(node, path):
    # We need to be sure to disable auto keyframe, because it breaks import of animations
    # do this now so we don't forget...
    sceneAnimationController = OpenMayaAnim.MAnimControl()
    sceneAnimationController.setAutoKeyMode(False)

    # Check if the user requests the scene be cleared for each import.
    if utilityQueryToggleItem("importReset"):
        utilityClearAnimation()

    switcherLoop = {
        None: OpenMayaAnim.MAnimControl.kPlaybackOnce,
        0: OpenMayaAnim.MAnimControl.kPlaybackOnce,
        1: OpenMayaAnim.MAnimControl.kPlaybackLoop,
    }

    sceneAnimationController.setPlaybackMode(switcherLoop[node.Looping()])

    switcherFps = {
        None: OpenMaya.MTime.kFilm,
        2: OpenMaya.MTime.k2FPS,
        3: OpenMaya.MTime.k3FPS,
        24: OpenMaya.MTime.kFilm,
        30: OpenMaya.MTime.kNTSCFrame,
        60: OpenMaya.MTime.kNTSCField,
        100: OpenMaya.MTime.k100FPS,
        120: OpenMaya.MTime.k120FPS,
    }

    if int(node.Framerate()) in switcherFps:
        wantedFps = switcherFps[int(node.Framerate())]
    else:
        wantedFps = switcherFps[None]

    # If the user toggles this setting, we need to shift incoming frames
    # by the current time
    if sceneSettings["importAtTime"]:
        startFrame = sceneAnimationController.currentTime()
    else:
        startFrame = OpenMaya.MTime(0, wantedFps)

    # We need to determine the proper time to import the curves, for example
    # the user may want to import at the current scene time, and that would require
    # fetching once here, then passing to the curve importer.
    wantedSmallestFrame = OpenMaya.MTime(sys.maxsize, wantedFps)
    wantedLargestFrame = OpenMaya.MTime(1, wantedFps)

    curves = node.Curves()
    curveModeOverrides = node.CurveModeOverrides()

    progress = utilityCreateProgress("Importing animation...", len(curves))

    for x in curves:
        (smallestFrame, largestFrame) = importCurveNode(
            x, path, wantedFps, startFrame, curveModeOverrides)
        wantedSmallestFrame = min(smallestFrame, wantedSmallestFrame)
        wantedLargestFrame = max(largestFrame, wantedLargestFrame)
        utilityStepProgress(progress)

    utilityEndProgress(progress)

    for x in node.Notifications():
        (smallestFrame, largestFrame) = importNotificationTrackNode(
            x, wantedFps, startFrame)
        wantedSmallestFrame = min(smallestFrame, wantedSmallestFrame)
        wantedLargestFrame = max(largestFrame, wantedLargestFrame)

    # Set the animation segment
    if wantedSmallestFrame == OpenMaya.MTime(sys.maxsize, wantedFps):
        wantedSmallestFrame = OpenMaya.MTime(0, wantedFps)

    sceneAnimationController.setAnimationStartEndTime(
        wantedSmallestFrame, wantedLargestFrame)
    sceneAnimationController.setMinMaxTime(
        wantedSmallestFrame, wantedLargestFrame)
    sceneAnimationController.setCurrentTime(wantedSmallestFrame)


def importInstanceNodes(nodes, path):
    overrideCursor = utilityResetCursor()

    rootPath = cmds.fileDialog2(
        caption="Select the root directory where instance scenes are located", dialogStyle=2, startingDirectory=path, fileMode=3, okCaption="Import")

    if overrideCursor:
        utilitySetWaitCursor()

    if rootPath is None:
        return cmds.error("Unable to import instances without a root directory!")

    rootPath = rootPath[0]

    uniqueInstances = {}

    # Resolve unique instances by the scene they reference. Eventually we can also support
    # recursively searching for the referenced file if it doesn't exist exactly where it points to.
    for instance in nodes:
        refs = os.path.join(rootPath, instance.ReferenceFile().Path())

        if refs in uniqueInstances:
            uniqueInstances[refs].append(instance)
        else:
            uniqueInstances[refs] = [instance]

    name = os.path.splitext(os.path.basename(path))[0]

    # Used to contain the original imported scene, will be set to hidden once completed.
    baseGroup = OpenMaya.MFnTransform()
    baseGroup.create()
    baseGroup.setName("%s_scenes" % name)

    # Used to contain every instance.
    instanceGroup = OpenMaya.MFnTransform()
    instanceGroup.create()
    instanceGroup.setName("%s_instances" % name)

    for instancePath, instances in uniqueInstances.items():
        try:
            imported = cmds.file(instancePath, i=True,
                                 type="Cast", returnNewNodes=True)
        except RuntimeError:
            cmds.warning(
                "Instance: %s failed to import or not found, skipping..." % instancePath)
            continue

        cmds.select(imported, replace=True)

        imported = cmds.ls(l=True, selection=True, exactType="transform")
        importedRoots = [x for x in imported if len(x.split('|')) == 2]

        cmds.select(clear=True)

        roots = len(importedRoots)

        if roots == 0:
            cmds.warning(
                "Instance: %s imported nothing so there will be no instancing." % instancePath)
            continue

        if roots == 1:
            base = imported[0]
        else:
            group = OpenMaya.MFnTransform()
            group.create()
            group.setName("%s_scene" % os.path.splitext(
                os.path.basename(instancePath))[0])

            for root in importedRoots:
                cmds.parent(root, group.fullPathName())

            base = group.fullPathName()

        for instance in instances:
            newInstance = cmds.instance(base, name=instance.Name())[0]

            selectList = OpenMaya.MSelectionList()
            selectList.add(newInstance)

            dagPath = OpenMaya.MDagPath()
            selectList.getDagPath(0, dagPath)

            transform = OpenMaya.MFnTransform(dagPath)

            position = instance.Position()
            rotation = instance.Rotation()
            scale = instance.Scale()

            transform.setTranslation(OpenMaya.MVector(
                position[0], position[1], position[2]), OpenMaya.MSpace.kWorld)
            transform.setRotation(OpenMaya.MQuaternion(
                rotation[0], rotation[1], rotation[2], rotation[3]))

            scaleUtility = OpenMaya.MScriptUtil()
            scaleUtility.createFromList([scale[0], scale[1], scale[2]], 3)

            transform.setScale(scaleUtility.asDoublePtr())

            cmds.parent(newInstance, instanceGroup.fullPathName())

        cmds.parent(base, baseGroup.fullPathName())

    cmds.setAttr("%s.visibility" % baseGroup.fullPathName(), False)


def importCast(path):
    cast = Cast.load(path)

    instances = []

    for root in cast.Roots():
        for child in root.ChildrenOfType(Model):
            importModelNode(child, path)
        for child in root.ChildrenOfType(Animation):
            importAnimationNode(child, path)
        for child in root.ChildrenOfType(Instance):
            instances.append(child)

    if len(instances) > 0:
        importInstanceNodes(instances, path)


def exportAnimation(root, objects):
    animation = root.CreateAnimation()
    animation.SetFramerate(cmds.playbackOptions(query=True, fps=True))
    animation.SetLooping(cmds.playbackOptions(
        query=True, loop=True) == "continuous")

    # Configure the scene to use degrees.
    currentAngle = cmds.currentUnit(query=True, angle=True)

    cmds.currentUnit(angle="deg")

    # Grab the smallest and largest keyframe we want to support.
    startFrame = int(cmds.playbackOptions(query=True, ast=True))
    endFrame = int(cmds.playbackOptions(query=True, aet=True))

    # Make sure the frames are positive, for startFrame, force it to be 0 if it's < 0.
    # If endFrame is < 0, force a fatal error.
    if startFrame < 0:
        cmds.warning(
            "Animation start time was negative [%d], defaulting to 0." % startFrame)
        startFrame = 0
    if endFrame < 0:
        cmds.error("Animation end time must not be negative.")
        return

    simpleProperties = [
        ["translateX", "tx"],
        ["translateY", "ty"],
        ["translateZ", "tz"],
        ["scaleX", "sx"],
        ["scaleY", "sy"],
        ["scaleZ", "sz"]
    ]

    exportable = []

    # For each object, we want to query animatable properties, and which keyframes appear where.
    for object in objects:
        # Check simple properties
        for property in simpleProperties:
            keyframes = cmds.keyframe(
                object, at=property[0], query=True, timeChange=True)

            if keyframes:
                exportable.append(
                    [object, property[0], property[1], list(set([int(x) for x in keyframes]))])

        # Check rotation properties
        rotateX = cmds.keyframe(object, at="rotateX",
                                query=True, timeChange=True)
        rotateY = cmds.keyframe(object, at="rotateY",
                                query=True, timeChange=True)
        rotateZ = cmds.keyframe(object, at="rotateZ",
                                query=True, timeChange=True)

        keyframes = set()

        if rotateX:
            keyframes.update([int(x) for x in rotateX])
        if rotateY:
            keyframes.update([int(x) for x in rotateY])
        if rotateZ:
            keyframes.update([int(x) for x in rotateZ])

        if len(keyframes) > 0:
            exportable.append([object, "rotate", "rq", list(keyframes)])

    progress = utilityCreateProgress("Exporting animation...", len(exportable))

    for export in exportable:
        # Always ensure a control keyframe is present based on the start range.
        if not startFrame in export[3]:
            export[3].append(startFrame)

        keyframes = []
        keyvalues = []

        # Export the keyed and possibly control keyframes within the range.
        for frame in export[3]:
            if frame < startFrame or frame > endFrame:
                continue

            keyframes.append(frame)

            # We need to sample the joint orientation into the quaternion curve
            # because cast models will combine the rotation and orientation.
            if export[1] == "rotate":
                euler = cmds.getAttr("%s.rotate" % export[0], time=frame)[0]
                eulerJo = cmds.getAttr("%s.jointOrient" %
                                       export[0], time=frame)[0]

                quat = OpenMaya.MEulerRotation(math.radians(euler[0]), math.radians(
                    euler[1]), math.radians(euler[2])).asQuaternion()
                quatJo = OpenMaya.MEulerRotation(math.radians(eulerJo[0]), math.radians(
                    eulerJo[1]), math.radians(eulerJo[2])).asQuaternion()

                value = quat * quatJo

                keyvalues.append((value.x, value.y, value.z, value.w))
            else:
                keyvalues.append(cmds.getAttr("%s.%s" %
                                 (export[0], export[1]), time=frame))

        # Make sure we had at least one usable keyframe before creating the curve.
        if len(keyframes) > 0:
            curveNode = animation.CreateCurve()
            curveNode.SetNodeName(export[0])
            curveNode.SetKeyPropertyName(export[2])
            curveNode.SetMode("absolute")

            curveNode.SetKeyFrameBuffer(keyframes)

            if export[1] == "rotate":
                curveNode.SetVec4KeyValueBuffer(keyvalues)
            else:
                curveNode.SetFloatKeyValueBuffer(keyvalues)

        utilityStepProgress(progress)
    utilityEndProgress(progress)

    # Collect and create notification tracks.
    notifications = utilityGetNotetracks()

    for note in notifications:
        notetrack = animation.CreateNotification()
        notetrack.SetName(note)
        notetrack.SetKeyFrameBuffer([int(x) for x in notifications[note]])

    # Reset scene units back to user setting.
    cmds.currentUnit(angle=currentAngle)


def exportCast(path, exportSelected):
    cast = Cast()
    root = cast.CreateRoot()

    if sceneSettings["exportAnim"]:
        if exportSelected:
            exportAnimation(root, cmds.ls(type="joint", selection=True))
        else:
            exportAnimation(root, cmds.ls(type="joint"))

    if sceneSettings["exportModel"]:
        print("")

    cast.save(path)


class CastFileTranslator(OpenMayaMPx.MPxFileTranslator):
    def __init__(self):
        OpenMayaMPx.MPxFileTranslator.__init__(self)

    def haveWriteMethod(self):
        return True

    def haveReadMethod(self):
        return True

    def identifyFile(self, fileObject, buf, size):
        if os.path.splitext(fileObject.fullName())[1].lower() == ".cast":
            return OpenMayaMPx.MPxFileTranslator.kIsMyFileType
        return OpenMayaMPx.MPxFileTranslator.kNotMyFileType

    def filter(self):
        return "*.cast"

    def defaultExtension(self):
        return "cast"

    def writer(self, fileObject, optionString, accessMode):
        exportCast(fileObject.fullName(), exportSelected=accessMode ==
                   OpenMayaMPx.MPxFileTranslator.kExportActiveAccessMode)

    def reader(self, fileObject, optionString, accessMode):
        importCast(fileObject.fullName())


def createCastTranslator():
    return OpenMayaMPx.asMPxPtr(CastFileTranslator())


def initializePlugin(m_object):
    m_plugin = OpenMayaMPx.MFnPlugin(m_object, "DTZxPorter", version, "Any")
    try:
        m_plugin.registerFileTranslator(
            "Cast", None, createCastTranslator)
    except RuntimeError:
        pass
    utilityLoadSettings()
    utilityCreateMenu()


def uninitializePlugin(m_object):
    m_plugin = OpenMayaMPx.MFnPlugin(m_object)
    try:
        m_plugin.deregisterFileTranslator("Cast")
    except RuntimeError:
        pass
    utilityRemoveMenu()
