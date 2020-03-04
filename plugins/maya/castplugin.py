import os
import os.path
from cast import Cast, Model, Mesh, Skeleton, Bone, Material
import maya.mel as mel
import maya.cmds as cmds
import maya.OpenMaya as OpenMaya
import maya.OpenMayaAnim as OpenMayaAnim
import maya.OpenMayaMPx as OpenMayaMPx

# Support Python 3.0+
if xrange is None:
    xrange = range


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


def importMaterialNode(material):
    # If you already created the material, ignore this
    if cmds.objExists(material.Name()):
        return material.Name()

    materialNew = cmds.shadingNode(
        "lambert", asShader=True, name=material.Name())
    materialGroup = cmds.sets(
        renderable=True, empty=True, name=("%sSG" % materialNew))

    # Connect shader -> surface
    cmds.connectAttr(("%s.outColor" % materialNew),
                     ("%s.surfaceShader" % materialGroup), force=True)

    # TODO: Convert dynamic texture slots to shader mapping
    return material.Name()


def importModelNode(model, path):
    # Import skeleton for binds, materials for meshes
    (handles, paths) = importSkeletonNode(model.Skeleton())
    materials = [importMaterialNode(x) for x in model.Materials()]

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
