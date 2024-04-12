import c4d
import os
import array
import math
from c4d import plugins, bitmaps, Vector, gui, BaseObject
import mxutils

resDir = os.path.join(os.path.dirname(__file__), "res")
mxutils.ImportSymbols(resDir)
with mxutils.LocalImportPath(resDir):
    from cast import Cast, CastColor, Model, Animation, Instance, File

__pluginname__ = "Cast"

class CastLoader(plugins.SceneLoaderData):
    def Identify(self, node, name, probe, size):
        if "cast" in name[-4:]:
            return True
        return False

    def Load(self, node, name, doc, filterflags, error, bt):
        importCast(doc, node, name)
        return c4d.FILEERROR_NONE

def importCast(doc, node, path):
    cast = Cast.load(path)

    instances = []

    for root in cast.Roots():
        for child in root.ChildrenOfType(Model):
            importModelNode(doc, node, child, path)
        for child in root.ChildrenOfType(Animation):
            importAnimationNode(doc, child, path)
        for child in root.ChildrenOfType(Instance):
            instances.append(child)

    if len(instances) > 0:
        importInstanceNodes(doc, instances, path)
        
"""
We are using Blender unpack_list for convinience
https://github.com/blender/blender/blob/main/scripts/modules/bpy_extras/io_utils.py#L370
"""
def unpack_list(list_of_tuples):
    flat_list = []
    flat_list_extend = flat_list.extend  # a tiny bit faster
    for t in list_of_tuples:
        flat_list_extend(t)
    return flat_list

def utilityQuaternionToEuler(q):
    x, y, z, w = q
    sinr_cosp = 2 * (w * x + y * z)
    cosr_cosp = 1 - 2 * (x * x + y * y)
    roll = math.atan2(sinr_cosp, cosr_cosp)

    sinp = 2 * (w * y - z * x)
    if abs(sinp) >= 1:
        pitch = math.copysign(math.pi / 2, sinp)
    else:
        pitch = math.asin(sinp)

    siny_cosp = 2 * (w * z + x * y)
    cosy_cosp = 1 - 2 * (y * y + z * z)
    yaw = math.atan2(siny_cosp, cosy_cosp)

    return roll, pitch, -yaw

def utilityAddTextureMaterialSlots(slotName, texPath, mat, shaderType):
    shader = c4d.BaseList2D(c4d.Xbitmap)
    shader[c4d.BITMAPSHADER_FILENAME] = texPath
    shader.SetName(slotName)
    if slotName == "normal":
        mat[c4d.MATERIAL_USE_NORMAL] = True
        shader[c4d.BITMAPSHADER_COLORPROFILE] = 1  # Linear color space

    mat[shaderType] = shader
    mat.InsertShader(shader)

def utilityAssignMaterialSlots(doc, material, slots, path):
    switcher = {
        "albedo": c4d.MATERIAL_COLOR_SHADER,
        "diffuse": c4d.MATERIAL_COLOR_SHADER,
        "normal": c4d.MATERIAL_NORMAL_SHADER
    }

    for slot in slots:
        connection = slots[slot]
        if not connection.__class__ is File:
            continue
        if not slot in switcher:
            continue

        texturePath = os.path.dirname(path) + "\\" + connection.Path()
        utilityAddTextureMaterialSlots(slot, texturePath, material, switcher[slot])

def utilityWriteNormalTag(tag, normalList):
    # Retrieves the write buffer array
    buffer = tag.GetLowlevelDataAddressW()
    if buffer is None:
        raise RuntimeError("Failed to retrieves internal write data for the normal tag.")

    # Translates list of short int 16 to a BitSeq (string are byte in Python 2.7)
    data = array.array('h')
    data.fromlist(normalList)
    data = data.tobytes()
    buffer[:len(data)] = data

