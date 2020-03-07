import os
import os.path
from cast import Cast, Model, Mesh, Skeleton, Bone, Material, File
import maya.mel as mel
import maya.cmds as cmds
import maya.OpenMaya as OpenMaya
import maya.OpenMayaAnim as OpenMayaAnim
import maya.OpenMayaMPx as OpenMayaMPx

# Support Python 3.0+
if xrange is None:
    xrange = range


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

    for mesh in model.Meshes():
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

        if maximumInfluence > 0:
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


def importRootNode(node, path):
    for child in node.ChildrenOfType(Model):
        importModelNode(child, path)
    # TODO: We would import animations here once we create
    # a type to load from


def importCast(path):
    cast = Cast()
    cast.load(path)

    for root in cast.Roots():
        importRootNode(root, path)


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
    # __create_menu__()


def uninitializePlugin(m_object):
    m_plugin = OpenMayaMPx.MFnPlugin(m_object)
    try:
        m_plugin.deregisterFileTranslator("Cast")
    except RuntimeError:
        pass
    # __remove_menu__()
