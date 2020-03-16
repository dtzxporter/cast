import os
import os.path
import json
from cast import Cast, Model, Animation, Curve, NotificationTrack, Mesh, Skeleton, Bone, Material, File
import maya.mel as mel
import maya.cmds as cmds
import maya.OpenMaya as OpenMaya
import maya.OpenMayaAnim as OpenMayaAnim
import maya.OpenMayaMPx as OpenMayaMPx

# Support Python 3.0+
if xrange is None:
    xrange = range

# Used for scene reset cache
sceneResetCache = {}

# Used for various configuration
sceneSettings = {
    "importAtTime": False,
    "importSkin": True,
}


def utilityRemoveNamespaces():
    namespaceController = OpenMaya.MNamespace()
    namespaces = namespaceController.getNamespaces(True)

    for namespace in namespaces:
        try:
            mel.eval(
                "namespace -removeNamespace \"%s\" -mergeNamespaceWithRoot;" % namespace)
        except RuntimeError:
            pass


def utilitySetToggleItem(name, value=False):
    if sceneSettings.has_key(name):
        sceneSettings[name] = bool(
            cmds.menuItem(name, query=True, checkBox=True))

    utilitySaveSettings()


def utilityQueryToggleItem(name):
    if sceneSettings.has_key(name):
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
        if sceneSettings.has_key(key):
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

    cmds.setParent(animMenu, menu=True)
    cmds.setParent(menu, menu=True)

    modelMenu = cmds.menuItem(label="Model", subMenu=True)

    cmds.menuItem("importSkin", label="Import Bind Skin", annotation="Imports and binds a model to it's smooth skin",
                  checkBox=utilityQueryToggleItem("importSkin"), command=lambda x: utilitySetToggleItem("importSkin"))

    cmds.setParent(animMenu, menu=True)
    cmds.setParent(menu, menu=True)
    cmds.menuItem(divider=True)

    cmds.menuItem(label="Remove Namespaces", annotation="Removes all namespaces in the scene",
                  command=lambda x: utilityRemoveNamespaces())

    cmds.menuItem(divider=True)

    cmds.menuItem(label="Reset Scene", annotation="Resets the scene, removing the current animation curves",
                  command=lambda x: utilityClearAnimation())


def utilityClearAnimation():
    # First we must remove all existing animation curves
    # this deletes all curve channels
    global sceneResetCache

    cmds.delete(all=True, c=True)

    for transPath in sceneResetCache:
        selectList = OpenMaya.MSelectionList()
        selectList.add(transPath)

        dagPath = OpenMaya.MDagPath()
        selectList.getDagPath(0, dagPath)

        transform = OpenMaya.MFnTransform(dagPath)
        transform.resetFromRestPosition()

    sceneResetCache = {}


def utilityCreateSkinCluster(newMesh, bones=[], maxWeightInfluence=1):
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

    return OpenMayaAnim.MFnSkinCluster(clusterObject)


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
        "roughness": "TEX_roughness_map",
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
        if not switcher.has_key(slot):
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
        if not switcher.has_key(slot):
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

    if not switcher.has_key(type):
        type = None

    mayaShaderType = switcher[type]
    if cmds.getClassification(mayaShaderType) == [u'']:
        mayaShaderType = switcher[None]

    materialInstance = cmds.shadingNode(
        mayaShaderType, asShader=True, name=name)

    loader[mayaShaderType](materialInstance, slots, path)

    return (materialInstance)


def utilitySaveNodeData(dagPath, rotationTrack):
    global sceneResetCache

    if dagPath.fullPathName() in sceneResetCache:
        return

    sceneResetCache[dagPath.fullPathName()] = None

    # We are going to save the rest position on the node
    # so we can reset the scene later
    transform = OpenMaya.MFnTransform(dagPath)
    transform.setRestPosition(transform.transformation())

    # Set the orientation to 0 since we animate on the rotation transform
    if rotationTrack and cmds.objExists("%s.jo" % dagPath.fullPathName()):
        cmds.setAttr("%s.jo" % dagPath.fullPathName(), 0, 0, 0)


def utilityGetOrCreateCurve(name, property, curveType):
    if not cmds.objExists("%s.%s" % (name, property)):
        return None

    selectList = OpenMaya.MSelectionList()
    selectList.add(name)

    try:
        nodePath = OpenMaya.MDagPath()
        selectList.getDagPath(0, nodePath)
    except RuntimeError:
        return None

    utilitySaveNodeData(nodePath, property in ["rx", "ry", "rz"])

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
        return newCurve
    elif inputSources[0].node().hasFn(OpenMaya.MFn.kAnimCurve):
        # There is an existing curve on this node, we need to
        # grab the curve, but then reset the rotation interpolation
        newCurve = OpenMayaAnim.MFnAnimCurve()
        newCurve.setObject(inputSources[0].node())

        # If we have a rotation curve, it's interpolation must be reset before keying
        if property in ["rx", "ry", "rz"] and utilityGetCurveInterpolation(newCurve.name()) != "none":
            utilitySetCurveInterpolation(newCurve.name())

        # Return the existing curve
        return newCurve

    return None


