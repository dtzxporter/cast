import os
import json
import math
import sys

import maya.mel as mel
import maya.cmds as cmds
import maya.OpenMaya as OpenMaya
import maya.OpenMayaAnim as OpenMayaAnim
import maya.OpenMayaMPx as OpenMayaMPx


from cast import Cast, CastColor, Model, Animation, Instance, Metadata, File, Color

# Minimum weight value to be considered.
WEIGHT_THRESHOLD = 0.000001

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
    "importBlendShapes": True,
    "importMerge": False,
    "importAxis": True,
    "importHair": True,
    "exportAnim": True,
    "exportModel": True,
    "exportAxis": True,
    "bakeKeyframes": False,
    "createMinMaterials": False,
    "createFullMaterials": True,
    "createCurveHairs": True,
    "createMeshHairs": False,
    "setupArnoldHair": True,
}

# Shared version number
version = "1.89"

# Time unit to framerate map
framerateMap = {
    OpenMaya.MTime.k2FPS: 2,
    OpenMaya.MTime.k3FPS: 3,
    OpenMaya.MTime.k4FPS: 4,
    OpenMaya.MTime.k5FPS: 5,
    OpenMaya.MTime.k6FPS: 6,
    OpenMaya.MTime.k8FPS: 8,
    OpenMaya.MTime.k10FPS: 10,
    OpenMaya.MTime.k12FPS: 12,
    OpenMaya.MTime.kGames: 15,
    OpenMaya.MTime.k16FPS: 16,
    OpenMaya.MTime.k20FPS: 20,
    OpenMaya.MTime.kFilm: 24,
    OpenMaya.MTime.kPALFrame: 25,
    OpenMaya.MTime.kNTSCFrame: 30,
    OpenMaya.MTime.k40FPS: 40,
    OpenMaya.MTime.kShowScan: 48,
    OpenMaya.MTime.kPALField: 50,
    OpenMaya.MTime.kNTSCField: 60,
    OpenMaya.MTime.k75FPS: 75,
    OpenMaya.MTime.k80FPS: 80,
    OpenMaya.MTime.k100FPS: 100,
    OpenMaya.MTime.k120FPS: 120,
    OpenMaya.MTime.k125FPS: 125,
    OpenMaya.MTime.k150FPS: 150,
    OpenMaya.MTime.k200FPS: 200,
    OpenMaya.MTime.k240FPS: 240,
    OpenMaya.MTime.k250FPS: 250,
    OpenMaya.MTime.k300FPS: 300,
    OpenMaya.MTime.k375FPS: 375,
}