def importMaterialNode(doc, path, material):
    materials = doc.GetMaterials()
    for mat in materials:
        if mat.GetName() == material.Name():
            return mat
        
    materialNew = c4d.BaseMaterial(c4d.Mmaterial)
    materialNew.SetName(material.Name())

    utilityAssignMaterialSlots(doc, materialNew, material.Slots(), path)

    doc.InsertMaterial(materialNew)
    materialNew.Message(c4d.MSG_UPDATE)

    return materialNew

def importModelNode(doc, node, model, path):

    # Extract the name of this model from the path
    modelName = model.Name() or os.path.splitext(os.path.basename(path))[0]
    # Create a collection for our objects
    modelNull = BaseObject(c4d.Onull)
    modelNull.SetName(modelName)
    doc.InsertObject(modelNull)
    # Import skeleton for binds, materials for meshes
    boneIndexes = importSkeletonNode(
        modelNull, model.Skeleton())
    materialArray = {x.Name(): importMaterialNode(doc, path, x)
                 for x in model.Materials()}

    meshes = model.Meshes()
    meshHandles = {}
    
    for mesh in meshes:
        newMesh = BaseObject(c4d.Opolygon) #c4d.CallCommand(13039) #bpy.data.meshes.new("polySurfaceMesh")
        newMesh.SetName(mesh.Name() or "CastMesh") # meshObj = bpy.data.objects.new(mesh.Name() or "CastMesh", newMesh)
        
        meshHandles[mesh.Hash()] = (newMesh)

        vertexPositions = mesh.VertexPositionBuffer()
        vertexCount = int(len(vertexPositions) / 3)
        
        faces = mesh.FaceBuffer()
        faceIndicesCount = len(faces)
        facesCount = int(faceIndicesCount / 3)
        faces = unpack_list([(faces[x + 2], faces[x + 1], faces[x + 0])
                        for x in range(0, faceIndicesCount, 3)])
        
        newMesh.ResizeObject(vertexCount, facesCount)

        # Vertice
        for i in range(0, len(vertexPositions), 3):
            vertexIndex = i // 3
            x, y, z = vertexPositions[i:i+3]
            newMesh.SetPoint(vertexIndex, Vector(x, y, -z)) # Matching the Maya default import

        # Faces
        for i in range(0, len(faces), 3):
            polyIndex = i // 3
            a, b, c = faces[i:i+3]
            newMesh.SetPolygon(polyIndex, c4d.CPolygon(a, b, c))

        # UVW
        for i in range(mesh.UVLayerCount()):
            uvTag = c4d.UVWTag(facesCount)
            uvBuffer = mesh.VertexUVLayerBuffer(0)
            uvUnpacked = unpack_list([(uvBuffer[x * 2], 1.0 - uvBuffer[(x * 2) + 1]) for x in faces])
            for i in range(0, len(uvUnpacked), 6):
                polyIndex = i // 6
                u1, v1, u2, v2, u3, v3 = uvUnpacked[i:i+6]
                uvTag.SetSlow(polyIndex, Vector(u1, 1-v1,0),
                    Vector(u2, 1-v2,0),
                    Vector(u3, 1-v3,0),
                    Vector(0,0,0))
            newMesh.InsertTag(uvTag)

        # Vertex Colors
        vertexColors = mesh.VertexColorBuffer()
        if vertexColors is not None:
            vcTag = c4d.VertexColorTag(vertexCount)
            vertexColorList = [x for xs in [CastColor.fromInteger(x) for x in vertexColors] for x in xs], len(vertexColors) * 4
            vcData = vcTag.GetDataAddressW()
            for i in range(0, len(vertexColorList[0]), 4):
                vIndex = i // 4
                r, g, b, a = vertexColorList[0][i:i+4]
                vcTag.SetPoint(vcData,None,None,vIndex,c4d.Vector4d(r, g, b, a))
            newMesh.InsertTag(vcTag)

        # Vertex Normals
        vertexNormals = mesh.VertexNormalBuffer()
        if vertexNormals is not None:
            # Yeah I don't know what I'm doing here
            normaltag = c4d.NormalTag(count=newMesh.GetPolygonCount())

            normalListUnpacked = unpack_list([(vertexNormals[x * 3], vertexNormals[(x * 3) + 1], vertexNormals[(x * 3) + 2]) for x in faces])
            normalList = [Vector(normalListUnpacked[i], normalListUnpacked[i+1], -normalListUnpacked[i+2]) for i in range(0, len(normalListUnpacked), 3)]

            # Even if it's a Tri, you should pass a value.
            for i in range(len(normalList) // 3):
                normalList.insert((i + 1) * 4 - 1, Vector(0, 0, 0))

            # Maps data from float to int16 value
            normalListToSet = [int(component * 32000.0)
                   for n in normalList for component in (n.x, n.y, n.z)]
            
            utilityWriteNormalTag(normaltag, normalListToSet)
            newMesh.InsertTag(normaltag)

        # Weight
        if model.Skeleton() is not None and node[CAST_IMPORT_BIND_SKIN]:
            skinObj = BaseObject(c4d.Oskin)
            skinningMethod = mesh.SkinningMethod()
            skinType = c4d.ID_CA_SKIN_OBJECT_TYPE
            if skinningMethod == "linear":
                skinObj[skinType] = 0
            elif skinningMethod == "quaternion":
                skinObj[skinType] = 1
            doc.InsertObject(skinObj, parent=newMesh)

            weightTag = c4d.modules.character.CAWeightTag()
            newMesh.InsertTag(weightTag)
            for key, value in boneIndexes.items():
                weightTag.AddJoint(value)
            maximumInfluence = mesh.MaximumWeightInfluence()
            if maximumInfluence > 1:  # Slower path for complex weights
                weightBoneBuffer = mesh.VertexWeightBoneBuffer()
                weightValueBuffer = mesh.VertexWeightValueBuffer()

                for x in range(vertexCount):
                    for j in range(maximumInfluence):
                            weightIndex = j + (x * maximumInfluence)
                            weightValue = weightTag.GetWeight(weightBoneBuffer[weightIndex], x)
                            weightValue += weightValueBuffer[weightIndex]
                            weightTag.SetWeight(
                                weightBoneBuffer[weightIndex],
                                x,
                                weightValue
                            )
            elif maximumInfluence > 0:  # Fast path for simple weighted meshes
                weightBoneBuffer = mesh.VertexWeightBoneBuffer()
                for x in range(len(newMesh.vertices)):
                        weightTag.SetWeight(
                            weightBoneBuffer[x],
                            x,
                            1.0
                        )
            weightTag.Message(c4d.MSG_UPDATE)
            c4d.EventAdd()

        meshMaterial = mesh.Material()
        if meshMaterial is not None:
            material = materialArray[meshMaterial.Name()]
            material_tag = newMesh.MakeTag(c4d.Ttexture)
            material_tag[c4d.TEXTURETAG_MATERIAL] = material
            material_tag[c4d.TEXTURETAG_PROJECTION] = 6

        doc.InsertObject(newMesh, parent=modelNull)
        newMesh.Message(c4d.MSG_UPDATE)
        c4d.EventAdd()

    if node[CAST_IMPORT_IK_HANDLES]:
        importSkeletonIKNode(doc, modelNull, model.Skeleton(), boneIndexes)

    if node[CAST_IMPORT_CONSTRAINTS]:
        importSkeletonConstraintNode(model.Skeleton(), boneIndexes)

def importSkeletonConstraintNode(skeleton, boneIndexes):
    if skeleton is None:
        return

    for constraint in skeleton.Constraints():
        constraintBone = boneIndexes[constraint.ConstraintBone().Hash()]
        targetBone = boneIndexes[constraint.TargetBone().Hash()]

        type = constraint.ConstraintType()

        # C4D's constraint system is a bit worse than Blender's
        constraintTag = c4d.BaseTag(CONSTRAINT_TAG)
        constraintBone.InsertTag(constraintTag)
        constraintTag[c4d.ID_CA_CONSTRAINT_TAG_PSR] = 1
        
        # Disabling all constraints, cause default is enabled
        constraintTag[CONSTRAIN_POS] = 0
        constraintTag[c4d.ID_CA_CONSTRAINT_TAG_PSR_CONSTRAIN_P_X] = 0
        constraintTag[c4d.ID_CA_CONSTRAINT_TAG_PSR_CONSTRAIN_P_Y] = 0
        constraintTag[c4d.ID_CA_CONSTRAINT_TAG_PSR_CONSTRAIN_P_Z] = 0

        constraintTag[CONSTRAIN_SCALE] = 0
        constraintTag[c4d.ID_CA_CONSTRAINT_TAG_PSR_CONSTRAIN_S_X] = 0
        constraintTag[c4d.ID_CA_CONSTRAINT_TAG_PSR_CONSTRAIN_S_Y] = 0
        constraintTag[c4d.ID_CA_CONSTRAINT_TAG_PSR_CONSTRAIN_S_Z] = 0

        constraintTag[CONSTRAIN_ROT] = 0
        constraintTag[c4d.ID_CA_CONSTRAINT_TAG_PSR_CONSTRAIN_R_X] = 0
        constraintTag[c4d.ID_CA_CONSTRAINT_TAG_PSR_CONSTRAIN_R_Y] = 0
        constraintTag[c4d.ID_CA_CONSTRAINT_TAG_PSR_CONSTRAIN_R_Z] = 0

        constraintTag[c4d.ID_CA_CONSTRAINT_TAG_PSR_MAINTAIN] = constraint.MaintainOffset()

        if type == "pt":
            constraintTag[CONSTRAIN_POS] = 1
            constraintTag[CONSTRAINT_TARGET] = targetBone
            constraintTag[c4d.ID_CA_CONSTRAINT_TAG_LOCAL_P] = 1
            if not constraint.SkipX():
                constraintTag[c4d.ID_CA_CONSTRAINT_TAG_PSR_CONSTRAIN_P_X] = 1
            if not constraint.SkipY():
                constraintTag[c4d.ID_CA_CONSTRAINT_TAG_PSR_CONSTRAIN_P_Y] = 1
            if not constraint.SkipZ():
                constraintTag[c4d.ID_CA_CONSTRAINT_TAG_PSR_CONSTRAIN_P_Z] = 1
        elif type == "sc":
            constraintTag[CONSTRAIN_SCALE] = 1
            constraintTag[CONSTRAINT_TARGET] = targetBone
            constraintTag[c4d.ID_CA_CONSTRAINT_TAG_LOCAL_S] = 1
            if not constraint.SkipX():
                constraintTag[c4d.ID_CA_CONSTRAINT_TAG_PSR_CONSTRAIN_S_X] = 1
            if not constraint.SkipY():
                constraintTag[c4d.ID_CA_CONSTRAINT_TAG_PSR_CONSTRAIN_S_Y] = 1
            if not constraint.SkipZ():
                constraintTag[c4d.ID_CA_CONSTRAINT_TAG_PSR_CONSTRAIN_S_Z] = 1
        elif type == "or":
            constraintTag[CONSTRAIN_ROT] = 1
            constraintTag[CONSTRAINT_TARGET] = targetBone
            constraintTag[c4d.ID_CA_CONSTRAINT_TAG_LOCAL_R] = 1
            if not constraint.SkipX():
                constraintTag[c4d.ID_CA_CONSTRAINT_TAG_PSR_CONSTRAIN_R_X] = 1
            if not constraint.SkipY():
                constraintTag[c4d.ID_CA_CONSTRAINT_TAG_PSR_CONSTRAIN_R_Y] = 1
            if not constraint.SkipZ():
                constraintTag[c4d.ID_CA_CONSTRAINT_TAG_PSR_CONSTRAIN_R_Z] = 1
        else:
            continue

        if constraint.Name() is not None:
            constraintTag[c4d.ID_BASELIST_NAME] = constraint.Name()

def importSkeletonIKNode(doc, modelNull, skeleton, boneIndexes):
    if skeleton is None or not skeleton.IKHandles():
        return

    ikParentNull = BaseObject(c4d.Onull)
    ikParentNull.SetName("IK_Handles")
    doc.InsertObject(ikParentNull, modelNull)
    for handle in skeleton.IKHandles():
        startBone = boneIndexes[handle.StartBone().Hash()]
        endBone = boneIndexes[handle.EndBone().Hash()]

        ikTargetNull = BaseObject(c4d.Onull)
        ikTargetNull.SetName(endBone.GetName() + "_IK")
        ikTargetNull.SetMg(endBone.GetMg())
        ikTargetNull.SetAbsRot(Vector(0, 0, 0))
        doc.InsertObject(ikTargetNull, ikParentNull)

        ikTag = c4d.BaseTag(IK_TAG)
        ikTag[c4d.ID_CA_IK_TAG_SOLVER] = 2
        ikTag[c4d.ID_CA_IK_TAG_TIP] = endBone
        ikTag[c4d.ID_CA_IK_TAG_TARGET] = ikTargetNull
        
        poleVectorBone = handle.PoleVectorBone()
        if poleVectorBone is not None:
            poleVector = boneIndexes[poleVectorBone.Hash()]
            ikPoleNull = BaseObject(c4d.Onull)
            ikPoleNull.SetName(poleVector.GetName() + "_Pole")
            ikPoleNull.SetMg(poleVector.GetMg())
            ikPoleNull.SetAbsRot(Vector(0, 0, 0))
            
            doc.InsertObject(ikPoleNull, startBone)
            
            ikTag[c4d.ID_CA_IK_TAG_POLE] = poleVector

        startBone.InsertTag(ikTag)
            
def importSkeletonNode(modelNull, skeleton):
    if skeleton is None:
        return None

    bones = skeleton.Bones()
    handles = [None] * len(bones)
    boneIndexes = {}

    for i, bone in enumerate(bones):
        newBone = BaseObject(c4d.Ojoint)
        newBone.SetName(bone.Name())
        
        tX, tY, tZ = bone.LocalPosition()
        translation = Vector(tX, tY, -tZ)

        rX, rY, rZ = utilityQuaternionToEuler(bone.LocalRotation())
        newBone.SetRotationOrder(5)

        scale_tuple = bone.Scale() or (1.0, 1.0, 1.0)
        scale = Vector(scale_tuple[0], scale_tuple[1], scale_tuple[2])

        newBone.SetAbsPos(translation)
        newBone.SetAbsRot(Vector(rX, rY, rZ))
        newBone.SetAbsScale(scale)

        handles[i] = newBone
        boneIndexes[bone.Hash() or i] = newBone

        if bone.ParentIndex() > -1:
            handles[i].InsertUnder(handles[bone.ParentIndex()])
        else:
            handles[i].InsertUnder(modelNull)

    return boneIndexes

def importAnimationNode(doc, animation, path):
    gui.MessageDialog(text="Animations are currently not supported.", type=c4d.GEMB_ICONSTOP)

def importInstanceNodes(doc, nodes, path):
    gui.MessageDialog(text="Instances are currently not supported.", type=c4d.GEMB_ICONSTOP)

if __name__ == '__main__':
    dir,fn=os.path.split(__file__)
    bmp=bitmaps.BaseBitmap()
    bmp.InitWith(os.path.join(dir,"res","icon.png"))
    reg=plugins.RegisterSceneLoaderPlugin(id=PLUGIN_ID,
                                          str=__pluginname__,
                                          info=0,
                                          g=CastLoader,
                                          description="fcastloader",
                                          )