def utilityImportQuatTrackData(tracks, timeUnit, frameBuffer, valueBuffer):
    timeBuffer = OpenMaya.MTimeArray()
    smallestFrame = OpenMaya.MTime()
    largestFrame = OpenMaya.MTime()

    for x in frameBuffer:
        frame = OpenMaya.MTime(x, timeUnit)
        if frame < smallestFrame:
            smallestFrame = frame
        if frame > largestFrame:
            largestFrame = frame
        timeBuffer.append(frame)

    tempBufferX = OpenMaya.MScriptUtil()
    tempBufferY = OpenMaya.MScriptUtil()
    tempBufferZ = OpenMaya.MScriptUtil()

    if timeBuffer.length() <= 0:
        return (smallestFrame, largestFrame)

    valuesX = [0.0] * timeBuffer.length()
    valuesY = [0.0] * timeBuffer.length()
    valuesZ = [0.0] * timeBuffer.length()

    for i in xrange(0, len(valueBuffer), 4):
        euler = OpenMaya.MQuaternion(
            valueBuffer[i], valueBuffer[i + 1], valueBuffer[i + 2], valueBuffer[i + 3]).asEulerRotation()
        slot = i / 4
        valuesX[slot] = euler.x
        valuesY[slot] = euler.y
        valuesZ[slot] = euler.z

    tempBufferX.createFromList(valuesX, len(valuesX))
    tempBufferY.createFromList(valuesY, len(valuesY))
    tempBufferZ.createFromList(valuesZ, len(valuesZ))

    if tracks[0] is not None:
        tracks[0].addKeys(timeBuffer, OpenMaya.MDoubleArray(tempBufferX.asDoublePtr(), timeBuffer.length(
        )), OpenMayaAnim.MFnAnimCurve.kTangentLinear, OpenMayaAnim.MFnAnimCurve.kTangentLinear)

    if tracks[1] is not None:
        tracks[1].addKeys(timeBuffer, OpenMaya.MDoubleArray(tempBufferY.asDoublePtr(), timeBuffer.length(
        )), OpenMayaAnim.MFnAnimCurve.kTangentLinear, OpenMayaAnim.MFnAnimCurve.kTangentLinear)

    if tracks[2] is not None:
        tracks[2].addKeys(timeBuffer, OpenMaya.MDoubleArray(tempBufferZ.asDoublePtr(), timeBuffer.length(
        )), OpenMayaAnim.MFnAnimCurve.kTangentLinear, OpenMayaAnim.MFnAnimCurve.kTangentLinear)

    return (smallestFrame, largestFrame)


def utilityImportSingleTrackData(tracks, timeUnit, frameBuffer, valueBuffer):
    smallestFrame = OpenMaya.MTime()
    largestFrame = OpenMaya.MTime()

    scriptUtil = OpenMaya.MScriptUtil()
    scriptUtil.createFromList([x for x in valueBuffer], len(valueBuffer))

    timeBuffer = OpenMaya.MTimeArray()
    valueBuffer = OpenMaya.MDoubleArray(
        scriptUtil.asDoublePtr(), len(valueBuffer))

    for x in frameBuffer:
        frame = OpenMaya.MTime(x, timeUnit)
        if frame < smallestFrame:
            smallestFrame = frame
        if frame > largestFrame:
            largestFrame = frame
        timeBuffer.append(frame)

    if tracks[0] is None or timeBuffer.length() <= 0:
        return (smallestFrame, largestFrame)

    tracks[0].addKeys(timeBuffer, valueBuffer, OpenMayaAnim.MFnAnimCurve.kTangentLinear,
                      OpenMayaAnim.MFnAnimCurve.kTangentLinear)

    return (smallestFrame, largestFrame)