def utilityAbout():
    cmds.confirmDialog(message="A Cast import and export plugin for Autodesk Maya. Cast is open-sourced model and animation container supported across various toolchains.\n\n- Developed by DTZxPorter\n- Version v%s" % version,
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


def utilitySyncNotetracks():
    if not cmds.objExists("CastNotetracks"):
        return

    if cmds.textScrollList("CastNotetrackList", query=True, exists=True):
        cmds.textScrollList("CastNotetrackList", edit=True, removeAll=True)

        notifications = []
        notetracks = utilityGetNotetracks()

        for note in notetracks:
            for frame in notetracks[note]:
                notifications.append((frame, note))

        sortedNotifications = []

        for notification in sorted(notifications, key=lambda note: note[0]):
            sortedNotifications.append(
                "[%d\t] %s" % (notification[0], notification[1]))

        cmds.textScrollList("CastNotetrackList", edit=True,
                            append=sortedNotifications)


def utilityClearNotetracks():
    if cmds.objExists("CastNotetracks"):
        cmds.delete("CastNotetracks")

    if cmds.textScrollList("CastNotetrackList", query=True, exists=True):
        cmds.textScrollList("CastNotetrackList", edit=True, removeAll=True)


def utilityCreateNotetrack():
    frame = int(cmds.currentTime(query=True))

    result = cmds.promptDialog(title="Cast - Create Notification",
                               message="Enter in the new notification name:\t\t  ",
                               button=["Confirm", "Cancel"],
                               defaultButton="Confirm",
                               cancelButton="Cancel",
                               dismissString="Cancel")

    if result != "Confirm":
        return

    name = cmds.promptDialog(query=True, text=True)

    if utilityAddNotetrack(name, frame):
        utilitySyncNotetracks()


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

    notetrackListControl = cmds.textScrollList(
        "CastNotetrackList", allowMultiSelection=True)

    utilitySyncNotetracks()

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


def utilityGetDagPath(pathName):
    selectList = OpenMaya.MSelectionList()
    selectList.add(pathName)

    dagPath = OpenMaya.MDagPath()

    selectList.getDagPath(0, dagPath)

    return dagPath


def utilityBoneIndex(list, name):
    for i, v in enumerate(list):
        if v[0] == name:
            return i
    return -1


def utilityBoneParent(joint):
    fullPath = joint.fullPathName()
    splitPath = fullPath[1:].split("|")
    splitCount = len(splitPath)

    if splitCount > 2:
        dagPath = utilityGetDagPath(splitPath[len(splitPath) - 2])
    elif splitCount == 2:
        dagPath = utilityGetDagPath(fullPath[0:fullPath.find("|", 1)])
    else:
        dagPath = None

    if dagPath and dagPath.hasFn(OpenMaya.MFn.kJoint):
        return splitPath[len(splitPath) - 2]

    return None


def utilityFramerateToUnit(framerate):
    framerates = list(framerateMap.items())
    (unit, unitFramerate) = min(framerates,
                                key=lambda x: abs(x[1] - framerate))

    if unitFramerate != framerate:
        cmds.warning(
            "Using closest matching framerate units %f (wanted) %f (chosen)" % (framerate, unitFramerate))

    return unit


def utilityUnitToFramerate(unit):
    if unit in framerateMap:
        return framerateMap[unit]
    else:
        cmds.warning("Time unit wasn't in framerate map, defaulting to 30fps")
        return framerateMap[OpenMaya.MTime.kNTSCFrame]


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


def utilitySetRadioItem(names):
    for name in names:
        if name in sceneSettings:
            sceneSettings[name] = bool(cmds.menuItem(
                name, query=True, radioButton=True))

    utilitySaveSettings()


def utilityCreatePRS(position, rotation, scale):
    position = position or (0, 0, 0)
    rotation = rotation or (0, 0, 0, 1)
    scale = scale or (1, 1, 1)

    return (position, rotation, scale)


def utilitySetPRS(transform, position, rotation, scale):
    transform.setTranslation(OpenMaya.MVector(
        position[0], position[1], position[2]), OpenMaya.MSpace.kTransform)
    transform.setRotation(OpenMaya.MQuaternion(
        rotation[0], rotation[1], rotation[2], rotation[3]))

    scaleUtility = OpenMaya.MScriptUtil()
    scaleUtility.createFromList([scale[0], scale[1], scale[2]], 3)

    transform.setScale(scaleUtility.asDoublePtr())


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

    currentPath = os.path.dirname(
        os.path.realpath(cmds.pluginInfo("castplugin", q=True, p=True)))
    settingsPath = os.path.join(currentPath, "cast.cfg")

    try:
        with open(settingsPath, "r") as file:
            diskSettings = json.loads(file.read())
    except:
        diskSettings = {}

    for key in diskSettings:
        if key in sceneSettings:
            sceneSettings[key] = diskSettings[key]

    utilitySaveSettings()


def utilitySaveSettings():
    global sceneSettings

    currentPath = os.path.dirname(
        os.path.realpath(cmds.pluginInfo("castplugin", q=True, p=True)))
    settingsPath = os.path.join(currentPath, "cast.cfg")

    try:
        with open(settingsPath, "w") as file:
            file.write(json.dumps(sceneSettings))
    except:
        pass


def utilityCreateProgress(status="", maximum=0):
    instance = mel.eval("$tmp = $gMainProgressBar")
    cmds.progressBar(instance, edit=True, beginProgress=True,
                     isInterruptable=False, status=status, maxValue=max(1, maximum))
    return instance


def utilityStepProgress(instance, status=""):
    try:
        cmds.progressBar(instance, edit=True, status=status, step=1)
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


def utilityCreateMenu(refresh=False):
    if refresh:
        menu = cmds.menu("CastMenu", edit=True, deleteAllItems=True)
        cmds.setParent(menu, menu=True)
    else:
        cmds.setParent(mel.eval("$tmp = $gMainWindow"))
        menu = cmds.menu("CastMenu", label="Cast", tearOff=True)

    cmds.menuItem(label="Animation", subMenu=True)

    cmds.menuItem("importAtTime", label="Import At Scene Time", annotation="Import animations starting at the current scene time",
                  checkBox=utilityQueryToggleItem("importAtTime"), command=lambda x: utilitySetToggleItem("importAtTime"))

    cmds.menuItem("importReset", label="Import Resets Scene", annotation="Importing animations clears all existing animations in the scene",
                  checkBox=utilityQueryToggleItem("importReset"), command=lambda x: utilitySetToggleItem("importReset"))

    cmds.menuItem(divider=True)

    cmds.menuItem("exportAnim", label="Export Animations", annotation="Include animations when exporting",
                  checkBox=utilityQueryToggleItem("exportAnim"), command=lambda x: utilitySetToggleItem("exportAnim"))

    cmds.menuItem(divider=True)

    cmds.menuItem("bakeKeyframes", label="Bake Keyframes", annotation="Bake a keyframe for all frames of an animation",
                  checkBox=utilityQueryToggleItem("bakeKeyframes"), command=lambda x: utilitySetToggleItem("bakeKeyframes"))

    cmds.menuItem(divider=True)

    cmds.menuItem("editNotetracks", label="Edit Notifications",
                  annotation="Edit the animations notifications", command=lambda x: utilityEditNotetracks())

    cmds.setParent(menu, menu=True)

    cmds.menuItem(label="Model", subMenu=True)

    cmds.menuItem("importSkin", label="Import Bind Skin", annotation="Imports and binds a model to it's smooth skin",
                  checkBox=utilityQueryToggleItem("importSkin"), command=lambda x: utilitySetToggleItem("importSkin"))

    cmds.menuItem("importIK", label="Import IK Handles", annotation="Imports and configures ik handles for the models skeleton",
                  checkBox=utilityQueryToggleItem("importIK"), command=lambda x: utilitySetToggleItem("importIK"))

    cmds.menuItem("importConstraints", label="Import Constraints", annotation="Imports and configures constraints for the models skeleton",
                  checkBox=utilityQueryToggleItem("importConstraints"), command=lambda x: utilitySetToggleItem("importConstraints"))

    cmds.menuItem("importBlendShapes", label="Import Blend Shapes", annotation="Imports and configures blend shapes for a model",
                  checkBox=utilityQueryToggleItem("importBlendShapes"), command=lambda x: utilitySetToggleItem("importBlendShapes"))

    cmds.menuItem("importHair", label="Import Hair", annotation="Imports hair definitions for models",
                  checkBox=utilityQueryToggleItem("importHair"), command=lambda x: utilitySetToggleItem("importHair"))

    cmds.menuItem("importMerge", label="Import Merge", annotation="Imports and merges models together with a skeleton in the scene",
                  checkBox=utilityQueryToggleItem("importMerge"), command=lambda x: utilitySetToggleItem("importMerge"))

    cmds.menuItem(divider=True)

    cmds.menuItem("exportModel", label="Export Models", annotation="Include models when exporting",
                  checkBox=utilityQueryToggleItem("exportModel"), command=lambda x: utilitySetToggleItem("exportModel"))

    cmds.setParent(menu, menu=True)

    cmds.menuItem(label="Material", subMenu=True)

    cmds.radioMenuItemCollection()

    cmds.menuItem("createMinMaterials", label="Create Basic Materials", annotation="Creates basic materials with minimal configuration",
                  radioButton=utilityQueryToggleItem("createMinMaterials"), command=lambda x: utilitySetRadioItem(["createMinMaterials", "createFullMaterials"]))

    cmds.menuItem("createFullMaterials", label="Create Standard Materials", annotation="Creates standard materials with full configuration",
                  radioButton=utilityQueryToggleItem("createFullMaterials"), command=lambda x: utilitySetRadioItem(["createFullMaterials", "createMinMaterials"]))

    cmds.setParent(menu, menu=True)

    cmds.menuItem(label="Hair", subMenu=True)

    cmds.radioMenuItemCollection()

    cmds.menuItem("createCurveHairs", label="Create Curve Hairs", annotation="Creates hairs as curves",
                  radioButton=utilityQueryToggleItem("createCurveHairs"), command=lambda x: utilitySetRadioItem(["createCurveHairs", "createMeshHairs"]))

    cmds.menuItem("createMeshHairs", label="Create Mesh Hairs", annotation="Creates hairs as simple meshes",
                  radioButton=utilityQueryToggleItem("createMeshHairs"), command=lambda x: utilitySetRadioItem(["createMeshHairs", "createCurveHairs"]))

    cmds.menuItem(divider=True)

    cmds.menuItem("setupArnoldHair", label="Setup Arnold Curves", annotation="Configures Arnold rendering for each hair curve",
                  checkBox=utilityQueryToggleItem("setupArnoldHair"), command=lambda x: utilitySetToggleItem("setupArnoldHair"))

    cmds.setParent(menu, menu=True)

    cmds.menuItem(label="Scene", subMenu=True)

    cmds.menuItem("importAxis", label="Import Up Axis", annotation="Imports and sets the up axis for the scene",
                  checkBox=utilityQueryToggleItem("importAxis"), command=lambda x: utilitySetToggleItem("importAxis"))

    cmds.menuItem(divider=True)

    cmds.menuItem("exportAxis", label="Export Up Axis", annotation="Include up axis information when exporting",
                  checkBox=utilityQueryToggleItem("exportAxis"), command=lambda x: utilitySetToggleItem("exportAxis"))

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
    cmds.delete(all=True, channels=True)
    cmds.playbackOptions(minTime=0)

    for jointPath in cmds.ls(type="joint", long=True):
        try:
            dagPath = utilityGetDagPath(jointPath)
            restPosition = utilityGetSavedNodeData(dagPath)

            transform = OpenMaya.MFnTransform(dagPath)
            transform.set(restPosition)
        except RuntimeError:
            pass
        except ValueError:
            pass
    for deformer in cmds.ls(type="blendShape", long=True):
        for weight in cmds.listAttr("%s.weight" % deformer, m=True):
            try:
                cmds.setAttr("%s.%s" % (deformer, weight.split("|")[-1]), 0.0)
            except RuntimeError:
                pass
            except ValueError:
                pass

    # Set the current time back to zero after resetting all joint/shapes to trigger a refresh.
    cmds.currentTime(0, edit=True)

    utilityClearNotetracks()


def utilityGetSkinCluster(mesh):
    skinCluster = mel.eval("findRelatedSkinCluster %s" % mesh.fullPathName())

    if not skinCluster:
        return None

    selectList = OpenMaya.MSelectionList()
    selectList.add(skinCluster)

    clusterObject = OpenMaya.MObject()
    selectList.getDependNode(0, clusterObject)

    return OpenMayaAnim.MFnSkinCluster(clusterObject)


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


def utilityGetRootTransform(path):
    while True:
        parent = cmds.listRelatives(path, parent=True, fullPath=True)
        if not parent:
            return path.split("|")[-1]
        path = parent[0]


def utilityGetSceneSkeleton():
    joints = cmds.ls(type="joint", long=True)

    if not joints:
        return None

    skeleton = {}

    for joint in joints:
        skeleton[joint.split("|")[-1]] = joint

    # Grab the 'root' transform that cast creates for the new top level parent.
    skeleton[None] = utilityGetRootTransform(joints[0])

    return skeleton


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


def utilityQueryMaterialSlots(shader, matNode, path):
    slots = {
        "baseColor": "albedo",
        "color": "diffuse",
        "ambientColor": "specular",
        "specular": "specular",
        "specularColor": "specular",
        "metalness": "metal",
        "specularRoughness": "roughness",
        "specularAnisotropy": "aniso",
        "normalCamera": "normal",
    }

    fileConnections = cmds.listConnections(shader,
                                           plugs=True,
                                           connections=True,
                                           type="file")

    for i in xrange(0, len(fileConnections), 2):
        connection = fileConnections[i].split(".")[-1]
        node = fileConnections[i + 1].split(".")[0]

        if not cmds.objExists("%s.fileTextureName" % node):
            continue

        file = matNode.CreateFile()
        filePath = cmds.getAttr("%s.fileTextureName" % node)

        try:
            # Attempt to build a relative path to the image based on where the cast is being saved.
            file.SetPath(os.path.relpath(filePath, os.path.dirname(path)))
        except:
            # Fallback to the absolute path of the image.
            file.SetPath(filePath)

        if connection in slots:
            matNode.SetSlot(slots[connection], file.Hash())


def utilityAssignMaterialSlots(shader, slots, basic, path):
    # Determine workflow, metalness/roughness or specular/gloss
    metalness = ("metal" in slots and not basic)

    if basic:
        switcher = {
            "albedo": "color",
            "diffuse": "color",
            "specular": "ambientColor",
            "normal": "normalCamera",
        }
    elif metalness:
        switcher = {
            "albedo": "baseColor",
            "diffuse": "baseColor",
            "specular": "specular",
            "normal": "normalCamera",
            "metal": "metalness",
            "roughness": "specularRoughness",
            "gloss": "specularRoughness",
            "emissive": "emissionColor",
            "emask": "emission",
            "aniso": "specularAnisotropy",
        }
    else:
        # Set reasonable defaults for specular/gloss workflow.
        cmds.setAttr("%s.metalness" % shader, 0.0)
        cmds.setAttr("%s.specularIOR" % shader, 1.5)

        switcher = {
            "albedo": "baseColor",
            "diffuse": "baseColor",
            "specular": "specularColor",
            "normal": "normalCamera",
            "roughness": "specularRoughness",
            "gloss": "specularRoughness",
            "emissive": "emissionColor",
            "emask": "emission",
            "aniso": "specularAnisotropy",
        }

    # Prevent duplicate connections if one or more conflict occurs.
    used = []

    for slot in slots:
        connection = slots[slot]

        if not slot in switcher:
            continue
        if switcher[slot] in used:
            continue

        used.append(switcher[slot])

        if connection.__class__ is File:
            node = cmds.shadingNode("file", name=("%s_%s" % (shader, slot)),
                                    isColorManaged=True, asTexture=True)

            # This prevents scene color space rules from overriding our file ones.
            cmds.setAttr("%s.ignoreColorSpaceFileRules" % node, 1)

            # The following slots are raw data.
            if slot in ["metal", "normal", "gloss", "roughness", "aniso"] \
                    or (metalness and slot == "specular"):
                cmds.setAttr("%s.colorSpace" % node, "Raw", type="string")
            else:
                cmds.setAttr("%s.colorSpace" % node, "sRGB", type="string")

            cmds.setAttr("%s.fileTextureName" % node,
                         utilityBuildPath(path, connection.Path()), type="string")

            texture2dNode = cmds.shadingNode("place2dTexture",
                                             name=("place2dTexture_%s_%s" % (shader, slot)), asUtility=True)
            cmds.connectAttr(("%s.outUV" % texture2dNode),
                             ("%s.uvCoord" % node))
        elif connection.__class__ is Color:
            node = cmds.shadingNode("colorConstant",
                                    name=("color_%s" % slot), asUtility=True)

            # Handle color conversion if necessary, maya color node is linear.
            if connection.ColorSpace() == "srgb":
                rgba = CastColor.toLinearFromSRGB(connection.Rgba())
            else:
                rgba = connection.Rgba()

            cmds.setAttr("%s.inColor" % node, rgba[0], rgba[1], rgba[2])
            cmds.setAttr("%s.inAlpha" % node, rgba[3])
        else:
            continue

        # Update the shader node.
        mel.eval("shaderfx -sfxnode %s -update" % shader)

        # If we don't have a map for this material, skip to next one.
        if not slot in switcher:
            continue

        if slot == "normal":
            normaMap = cmds.shadingNode("bump2d", asUtility=True)

            # Tangent space normal map.
            cmds.setAttr("%s.bumpInterp" % normaMap, 1)

            cmds.connectAttr(("%s.outAlpha" % node),
                             ("%s.bumpValue" % normaMap), force=True)
            cmds.connectAttr(("%s.outNormal" % normaMap), ("%s.%s" %
                             (shader, switcher[slot])), force=True)
        elif slot == "gloss":
            invert = cmds.shadingNode("reverse", asUtility=True)

            cmds.connectAttr(("%s.outColor" % node),
                             ("%s.input" % invert), force=True)
            cmds.connectAttr(("%s.outputX" % invert), ("%s.%s" %
                             (shader, switcher[slot])), force=True)
        elif slot in ["metal", "roughness", "emask", "aniso"] \
                or (metalness and slot == "specular"):
            cmds.connectAttr(("%s.outColorR" % node), ("%s.%s" % (
                shader, switcher[slot])), force=True)
        else:
            cmds.connectAttr(("%s.outColor" % node), ("%s.%s" % (
                shader, switcher[slot])), force=True)


def utilityGetMaterial(mesh, path):
    shaders = OpenMaya.MObjectArray()
    shaderIndices = OpenMaya.MIntArray()
    materialPlugs = OpenMaya.MPlugArray()

    mesh.getConnectedShaders(path.instanceNumber(), shaders, shaderIndices)

    for i in xrange(shaders.length()):
        shaderNode = OpenMaya.MFnDependencyNode(shaders[i])

        shaderPlug = shaderNode.findPlug("surfaceShader")
        shaderPlug.connectedTo(materialPlugs, True, False)

        if materialPlugs.length() > 0:
            return OpenMaya.MFnDependencyNode(materialPlugs[0].node()).name()

    return None


def utilityCreateMaterial(name, type, slots={}, path=""):
    switcher = {
        None: "lambert",
        "lambert": "lambert",
        "pbr": "standardSurface"
    }

    modes = {
        "lambert": True,
        "standardSurface": False,
    }

    # If the user wants a minimal material, force them to use lambert.
    if sceneSettings["createMinMaterials"]:
        switcher["pbr"] = "lambert"

    if not type in switcher:
        type = None

    mayaShaderType = switcher[type]
    if cmds.getClassification(mayaShaderType) == [u'']:
        mayaShaderType = switcher[None]

    materialInstance = cmds.shadingNode(
        mayaShaderType, asShader=True, name=name)

    utilityAssignMaterialSlots(
        materialInstance, slots, modes[mayaShaderType], path)

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

        restTransform.getScale(scalePtr, OpenMaya.MSpace.kTransform)

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
        nodePath = utilityGetDagPath(name)
    except RuntimeError:
        cmds.warning("Unable to animate %s[%s] due to a name conflict in the scene" % (
            name, property))
        return None

    restTransform = utilitySaveNodeData(nodePath)

    propertyPlug = \
        OpenMaya.MFnDependencyNode(nodePath.node()).findPlug(property, False)
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

    trackXExists = tracks[0][0].numKeys() > 0
    trackYExists = tracks[1][0].numKeys() > 0
    trackZExists = tracks[2][0].numKeys() > 0

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
        rest = utilityGetRestData(
            tracks[0][1], "rotation_quaternion").asEulerRotation()

        for i in xrange(0, len(valueBuffer), 4):
            slot = int(i / 4)

            frame = timeBuffer[slot]

            if trackXExists:
                sampleX = tracks[0][0].evaluate(frame)
            else:
                sampleX = rest.x
            if trackYExists:
                sampleY = tracks[1][0].evaluate(frame)
            else:
                sampleY = rest.y
            if trackZExists:
                sampleZ = tracks[2][0].evaluate(frame)
            else:
                sampleZ = rest.z

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

            euler = (frame * rest).asEulerRotation()

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


def utilityImportBlendShapeTrackData(shapeName, timeUnit, frameStart, frameBuffer, valueBuffer):
    smallestFrame = OpenMaya.MTime(sys.maxsize, timeUnit)
    largestFrame = OpenMaya.MTime(0, timeUnit)

    deformers = []

    # Grab all of the deformer nodes so we can determine if they have this shape key.
    for deformer in cmds.ls(type="blendShape"):
        if cmds.objExists("%s.%s" % (deformer, shapeName)):
            cmds.setAttr("%s.%s" % (deformer, shapeName), 0)
            deformers.append(deformer)

    if not deformers:
        return (smallestFrame, largestFrame)

    track = OpenMayaAnim.MFnAnimCurve()
    track.create(OpenMayaAnim.MFnAnimCurve.kAnimCurveTL)
    track.setName("%s_weight" % shapeName)

    timeBuffer = OpenMaya.MTimeArray()
    curveValueBuffer = OpenMaya.MDoubleArray(len(valueBuffer), 0.0)

    for i, frame in enumerate(frameBuffer):
        time = OpenMaya.MTime(frame, timeUnit) + frameStart

        smallestFrame = min(time, smallestFrame)
        largestFrame = max(time, largestFrame)

        timeBuffer.append(time)
        curveValueBuffer[i] = valueBuffer[i]

    if timeBuffer.length() <= 0:
        return (smallestFrame, largestFrame)

    track.addKeys(timeBuffer,
                  curveValueBuffer,
                  OpenMayaAnim.MFnAnimCurve.kTangentLinear,
                  OpenMayaAnim.MFnAnimCurve.kTangentLinear)

    for deformer in deformers:
        cmds.connectAttr("%s.output" % track.name(), "%s.%s" %
                         (deformer, shapeName))

    return (smallestFrame, largestFrame)


def utilityImportSingleTrackData(tracks, property, timeUnit, frameStart, frameBuffer, valueBuffer, mode, blendWeight):
    timeBuffer = OpenMaya.MTimeArray()

    smallestFrame = OpenMaya.MTime(sys.maxsize, timeUnit)
    largestFrame = OpenMaya.MTime(0, timeUnit)

    # We must have one track here
    if None in tracks:
        return (smallestFrame, largestFrame)

    track = tracks[0][0]
    trackExists = track.numKeys() > 0

    restTransform = tracks[0][1]

    for frame in frameBuffer:
        time = OpenMaya.MTime(frame, timeUnit) + frameStart

        smallestFrame = min(time, smallestFrame)
        largestFrame = max(time, largestFrame)

        timeBuffer.append(time)

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
            if trackExists:
                sample = track.evaluate(timeBuffer[i])
            else:
                sample = rest

            if property in ["sx", "sy", "sz"]:
                curveValueBuffer[i] = utilityLerp(
                    sample, sample * value, blendWeight)
            else:
                curveValueBuffer[i] = utilityLerp(
                    sample, sample + value, blendWeight)
    # Relative curves are applied against the resting position value in the scene
    # we will add it to the rest position
    elif mode == "relative":
        curveValueBuffer = OpenMaya.MDoubleArray(len(valueBuffer), 0.0)

        for i, value in enumerate(valueBuffer):
            if property in ["sx", "sy", "sz"]:
                curveValueBuffer[i] = rest * value
            else:
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
        customOffset = constraint.CustomOffset()
        maintainOffset = constraint.MaintainOffset()
        weight = constraint.Weight()

        skip = []

        if constraint.SkipX():
            skip.append("x")
        if constraint.SkipY():
            skip.append("y")
        if constraint.SkipZ():
            skip.append("z")

        if type == "pt":
            if customOffset:
                offset = [customOffset[0], customOffset[1], customOffset[2]]
            else:
                offset = [0.0, 0.0, 0.0]

            if maintainOffset:
                cmds.pointConstraint(targetBone, constraintBone,
                                     name=constraint.Name() or "CastPointConstraint",
                                     maintainOffset=True,
                                     weight=weight,
                                     skip=skip)
            else:
                cmds.pointConstraint(targetBone, constraintBone,
                                     name=constraint.Name() or "CastPointConstraint",
                                     offset=offset,
                                     weight=weight,
                                     skip=skip)
        elif type == "or":
            if customOffset:
                rotation = OpenMaya.MQuaternion(
                    customOffset[0], customOffset[1], customOffset[2], customOffset[3])
                rotationEuler = rotation.asEulerRotation()

                offset = [rotationEuler.x, rotationEuler.y, rotationEuler.z]
            else:
                offset = [0.0, 0.0, 0.0]

            if maintainOffset:
                cmds.orientConstraint(targetBone, constraintBone,
                                      name=constraint.Name() or "CastOrientConstraint",
                                      maintainOffset=True,
                                      weight=weight,
                                      skip=skip)
            else:
                cmds.orientConstraint(targetBone, constraintBone,
                                      name=constraint.Name() or "CastOrientConstraint",
                                      offset=offset,
                                      weight=weight,
                                      skip=skip)
        elif type == "sc":
            if customOffset:
                offset = [customOffset[0], customOffset[1], customOffset[2]]
            else:
                offset = [1.0, 1.0, 1.0]

            if maintainOffset:
                cmds.scaleConstraint(targetBone, constraintBone,
                                     name=constraint.Name() or "CastScaleConstraint",
                                     maintainOffset=True,
                                     offset=offset,
                                     weight=weight,
                                     skip=skip)
            else:
                cmds.scaleConstraint(targetBone, constraintBone,
                                     name=constraint.Name() or "CastScaleConstraint",
                                     offset=offset,
                                     weight=weight,
                                     skip=skip)


def importMergeModel(sceneSkeleton, skeleton, handles, paths, jointTransform):
    if skeleton is None:
        return jointTransform

    # Find matching root bones in the selected object.
    # If we had none by the end of the transaction, warn the user that the models aren't compatible.
    foundMatchingRoot = False

    missingBones = []
    remappedBones = {}
    existingBones = {}

    bones = skeleton.Bones()

    for i, bone in enumerate(bones):
        if not bone.Name() in sceneSkeleton:
            missingBones.append(i)
            continue

        # Make sure that any bone in handles/paths is updated to joint to the new skeleton.
        remappedBones[paths[i]] = sceneSkeleton[bone.Name()]

        existingPath = utilityGetDagPath(sceneSkeleton[bone.Name()])

        # Store remapped connections for later, after bind pose remap.
        existingBones[i] = (existingPath.fullPathName(),
                            OpenMayaAnim.MFnIkJoint(existingPath))

        if bone.ParentIndex() > -1:
            continue

        foundMatchingRoot = True

        worldMatrix = cmds.xform(
            sceneSkeleton[bone.Name()], query=True, worldSpace=True, matrix=True)

        # Move the models bone to the existing bone in the scene's position.
        cmds.xform(paths[i], worldSpace=True, matrix=worldMatrix)

    if not foundMatchingRoot:
        cmds.warning(
            "Could not find compatible root bones make sure the skeletons are compatible.")
        return jointTransform

    # Create missing bones.
    while missingBones:
        for i in [x for x in missingBones]:
            bone = bones[i]

            if bone.ParentIndex() > -1 and not bones[bone.ParentIndex()].Name() in sceneSkeleton:
                continue
            elif bone.ParentIndex() > -1:
                parent = bones[bone.ParentIndex()].Name()
            else:
                parent = None

            newBone = OpenMayaAnim.MFnIkJoint()
            newBone.create()
            newBone.setName(bone.Name())

            cmds.parent(newBone.fullPathName(), sceneSkeleton[parent])

            worldMatrix = cmds.xform(
                paths[i], query=True, worldSpace=True, matrix=True)

            cmds.xform(newBone.fullPathName(),
                       worldSpace=True, matrix=worldMatrix)

            sceneSkeleton[bone.Name()] = newBone.fullPathName()

            # Make sure that any bone in handles/paths is updated to joint to the new skeleton.
            remappedBones[paths[i]] = newBone.fullPathName()

            handles[i] = newBone
            paths[i] = newBone.fullPathName()

            missingBones.remove(i)

    for oldBone, newBone in remappedBones.items():
        # Remap skinCluster connections.
        for oldConnection in cmds.listConnections(oldBone, type="skinCluster", plugs=True) or []:
            if ".matrix" in oldConnection:
                cmds.connectAttr("%s.worldMatrix" %
                                 newBone, oldConnection, force=True)
            elif ".lockWeights" in oldConnection:
                if not cmds.objExists("%s.lockInfluenceWeights" % newBone):
                    cmds.addAttr(newBone,
                                 shortName="liw", longName="lockInfluenceWeights", attributeType="bool")
                cmds.connectAttr("%s.lockInfluenceWeights" %
                                 newBone, oldConnection, force=True)
            elif ".influenceColor" in oldConnection:
                cmds.connectAttr("%s.objectColorRGB" %
                                 newBone, oldConnection, force=True)
        # Remap dagPose connections.
        for oldConnection in cmds.listConnections(oldBone, type="dagPose", plugs=True) or []:
            if ".members" in oldConnection:
                cmds.connectAttr("%s.message" %
                                 newBone, oldConnection, force=True)
            elif ".worldMatrix" in oldConnection:
                cmds.connectAttr("%s.bindPose" %
                                 newBone, oldConnection, force=True)

    for i, (path, handle) in existingBones.items():
        # Ensure existing bones now point to the correct path/handle in the scene.
        paths[i] = path
        handles[i] = handle

    # Remove the old transform node and set it to the new one.
    selectList = OpenMaya.MSelectionList()
    selectList.add(jointTransform.fullPathName())
    selectList.add(sceneSkeleton[None])

    oldPath = OpenMaya.MDagPath()
    newPath = OpenMaya.MDagPath()

    selectList.getDagPath(0, oldPath)
    selectList.getDagPath(1, newPath)

    cmds.delete(oldPath.fullPathName())

    # Trigger a skin update by adjusting the position of the root transform.
    # This only works if the scene can redraw at least once, before resetting it.
    original = cmds.getAttr("%s.tx" % newPath.fullPathName())

    cmds.setAttr("%s.tx" % newPath.fullPathName(), original + 1.0)
    cmds.refresh()

    # Set it back before finishing merge.
    cmds.setAttr("%s.tx" % newPath.fullPathName(), original)

    return OpenMaya.MFnTransform(newPath)


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

        utilityStepProgress(progress, "Importing skeleton...")

    for i, bone in enumerate(bones):
        if bone.ParentIndex() > -1:
            cmds.parent(handles[i].fullPathName(),
                        handles[bone.ParentIndex()].fullPathName())

        utilityStepProgress(progress, "Importing skeleton...")

    for i, bone in enumerate(bones):
        newBone = handles[i]
        paths[i] = newBone.fullPathName()

        ssc = bone.SegmentScaleCompensate()
        segmentScaleCompensate = newBone.findPlug("segmentScaleCompensate")

        if segmentScaleCompensate is not None:
            segmentScaleCompensate.setBool(bool(ssc))

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

        utilityStepProgress(progress, "Importing skeleton...")
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
    # If we want to merge this model, grab the 'existing' skeleton
    sceneSkeleton = None

    if sceneSettings["importMerge"]:
        sceneSkeleton = utilityGetSceneSkeleton()

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

    for m, mesh in enumerate(meshes):
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
        scriptUtil.createFromList([x for y in (vertexPositions[i:i + 3] + tuple([1.0]) *
                                               (i < len(vertexPositions) - 2) for i in xrange(0, len(vertexPositions), 3)) for x in y], vertexCount)

        vertexPositionBuffer = \
            OpenMaya.MFloatPointArray(scriptUtil.asFloat4Ptr(), vertexCount)

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

        colorLayerCount = mesh.ColorLayerCount()
        for i in xrange(colorLayerCount):
            colorLayer = mesh.VertexColorLayerBuffer(i)
            colorLayerPacked = mesh.VertexColorLayerBufferPacked(i)

            scriptUtil = OpenMaya.MScriptUtil()

            if colorLayerPacked:
                colors = len(colorLayer)
                scriptUtil.createFromList(
                    [x for xs in [CastColor.fromInteger(x) for x in colorLayer] for x in xs], colors * 4)
            else:
                colors = int(len(colorLayer) / 4)
                scriptUtil.createFromList(colorLayer, colors * 4)

            vertexColorBuffer = OpenMaya.MColorArray(
                scriptUtil.asFloat4Ptr(), colors)

            newColorName = newMesh.createColorSetWithName("color%d" % i)

            newMesh.setCurrentColorSetName(newColorName)
            newMesh.setVertexColors(vertexColorBuffer, vertexIndexBuffer)

        uvLayerCount = mesh.UVLayerCount()

        scriptUtil = OpenMaya.MScriptUtil()
        scriptUtil.createFromList([x for x in xrange(len(faces))], len(faces))

        faceIndexBuffer = OpenMaya.MIntArray(
            scriptUtil.asIntPtr(), len(faces))

        # Set a material, or default.
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
            scriptUtil.createFromList([1.0 - y for xs in [uvLayer[faces[x] * 2 + 1:faces[x] * 2 + 2]
                                                          for x in xrange(len(faces))] for y in xs], len(faces))

            uvVBuffer = OpenMaya.MFloatArray(
                scriptUtil.asFloatPtr(), len(faces))

            if i > 0:
                newUVName = newMesh.createUVSetWithName(
                    "map%d" % (i + 1))
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

        utilityStepProgress(
            progress, "Importing mesh [%d] of [%d]..." % (m + 1, len(meshes)))
    utilityEndProgress(progress)

    # Import the hairs if necessary.
    if sceneSettings["importHair"]:
        hairs = model.Hairs()

        for h, hair in enumerate(hairs):
            segmentsBuffer = hair.SegmentsBuffer()
            particleBuffer = hair.ParticleBuffer()
            particleOffset = 0

            strandCount = hair.StrandCount()

            hairTransform = OpenMaya.MFnTransform()
            hairTransformNode = hairTransform.create(meshNode)
            hairTransform.setName(hair.Name() or "CastHair")

            status = "Importing hair [%d] of [%d]..." % (h + 1, len(hairs))
            progress = utilityCreateProgress(status, strandCount)

            # Curve hair is the best option for accuracy
            # Mesh hair can be used as a light weight fallback method.
            if sceneSettings["createCurveHairs"]:
                for s in xrange(strandCount):
                    segment = segmentsBuffer[s]
                    points = OpenMaya.MPointArray(segment + 1)

                    for pt in xrange(segment + 1):
                        points.set(pt, particleBuffer[particleOffset * 3],
                                   particleBuffer[particleOffset * 3 + 1],
                                   particleBuffer[particleOffset * 3 + 2], 1.0)
                        particleOffset += 1

                    curveTransform = OpenMaya.MFnTransform()
                    curveTransformNode = \
                        curveTransform.create(hairTransformNode)
                    curveTransform.setName("CastStrand")

                    curve = OpenMaya.MFnNurbsCurve()
                    curve.createWithEditPoints(
                        # Always use the default degree 3 curve unless we don't have enough points.
                        points, 3 if segment >= 3 else 1, OpenMaya.MFnNurbsCurve.kOpen, False, False, False, curveTransformNode)

                    path = curveTransform.fullPathName()

                    # Maya becomes unusable if the curves are allowed to be viewed in the outliner.
                    # This will hide them and only show the hair transform, with no children.
                    cmds.setAttr("%s.hiddenInOutliner" % path, True)

                    # Setup Arnold rendering for curves, this is a light weight system
                    # That can be used to produce good results without nHair.
                    if sceneSettings["setupArnoldHair"] and cmds.objExists("%s.aiRenderCurve" % path):
                        cmds.setAttr("%s.aiRenderCurve" % path, True)
                        cmds.setAttr("%s.aiMode" % path, 1)

                        # Set a material, or default.
                        hairMaterial = hair.Material()
                        try:
                            if hairMaterial is not None:
                                cmds.connectAttr("%s.outColor" % materials[hairMaterial.Name()],
                                                 "%s.aiCurveShader" % path, force=True)
                        except RuntimeError:
                            pass

                    utilityStepProgress(progress, status)
            elif sceneSettings["createMeshHairs"]:
                vertexBuffer = OpenMaya.MFloatPointArray()
                normalBuffer = OpenMaya.MVectorArray()
                normalIndices = OpenMaya.MIntArray()
                faceBuffer = OpenMaya.MIntArray()

                def createNormal(v1, v2, v3):
                    return ((v3 - v1) ^ (v2 - v1).normal()).normal()

                def createVertex(position, normal):
                    index = vertexBuffer.length()

                    vertexBuffer.append(position)

                    normalBuffer.append(OpenMaya.MVector(normal))
                    normalIndices.append(index)
                    return index

                particleExtrusion = OpenMaya.MFloatVector(0.0, 0.0, 0.010)
                particleOffset = 0

                for s in xrange(strandCount):
                    segment = segmentsBuffer[s]

                    for i in xrange(segment):
                        a = OpenMaya.MFloatPoint(particleBuffer[particleOffset * 3],
                                                 particleBuffer[particleOffset * 3 + 1],
                                                 particleBuffer[particleOffset * 3 + 2], 1.0)
                        particleOffset += 1
                        b = OpenMaya.MFloatPoint(particleBuffer[particleOffset * 3],
                                                 particleBuffer[particleOffset * 3 + 1],
                                                 particleBuffer[particleOffset * 3 + 2], 1.0)

                        aUp = a + particleExtrusion
                        bUp = b + particleExtrusion

                        normal1 = createNormal(a, b, aUp)
                        normal2 = createNormal(a, b, bUp)

                        a1 = createVertex(a, normal1)
                        b1 = createVertex(b, normal1)
                        aUp1 = createVertex(aUp, normal1)

                        a2 = createVertex(a, normal2)
                        b2 = createVertex(b, normal2)
                        bUp2 = createVertex(bUp, normal2)

                        faceBuffer.extend([a1, b1, aUp1])
                        faceBuffer.extend([a2, b2, bUp2])

                    particleOffset += 1
                    utilityStepProgress(progress, status)

                vertexCount = int(vertexBuffer.length())
                faceCount = int(faceBuffer.length() / 3)
                faceCountBuffer = OpenMaya.MIntArray(faceCount, 3)

                newMesh = OpenMaya.MFnMesh()
                newMesh.create(vertexCount, faceCount,
                               vertexBuffer, faceCountBuffer, faceBuffer, hairTransformNode)

                newMesh.setVertexNormals(normalBuffer, normalIndices)

                # Set a material, or default.
                hairMaterial = hair.Material()
                try:
                    if hairMaterial is not None:
                        cmds.sets(newMesh.fullPathName(), forceElement=(
                            "%sSG" % materials[hairMaterial.Name()]))
                    else:
                        cmds.sets(newMesh.fullPathName(),
                                  forceElement="initialShadingGroup")
                except RuntimeError:
                    pass

            utilityEndProgress(progress)

    # Import blend shape controllers if necessary.
    if sceneSettings["importBlendShapes"]:
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

        progress = utilityCreateProgress(
            "Importing shapes...", len(blendShapes))

        # Iterate over blend shapes by base shapes.
        for blendShapes in blendShapesByBaseShape.values():
            baseShape = meshHandles[blendShapes[0].BaseShape().Hash()]
            baseShapeDagNode = OpenMaya.MFnDagNode(baseShape)

            # Create the deformer on the abse shape.
            blendDeformer = OpenMayaAnim.MFnBlendShapeDeformer()
            blendDeformer.create(baseShape)

            # Create the targets in the deformer and set the new vertex data.
            for i, blendShape in enumerate(blendShapes):
                # Clone the base shape to add as a target.
                tempShape = cmds.duplicate(
                    baseShapeDagNode.fullPathName(), ic=True)

                # Get the actual mesh name.
                newShapeShapes = cmds.listRelatives(
                    tempShape, shapes=True, fullPath=True)

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
                    cmds.delete(tempShape)
                    utilityStepProgress(progress, "Importing shapes...")
                    continue

                vertexPositions = OpenMaya.MFloatPointArray()

                targetMesh.getPoints(vertexPositions)

                for index, vertexIndex in enumerate(indices):
                    vertexPositions.set(
                        vertexIndex, positions[index * 3], positions[(index * 3) + 1], positions[(index * 3) + 2], 1.0)

                targetMesh.setPoints(vertexPositions)

                blendDeformer.addTarget(baseShape, i, targetShape,
                                        max(0.0, blendShape.TargetWeightScale() or 1.0))

                # Delete the cloned shape now that the target was added.
                cmds.delete(tempShape)

                utilityStepProgress(progress, "Importing shapes...")
        utilityEndProgress(progress)

    # Merge with the existing skeleton here if one is selected and we have a skeleton.
    if sceneSettings["importMerge"]:
        if sceneSkeleton:
            jointTransform = importMergeModel(sceneSkeleton, model.Skeleton(),
                                              handles, paths, jointTransform)
        else:
            cmds.warning(
                "No skeleton exists to merge to in the current scene.")

    # Import any ik handles now that the meshes are bound because the constraints may
    # effect the bind pose of the joints causing the meshes to deform incorrectly.
    if sceneSettings["importIK"]:
        importSkeletonIKNode(model.Skeleton(), handles,
                             paths, indexes, jointTransform)

    # Import any additional constraints.
    if sceneSettings["importConstraints"]:
        importSkeletonConstraintNode(
            model.Skeleton(), handles, paths, indexes, jointTransform)

    # Optional transform to apply to the skeleton, or each separate mesh.
    # Must be done here, after skinning and bind pose has been used.
    (modelPosition, modelRotation, modelScale) = \
        utilityCreatePRS(model.Position(), model.Rotation(), model.Scale())

    if jointTransform:
        utilitySetPRS(jointTransform, modelPosition, modelRotation, modelScale)
    else:
        utilitySetPRS(meshTransform, modelPosition, modelRotation, modelScale)


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
    keyFrameBuffer = node.KeyFrameBuffer()
    keyValueBuffer = node.KeyValueBuffer()

    # Special case for blend shapes because it requires one curve to N deformer(s).
    if propertyName == "bs":
        return utilityImportBlendShapeTrackData(nodeName, timeUnit, startFrame, keyFrameBuffer, keyValueBuffer)

    smallestFrame = OpenMaya.MTime(sys.maxsize, timeUnit)
    largestFrame = OpenMaya.MTime(0, timeUnit)

    if not propertyName in propertySwitcher:
        return (smallestFrame, largestFrame)

    tracks = [utilityGetOrCreateCurve(
        nodeName, x, typeSwitcher[propertyName]) for x in propertySwitcher[propertyName]]

    if tracks is None:
        return (smallestFrame, largestFrame)

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

    # Pick the closest supported framerate.
    wantedFps = utilityFramerateToUnit(node.Framerate())

    # Configure the scene framerate.
    OpenMaya.MTime.setUIUnit(wantedFps)

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

    for i, x in enumerate(curves):
        (smallestFrame, largestFrame) = importCurveNode(x,
                                                        path,
                                                        wantedFps,
                                                        startFrame,
                                                        curveModeOverrides)

        wantedSmallestFrame = min(smallestFrame, wantedSmallestFrame)
        wantedLargestFrame = max(largestFrame, wantedLargestFrame)

        utilityStepProgress(progress,
                            "Importing curve [%d] of [%d]..." % (i + 1, len(curves)))

    utilityEndProgress(progress)

    notifications = node.Notifications()

    for x in notifications:
        (smallestFrame, largestFrame) = importNotificationTrackNode(x,
                                                                    wantedFps,
                                                                    startFrame)

        wantedSmallestFrame = min(smallestFrame, wantedSmallestFrame)
        wantedLargestFrame = max(largestFrame, wantedLargestFrame)

    # Sync the notetrack editor if we imported any notetracks.
    if notifications:
        utilitySyncNotetracks()

    # Set the animation segment
    if wantedSmallestFrame == OpenMaya.MTime(sys.maxsize, wantedFps):
        wantedSmallestFrame = OpenMaya.MTime(0, wantedFps)

    sceneAnimationController.setAnimationStartEndTime(
        wantedSmallestFrame, wantedLargestFrame)
    sceneAnimationController.setMinMaxTime(
        wantedSmallestFrame, wantedLargestFrame)
    sceneAnimationController.setCurrentTime(wantedSmallestFrame)


def importInstanceNodes(nodes, path, sceneRoot):
    try:
        overrideCursor = utilityResetCursor()

        if sceneRoot:
            root = os.path.dirname(path)
            rootPath = os.path.join(root, sceneRoot)
            rootPath = os.path.normpath(rootPath)

            if not os.path.isdir(rootPath):
                rootPath = None

        if not rootPath:
            rootPath = cmds.fileDialog2(
                caption="Select the root directory where instance scenes are located", dialogStyle=2, startingDirectory=path, fileMode=3, okCaption="Import")

            if rootPath is None:
                return cmds.error("Unable to import instances without a root directory!")

            rootPath = rootPath[0]
    finally:
        if overrideCursor:
            utilitySetWaitCursor()

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

            transform = OpenMaya.MFnTransform(utilityGetDagPath(newInstance))

            (position, rotation, scale) = \
                utilityCreatePRS(instance.Position(),
                                 instance.Rotation(), instance.Scale())

            utilitySetPRS(transform, position, rotation, scale)

            cmds.parent(newInstance, instanceGroup.fullPathName())

        cmds.parent(base, baseGroup.fullPathName())

    cmds.setAttr("%s.visibility" % baseGroup.fullPathName(), False)


def importMetadata(meta):
    if sceneSettings["importAxis"]:
        axis = meta.UpAxis()

        if axis == "y" or axis == "z":
            currentAxis = cmds.upAxis(q=True, ax=True)

            if currentAxis != axis:
                cmds.upAxis(ax=axis, rv=True)
        elif axis:
            cmds.warning("Up axis '%s' not supported!" % axis)


def importCast(path):
    cast = Cast.load(path)

    instances = []
    meta = None

    for root in cast.Roots():
        for child in root.ChildrenOfType(Model):
            importModelNode(child, path)
        for child in root.ChildrenOfType(Animation):
            importAnimationNode(child, path)
        for child in root.ChildrenOfType(Instance):
            instances.append(child)

        # Grab the first defined meta node, if there is one.
        meta = meta or root.ChildOfType(Metadata)

    if meta:
        sceneRoot = meta.SceneRoot()
    else:
        sceneRoot = None

    if instances:
        importInstanceNodes(instances, path, sceneRoot)

    if meta:
        importMetadata(meta)


def exportAnimation(root, exportSelected):
    animation = root.CreateAnimation()
    animation.SetFramerate(utilityUnitToFramerate(OpenMaya.MTime.uiUnit()))
    animation.SetLooping(
        cmds.playbackOptions(query=True, loop=True) == "continuous")

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

    # Grab objects which are able to be exported.
    objects = cmds.ls(type="joint", selection=exportSelected)

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
        # Check if we're baking every keyframe.
        if sceneSettings["bakeKeyframes"]:
            keyframes = list(xrange(startFrame, endFrame + 1))

            for property in simpleProperties:
                exportable.append(
                    [object, property[0], property[1], keyframes])

            exportable.append([object, "rotate", "rq", keyframes])
            continue

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

                quat = OpenMaya.MEulerRotation(
                    euler[0], euler[1], euler[2]).asQuaternion()
                quatJo = OpenMaya.MEulerRotation(
                    eulerJo[0], eulerJo[1], eulerJo[2]).asQuaternion()

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

        utilityStepProgress(progress, "Exporting animation...")
    utilityEndProgress(progress)

    # Collect and create notification tracks.
    notifications = utilityGetNotetracks()

    for note in notifications:
        notetrack = animation.CreateNotification()
        notetrack.SetName(note)
        notetrack.SetKeyFrameBuffer([int(x) for x in notifications[note]])


def exportModel(root, exportSelected, filePath):
    model = root.CreateModel()

    # Grab all selected, or objects that can be exported.
    objects = OpenMaya.MSelectionList()

    if exportSelected:
        OpenMaya.MGlobal.getActiveSelectionList(objects)
    else:
        mel.eval("select -r `ls -type joint`;")
        mel.eval("string $transforms[] = `ls -tr`;"
                 "string $meshes[] = `filterExpand -sm 12 $transforms`;"
                 "select -add $meshes")
        OpenMaya.MGlobal.getActiveSelectionList(objects)

    parentStack = []

    uniqueBoneIndex = 0
    uniqueBones = {}

    for i in xrange(objects.length()):
        dependNode = OpenMaya.MObject()

        objects.getDependNode(i, dependNode)

        if not dependNode.hasFn(OpenMaya.MFn.kJoint):
            continue

        jointPathName = OpenMaya.MFnDagNode(dependNode).fullPathName()
        joint = OpenMayaAnim.MFnIkJoint(utilityGetDagPath(jointPathName))
        jointName = joint.name()

        if jointName in uniqueBones:
            continue

        parentStack.append((jointName, utilityBoneParent(joint)))

        worldPosition = joint.getTranslation(OpenMaya.MSpace.kWorld)
        localPosition = joint.getTranslation(OpenMaya.MSpace.kTransform)

        worldRotation = OpenMaya.MQuaternion()
        localRotation = OpenMaya.MQuaternion()
        localOrientation = OpenMaya.MQuaternion()

        joint.getRotation(worldRotation, OpenMaya.MSpace.kWorld)
        joint.getRotation(localRotation, OpenMaya.MSpace.kTransform)
        joint.getOrientation(localOrientation)

        localRotation = localRotation * localOrientation

        scale = OpenMaya.MScriptUtil()
        scale.createFromList([1.0, 1.0, 1.0], 3)
        scalePtr = scale.asDoublePtr()

        joint.getScale(scalePtr)

        segmentScaleCompensate = \
            bool(cmds.getAttr("%s.segmentScaleCompensate" % joint.fullPathName()))

        uniqueBones[jointName] = [
            # Parent index in the parent stack.
            -1,
            # Segment scale compensate.
            segmentScaleCompensate,
            # World position.
            (worldPosition.x, worldPosition.y, worldPosition.z),
            (localPosition.x, localPosition.y, localPosition.z),
            # World rotation.
            (worldRotation.x, worldRotation.y,
             worldRotation.z, worldRotation.w),
            # Local rotation.
            (localRotation.x, localRotation.y,
             localRotation.z, localRotation.w),
            # Scale.
            (scale.getDoubleArrayItem(scalePtr, 0),
             scale.getDoubleArrayItem(scalePtr, 1),
             scale.getDoubleArrayItem(scalePtr, 2)),
            # Index in the final bone array.
            0]

    for (boneName, boneParent) in parentStack:
        if boneParent:
            uniqueBones[boneName][0] = \
                utilityBoneIndex(parentStack, boneParent)

    if parentStack:
        skeleton = model.CreateSkeleton()

        for (boneName, _) in parentStack:
            joint = uniqueBones[boneName]
            joint[7] = uniqueBoneIndex

            uniqueBoneIndex += 1

            bone = skeleton.CreateBone()
            bone.SetName(boneName)
            bone.SetParentIndex(joint[0])
            bone.SetSegmentScaleCompensate(joint[1])

            bone.SetWorldPosition(joint[2])
            bone.SetLocalPosition(joint[3])

            bone.SetWorldRotation(joint[4])
            bone.SetLocalRotation(joint[5])

            bone.SetScale(joint[6])

    uniqueMeshes = set()
    uniqueMaterials = {}

    for i in xrange(objects.length()):
        dependNode = OpenMaya.MObject()

        objects.getDependNode(i, dependNode)

        if not dependNode.hasFn(OpenMaya.MFn.kTransform):
            continue

        transformPathName = OpenMaya.MFnDagNode(dependNode).fullPathName()
        transformDagPath = utilityGetDagPath(transformPathName)

        try:
            transformDagPath.extendToShape()
        except RuntimeError:
            continue

        meshPath = transformDagPath.partialPathName()
        mesh = OpenMaya.MFnMesh(transformDagPath)
        meshName = mesh.name()

        if meshPath in uniqueMeshes:
            continue

        uniqueMeshes.add(meshPath)

        meshNode = model.CreateMesh()

        if not meshName.startswith("CastShape"):
            meshNode.SetName(meshName)

        # Collect, deduplicate materials.
        material = utilityGetMaterial(mesh, transformDagPath)

        if material:
            if material in uniqueMaterials:
                meshNode.SetMaterial(uniqueMaterials[material])
            else:
                matNode = model.CreateMaterial()
                matNode.SetName(material)
                matNode.SetType("pbr")

                utilityQueryMaterialSlots(material, matNode, filePath)

                uniqueMaterials[material] = matNode.Hash()

                meshNode.SetMaterial(uniqueMaterials[material])

        # Collect uv layers for this mesh.
        uvLayers = \
            cmds.polyUVSet(meshPath,
                           q=True, allUVSets=True)
        # Collect color layers for this mesh.
        colorLayers = \
            cmds.polyColorSet(meshPath,
                              q=True, allColorSets=True)

        # Find the skin cluster for this mesh.
        skinCluster = utilityGetSkinCluster(transformDagPath)
        skinJoints = OpenMaya.MDagPathArray()

        if skinCluster:
            skinCluster.influenceObjects(skinJoints)

        vertexIter = OpenMaya.MItMeshVertex(transformDagPath)
        vertexCount = vertexIter.count()

        vertexPositions = [None] * vertexCount
        vertexNormals = [None] * vertexCount
        vertexUVLayers = [[None] * vertexCount for _ in uvLayers]
        vertexColorLayers = [[None] * vertexCount for _ in colorLayers]
        vertexMaxInfluence = 0

        normal = OpenMaya.MVector()
        uv = OpenMaya.MScriptUtil()
        color = OpenMaya.MColor()

        numWeights = OpenMaya.MScriptUtil()
        numWeightsPtr = numWeights.asUintPtr()
        weights = OpenMaya.MDoubleArray()
        bones = [0] * skinJoints.length()

        # Create weight index to bone index lookup.
        for index in xrange(skinJoints.length()):
            jointDagPath = skinJoints[index]

            if not jointDagPath.hasFn(OpenMaya.MFn.kJoint):
                cmds.warning("Skipping non-joint influence object: %s" %
                             jointDagPath.partialPathName())
                continue

            joint = OpenMayaAnim.MFnIkJoint(jointDagPath)
            jointName = joint.name()

            try:
                bones[index] = uniqueBones[jointName][7]
            except KeyError:
                cmds.warning("Skipping joint not in skeleton: %s" % jointName)
                pass

        uv.createFromList([0.0, 0.0], 2)
        uvPtr = uv.asFloat2Ptr()

        while not vertexIter.isDone():
            index = vertexIter.index()

            position = vertexIter.position(OpenMaya.MSpace.kWorld)

            vertexPositions[index] = \
                (position.x, position.y, position.z)

            vertexIter.getNormal(normal)

            vertexNormals[index] = \
                (normal.x, normal.y, normal.z)

            for i, uvLayer in enumerate(uvLayers):
                vertexIter.getUV(uvPtr, uvLayer)

                vertexUVLayers[i][index] = \
                    (OpenMaya.MScriptUtil.getFloat2ArrayItem(uvPtr, 0, 0),
                     1.0 - OpenMaya.MScriptUtil.getFloat2ArrayItem(uvPtr, 0, 1))

            for i, colorLayer in enumerate(colorLayers):
                vertexIter.getColor(color, colorLayer)

                vertexColorLayers[i][index] = \
                    (color.r, color.g, color.b, color.a)

            if skinCluster:
                skinCluster.getWeights(transformDagPath,
                                       vertexIter.currentItem(),
                                       weights,
                                       numWeightsPtr)

                # Calculate the maximum influence for this vertex.
                influence = 0

                for vindex in xrange(weights.length()):
                    if weights[vindex] > WEIGHT_THRESHOLD:
                        influence += 1

                vertexMaxInfluence = max(vertexMaxInfluence, influence)

            vertexIter.next()

        if vertexMaxInfluence > 0:
            vertexWeightValueBuffer = [0.0] * vertexCount * vertexMaxInfluence
            vertexWeightBoneBuffer = [0] * vertexCount * vertexMaxInfluence

            vertexIter.reset()

            while not vertexIter.isDone():
                index = vertexIter.index()

                skinCluster.getWeights(transformDagPath,
                                       vertexIter.currentItem(),
                                       weights,
                                       numWeightsPtr)

                slot = 0

                for vindex in xrange(weights.length()):
                    if weights[vindex] > WEIGHT_THRESHOLD:
                        vertexWeightValueBuffer[(
                            index * vertexMaxInfluence) + slot] = weights[vindex]
                        vertexWeightBoneBuffer[(
                            index * vertexMaxInfluence) + slot] = bones[vindex]

                        slot += 1

                vertexIter.next()

            meshNode.SetMaximumWeightInfluence(vertexMaxInfluence)
            meshNode.SetVertexWeightValueBuffer(vertexWeightValueBuffer)
            meshNode.SetVertexWeightBoneBuffer(vertexWeightBoneBuffer)

        meshNode.SetVertexPositionBuffer(vertexPositions)
        meshNode.SetVertexNormalBuffer(vertexNormals)

        for uvLayer, vertexUVs in enumerate(vertexUVLayers):
            meshNode.SetVertexUVLayerBuffer(uvLayer, vertexUVs)

        meshNode.SetUVLayerCount(len(vertexUVLayers))

        for colorLayer, vertexColors in enumerate(vertexColorLayers):
            meshNode.SetVertexColorBuffer(colorLayer, vertexColors)

        meshNode.SetColorLayerCount(len(vertexColorLayers))

        faceCounts = OpenMaya.MIntArray()
        faceIndices = OpenMaya.MIntArray()

        # Automatically converts n-gons to triangle faces.
        mesh.getTriangles(faceCounts, faceIndices)

        faceBuffer = [0] * faceIndices.length()

        for i in xrange(faceIndices.length()):
            faceBuffer[i] = faceIndices[i]

        meshNode.SetFaceBuffer(faceBuffer)


def exportCast(path, exportSelected):
    # Query current user settings so we can reset them after the operation completes.
    currentAngle = cmds.currentUnit(query=True, angle=True)

    try:
        cast = Cast()
        root = cast.CreateRoot()

        meta = root.CreateMetadata()
        meta.SetSoftware("Cast v%s for %s" %
                         (version, cmds.about(product=True)))

        if sceneSettings["exportAxis"]:
            meta.SetUpAxis(cmds.upAxis(query=True, ax=True))

        cmds.currentUnit(angle="rad")

        if sceneSettings["exportAnim"]:
            exportAnimation(root, exportSelected)

        if sceneSettings["exportModel"]:
            exportModel(root, exportSelected, path)

        cast.save(path)
    finally:
        # Reset scene units back to user setting.
        cmds.currentUnit(angle=currentAngle)


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
        m_plugin.registerFileTranslator("Cast", None, createCastTranslator)
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