def importSkeletonNode(skeleton):
    if skeleton is None:
        return (None, None)

    bones = skeleton.Bones()
    handles = [None] * len(bones)
    paths = [None] * len(bones)

    jointTransform = OpenMaya.MFnTransform()
    jointNode = jointTransform.create()
    jointTransform.setName("Joints")

    for i, bone in enumerate(bones):
        newBone = OpenMayaAnim.MFnIkJoint()
        newBone.create(jointNode)
        newBone.setName(bone.Name())
        handles[i] = newBone

    for i, bone in enumerate(bones):
        if bone.ParentIndex() > -1:
            cmds.parent(handles[i].fullPathName(),
                        handles[bone.ParentIndex()].fullPathName())

    for i, bone in enumerate(bones):
        scaleUtility = OpenMaya.MScriptUtil()
        newBone = handles[i]
        paths[i] = newBone.fullPathName()

        if bone.SegmentScaleCompensate() is not None:
            segmentScale = bone.SegmentScaleCompensate()
            cmds.setAttr("%s.segmentScaleCompensate" % paths[1], segmentScale)

        if bone.LocalPosition() is not None:
            localPos = bone.LocalPosition()
            localRot = bone.LocalRotation()

            newBone.setTranslation(OpenMaya.MVector(
                localPos[0], localPos[1], localPos[2]), OpenMaya.MSpace.kTransform)
            newBone.setOrientation(OpenMaya.MQuaternion(
                localRot[0], localRot[1], localRot[2], localRot[3]))

        if bone.Scale() is not None:
            scale = bone.Scale()
            scaleUtility.createFromList([scale[0], scale[1], scale[2]], 3)
            newBone.setScale(scaleUtility.asDoublePtr())

    return (handles, paths)


def importMaterialNode(path, material):
    # If you already created the material, ignore this
    if cmds.objExists(material.Name()):
        return material.Name()

    # Create the material and assign slots
    (materialNew) = utilityCreateMaterial(
        material.Name(), material.Type(), material.Slots(), path)

    # Create the shader group that connects to a surface
    materialGroup = cmds.sets(
        renderable=True, empty=True, name=("%sSG" % materialNew))

    # Connect shader -> surface
    cmds.connectAttr(("%s.outColor" % materialNew),
                     ("%s.surfaceShader" % materialGroup), force=True)

    return material.Name()


def importModelNode(model, path):
    # Import skeleton for binds, materials for meshes
    (handles, paths) = importSkeletonNode(model.Skeleton())
    materials = [importMaterialNode(path, x) for x in model.Materials()]

    # Import the meshes
    meshTransform = OpenMaya.MFnTransform()
    meshNode = meshTransform.create()
    meshTransform.setName(os.path.splitext(os.path.basename(path))[0])

    meshes = model.Meshes()
    progress = utilityCreateProgress("Importing model...", len(meshes))

    for mesh in meshes:
        newMeshTransform = OpenMaya.MFnTransform()
        newMeshNode = newMeshTransform.create(meshNode)
        newMeshTransform.setName("CastMesh")

        # Triangle count / vertex count
        faceCount = mesh.FaceCount()
        vertexCount = mesh.VertexCount()

        faces = mesh.FaceBuffer()
        scriptUtil = OpenMaya.MScriptUtil()
        scriptUtil.createFromList([x for x in faces], len(faces))

        faceBuffer = OpenMaya.MIntArray(scriptUtil.asIntPtr(), len(faces))
        faceCountBuffer = OpenMaya.MIntArray(faceCount, 3)

        vertexPositions = mesh.VertexPositionBuffer()
        scriptUtil = OpenMaya.MScriptUtil()
        scriptUtil.createFromList([x for y in (vertexPositions[i:i + 3] + tuple([1.0]) * (i < len(
            vertexPositions) - 2) for i in xrange(0, len(vertexPositions), 3)) for x in y], vertexCount)

        vertexPositionBuffer = OpenMaya.MFloatPointArray(
            scriptUtil.asFloat4Ptr(), vertexCount)

        newMesh = OpenMaya.MFnMesh()
        newMesh.create(vertexCount, faceCount, vertexPositionBuffer,
                       faceCountBuffer, faceBuffer, newMeshNode)

        vertexNormals = mesh.VertexNormalBuffer()
        scriptUtil = OpenMaya.MScriptUtil()
        scriptUtil.createFromList(
            [x for x in vertexNormals], len(vertexNormals))

        vertexNormalBuffer = OpenMaya.MVectorArray(
            scriptUtil.asFloat3Ptr(), len(vertexNormals) / 3)

        scriptUtil = OpenMaya.MScriptUtil()
        scriptUtil.createFromList(
            [x for x in xrange(vertexCount)], vertexCount)

        vertexIndexBuffer = OpenMaya.MIntArray(
            scriptUtil.asIntPtr(), vertexCount)

        newMesh.setVertexNormals(vertexNormalBuffer, vertexIndexBuffer)

        vertexColors = mesh.VertexColorBuffer()
        scriptUtil = OpenMaya.MScriptUtil()
        scriptUtil.createFromList([x for xs in [[(x >> i & 0xff) / 255.0 for i in (
            24, 16, 8, 0)] for x in vertexColors] for x in xs], len(vertexColors) * 4)

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
                    "%sSG" % meshMaterial.Name()))
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

        if maximumInfluence > 0 and sceneSettings["importSkin"]:
            weightBoneBuffer = mesh.VertexWeightBoneBuffer()
            weightValueBuffer = mesh.VertexWeightValueBuffer()
            weightedBones = list({paths[x] for x in weightBoneBuffer})
            weightedBonesCount = len(weightedBones)

            skinCluster = utilityCreateSkinCluster(
                newMesh, weightedBones, maximumInfluence)

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
                        weightedValueBuffer[weightedRemap[weightBoneBuffer[j + (
                            i * maximumInfluence)]]] = weightValueBuffer[j + (i * maximumInfluence)]

                cmds.setAttr(clusterAttrPayload, *weightedValueBuffer)
                weightedValueBuffer = [0.0] * (weightedBonesCount)

        utilityStepProgress(progress)
    utilityEndProgress(progress)


def importCurveNode(node, path, timeUnit, transformSpace):
    propertySwitcher = {
        # This is special, maya can't animate a quat separate
        "rq": ["rx", "ry", "rz"],
        "rx": ["rx"],
        "ry": ["ry"],
        "rz": ["rz"],
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
        "rx": OpenMayaAnim.MFnAnimCurve.kAnimCurveTA,
        "ry": OpenMayaAnim.MFnAnimCurve.kAnimCurveTA,
        "rz": OpenMayaAnim.MFnAnimCurve.kAnimCurveTA,
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
        "rx": utilityImportSingleTrackData,
        "ry": utilityImportSingleTrackData,
        "rz": utilityImportSingleTrackData,
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

    if not propertySwitcher.has_key(propertyName):
        return

    tracks = [utilityGetOrCreateCurve(
        nodeName, x, typeSwitcher[propertyName]) for x in propertySwitcher[propertyName]]

    keyFrameBuffer = node.KeyFrameBuffer()
    keyValueBuffer = node.KeyValueBuffer()

    (smallestFrame, largestFrame) = trackSwitcher[propertyName](
        tracks, timeUnit, keyFrameBuffer, keyValueBuffer)

    # Make sure we have at least one quaternion track to set the interpolation mode to
    if propertyName == "rq":
        for track in tracks:
            if track is not None:
                utilitySetCurveInterpolation(track.name(), "quaternion")

    # Return the frame sizes [s, l] so we can adjust the scene times
    return (smallestFrame, largestFrame)


def importAnimationNode(node, path):
    # We need to be sure to disable auto keyframe, because it breaks import of animations
    # do this now so we don't forget...
    sceneAnimationController = OpenMayaAnim.MAnimControl()
    sceneAnimationController.setAutoKeyMode(False)

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

    if switcherFps.has_key(int(node.Framerate())):
        wantedFps = switcherFps[int(node.Framerate())]
    else:
        wantedFps = switcherFps[None]

    # We need to determine the proper time to import the curves, for example
    # the user may want to import at the current scene time, and that would require
    # fetching once here, then passing to the curve importer.
    wantedSmallestFrame = OpenMaya.MTime(0, wantedFps)
    wantedLargestFrame = OpenMaya.MTime(1, wantedFps)

    curves = node.ChildrenOfType(Curve)
    progress = utilityCreateProgress("Importing animation...", len(curves))

    for x in curves:
        (smallestFrame, largestFrame) = importCurveNode(
            x, path, wantedFps, node.TransformSpace())
        if smallestFrame < wantedSmallestFrame:
            wantedSmallestFrame = smallestFrame
        if largestFrame > wantedLargestFrame:
            wantedLargestFrame = largestFrame
        utilityStepProgress(progress)

    utilityEndProgress(progress)

    # Set the animation segment
    sceneAnimationController.setAnimationStartEndTime(
        wantedSmallestFrame, wantedLargestFrame)
    sceneAnimationController.setMinMaxTime(
        wantedSmallestFrame, wantedLargestFrame)


def importRootNode(node, path):
    for child in node.ChildrenOfType(Model):
        importModelNode(child, path)
    for child in node.ChildrenOfType(Animation):
        importAnimationNode(child, path)


def importCast(path):
    cast = Cast()
    cast.load(path)

    for root in cast.Roots():
        importRootNode(root, path)


class CastFileTranslator(OpenMayaMPx.MPxFileTranslator):
    def __init__(self):
        OpenMayaMPx.MPxFileTranslator.__init__(self)

    def haveWriteMethod(self):
        return False

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
        print("TODO: Implement")

    def reader(self, fileObject, optionString, accessMode):
        importCast(fileObject.fullName())


def createCastTranslator():
    return OpenMayaMPx.asMPxPtr(CastFileTranslator())


def initializePlugin(m_object):
    m_plugin = OpenMayaMPx.MFnPlugin(m_object, "DTZxPorter", "1.0", "Any")
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
