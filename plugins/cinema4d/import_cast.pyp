import c4d
import os
import array
import mxutils

from c4d import plugins, Vector, Vector4d, CPolygon, gui, BaseObject

PLUGIN_ID = 1062992
PLUGIN_RES_DIR = os.path.join(os.path.dirname(__file__), "res")

mxutils.ImportSymbols(PLUGIN_RES_DIR)

with mxutils.LocalImportPath(PLUGIN_RES_DIR):
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
        importInstanceNodes(doc, instances, node, path)


def utilityBuildPath(root, asset):
    if os.path.isabs(asset):
        return asset

    root = os.path.dirname(root)
    return os.path.join(root, asset)


def utilityQuaternionToEuler(tempQuat):
    quaternion = c4d.Quaternion()
    quaternion.w = tempQuat[3]
    quaternion.v = Vector(tempQuat[0], tempQuat[1], -tempQuat[2])

    return c4d.utils.MatrixToHPB(quaternion.GetMatrix(), c4d.ROTATIONORDER_HPB)


def utilityAddTextureMaterialSlots(slotName, texPath, mat, shaderType):
    shader = c4d.BaseList2D(c4d.Xbitmap)
    shader[c4d.BITMAPSHADER_FILENAME] = texPath
    shader.SetName(slotName)

    if slotName == "normal":
        mat[c4d.MATERIAL_USE_NORMAL] = True
        shader[c4d.BITMAPSHADER_COLORPROFILE] = c4d.BITMAPSHADER_COLORPROFILE_LINEAR

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

        utilityAddTextureMaterialSlots(
            slot, utilityBuildPath(path, connection.Path()), material, switcher[slot])


def importMaterialNode(doc, path, material):
    materials = doc.GetMaterials()

    # If you already created the material, ignore this
    for mat in materials:
        if mat.GetName() == material.Name():
            return mat

    materialNew = c4d.BaseMaterial(c4d.Mmaterial)
    materialNew.SetName(material.Name())

    # TODO: Better PBR Support?
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
    bones = importSkeletonNode(modelNull, model.Skeleton())
    materialArray = {x.Name(): importMaterialNode(doc, path, x)
                     for x in model.Materials()}

    meshes = model.Meshes()
    meshHandles = {}

    for mesh in meshes:
        newMesh = BaseObject(c4d.Opolygon)
        newMesh.SetName(mesh.Name() or "CastMesh")

        # Store for later creating blend shapes if necessary.
        meshHandles[mesh.Hash()] = newMesh

        vertexPositions = mesh.VertexPositionBuffer()
        vertexCount = int(len(vertexPositions) / 3)

        faces = mesh.FaceBuffer()
        faceIndicesCount = len(faces)
        facesCount = int(faceIndicesCount / 3)

        newMesh.ResizeObject(vertexCount, facesCount)

        for i in range(0, vertexCount, 3):
            newMesh.SetPoint(
                int(i / 3), Vector(vertexPositions[i], vertexPositions[i + 1], -vertexPositions[i + 2]))

        # Remap face indices to match c4d's winding order
        faces = [face for x in range(0, faceIndicesCount, 3)
                 for face in (faces[x + 2], faces[x + 1], faces[x + 0])]

        for i in range(0, faceIndicesCount, 3):
            newMesh.SetPolygon(
                int(i / 3), CPolygon(faces[i], faces[i + 1], faces[i + 2]))

        for i in range(mesh.UVLayerCount()):
            uvBuffer = mesh.VertexUVLayerBuffer(i)
            uvTag = c4d.UVWTag(facesCount)

            for i in range(0, faceIndicesCount, 3):
                uvTag.SetSlow(int(i / 3),
                              Vector(uvBuffer[faces[i] * 2],
                                     uvBuffer[(faces[i] * 2) + 1], 0),
                              Vector(uvBuffer[faces[i + 1] * 2],
                                     uvBuffer[(faces[i + 1] * 2) + 1], 0),
                              Vector(uvBuffer[faces[i + 2] * 2],
                                     uvBuffer[(faces[i + 2] * 2) + 1], 0),
                              Vector(0, 0, 0))

            newMesh.InsertTag(uvTag)

        for i in range(mesh.ColorLayerCount()):
            vertexColors = mesh.VertexColorLayerBuffer(i)
            vcTag = c4d.VertexColorTag(vertexCount)
            vcData = vcTag.GetDataAddressW()

            for v in range(vertexCount):
                color = CastColor.fromInteger(vertexColors[v])
                vcTag.SetPoint(vcData, None, None, v,
                               Vector4d(color[0], color[1], color[2], color[3]))

            newMesh.InsertTag(vcTag)

        vertexNormals = mesh.VertexNormalBuffer()
        if vertexNormals is not None:
            vnTag = c4d.NormalTag(facesCount)
            vnData = vnTag.GetDataAddressW()

            for i in range(0, faceIndicesCount, 3):
                vnTag.Set(vnData, int(i / 3), 
                          {"a": Vector(vertexNormals[faces[i] * 3],
                                       vertexNormals[(faces[i] * 3) + 1],
                                       -vertexNormals[(faces[i] * 3) + 2]),
                            "b": Vector(vertexNormals[faces[i + 1] * 3],
                                        vertexNormals[(faces[i + 1] * 3) + 1],
                                        -vertexNormals[(faces[i + 1] * 3) + 2]),
                            "c": Vector(vertexNormals[faces[i + 2] * 3],
                                        vertexNormals[(faces[i + 2] * 3) + 1],
                                        -vertexNormals[(faces[i + 2] * 3) + 2]),
                            "d": Vector(0, 0, 0)})



            newMesh.InsertTag(vnTag)

        if bones is not None and node[CAST_IMPORT_BIND_SKIN]:
            skinObj = BaseObject(c4d.Oskin)

            skinningMethod = mesh.SkinningMethod()

            if skinningMethod == "linear":
                skinObj[c4d.ID_CA_SKIN_OBJECT_TYPE] = c4d.ID_CA_SKIN_OBJECT_TYPE_LINEAR
            elif skinningMethod == "quaternion":
                skinObj[c4d.ID_CA_SKIN_OBJECT_TYPE] = c4d.ID_CA_SKIN_OBJECT_TYPE_QUAT

            doc.InsertObject(skinObj, parent=newMesh)

            weightTag = c4d.modules.character.CAWeightTag()
            
            newMesh.InsertTag(weightTag)

            for bone in bones.values():
                weightTag.AddJoint(bone)

            maximumInfluence = mesh.MaximumWeightInfluence()
            if maximumInfluence > 1:  # Slower path for complex weights
                weightBoneBuffer = mesh.VertexWeightBoneBuffer()
                weightValueBuffer = mesh.VertexWeightValueBuffer()

                for x in range(vertexCount):
                    for j in range(maximumInfluence):
                        weightIndex = j + (x * maximumInfluence)
                        weightValue = weightTag.GetWeight(
                            weightBoneBuffer[weightIndex], x)
                        weightValue += weightValueBuffer[weightIndex]
                        weightTag.SetWeight(
                            weightBoneBuffer[weightIndex], x, weightValue)
            elif maximumInfluence > 0:  # Fast path for simple weighted meshes
                weightBoneBuffer = mesh.VertexWeightBoneBuffer()
                for x in range(vertexCount):
                    weightTag.SetWeight(weightBoneBuffer[x], x, 1.0)

            weightTag.Message(c4d.MSG_UPDATE)

        meshMaterial = mesh.Material()
        if meshMaterial is not None:
            material = materialArray[meshMaterial.Name()]
            material_tag = newMesh.MakeTag(c4d.Ttexture)
            material_tag[c4d.TEXTURETAG_MATERIAL] = material
            material_tag[c4d.TEXTURETAG_PROJECTION] = c4d.TEXTURETAG_PROJECTION_UVW

        doc.InsertObject(newMesh, parent=modelNull)
        newMesh.Message(c4d.MSG_UPDATE)

    if node[CAST_IMPORT_IK_HANDLES]:
        importSkeletonIKNode(doc, modelNull, model.Skeleton(), bones)

    if node[CAST_IMPORT_CONSTRAINTS]:
        importSkeletonConstraintNode(model.Skeleton(), bones)

    # TODO: Does this do anything?
    c4d.EventAdd()

    return modelNull


def importSkeletonConstraintNode(skeleton, bones):
    if skeleton is None:
        return

    for constraint in skeleton.Constraints():
        constraintBone = bones[constraint.ConstraintBone().Hash()]
        targetBone = bones[constraint.TargetBone().Hash()]

        type = constraint.ConstraintType()

        # C4D's constraint system is a bit worse than Blender's
        constraintTag = c4d.BaseTag(c4d.Tcaconstraint)
        constraintBone.InsertTag(constraintTag)
        constraintTag[c4d.ID_CA_CONSTRAINT_TAG_PSR] = True

        # Disabling all constraints, cause default is enabled
        constraintTag[CONSTRAIN_POS] = False
        constraintTag[c4d.ID_CA_CONSTRAINT_TAG_PSR_CONSTRAIN_P_X] = False
        constraintTag[c4d.ID_CA_CONSTRAINT_TAG_PSR_CONSTRAIN_P_Y] = False
        constraintTag[c4d.ID_CA_CONSTRAINT_TAG_PSR_CONSTRAIN_P_Z] = False

        constraintTag[CONSTRAIN_SCALE] = False
        constraintTag[c4d.ID_CA_CONSTRAINT_TAG_PSR_CONSTRAIN_S_X] = False
        constraintTag[c4d.ID_CA_CONSTRAINT_TAG_PSR_CONSTRAIN_S_Y] = False
        constraintTag[c4d.ID_CA_CONSTRAINT_TAG_PSR_CONSTRAIN_S_Z] = False

        constraintTag[CONSTRAIN_ROT] = False
        constraintTag[c4d.ID_CA_CONSTRAINT_TAG_PSR_CONSTRAIN_R_X] = False
        constraintTag[c4d.ID_CA_CONSTRAINT_TAG_PSR_CONSTRAIN_R_Y] = False
        constraintTag[c4d.ID_CA_CONSTRAINT_TAG_PSR_CONSTRAIN_R_Z] = False

        constraintTag[c4d.ID_CA_CONSTRAINT_TAG_PSR_MAINTAIN] = constraint.MaintainOffset()

        if type == "pt":
            constraintTag[CONSTRAIN_POS] = True
            constraintTag[CONSTRAINT_TARGET] = targetBone
            constraintTag[c4d.ID_CA_CONSTRAINT_TAG_LOCAL_P] = True
            if not constraint.SkipX():
                constraintTag[c4d.ID_CA_CONSTRAINT_TAG_PSR_CONSTRAIN_P_X] = True
            if not constraint.SkipY():
                constraintTag[c4d.ID_CA_CONSTRAINT_TAG_PSR_CONSTRAIN_P_Y] = True
            if not constraint.SkipZ():
                constraintTag[c4d.ID_CA_CONSTRAINT_TAG_PSR_CONSTRAIN_P_Z] = True
        elif type == "sc":
            constraintTag[CONSTRAIN_SCALE] = True
            constraintTag[CONSTRAINT_TARGET] = targetBone
            constraintTag[c4d.ID_CA_CONSTRAINT_TAG_LOCAL_S] = True
            if not constraint.SkipX():
                constraintTag[c4d.ID_CA_CONSTRAINT_TAG_PSR_CONSTRAIN_S_X] = True
            if not constraint.SkipY():
                constraintTag[c4d.ID_CA_CONSTRAINT_TAG_PSR_CONSTRAIN_S_Y] = True
            if not constraint.SkipZ():
                constraintTag[c4d.ID_CA_CONSTRAINT_TAG_PSR_CONSTRAIN_S_Z] = True
        elif type == "or":
            constraintTag[CONSTRAIN_ROT] = True
            constraintTag[CONSTRAINT_TARGET] = targetBone
            constraintTag[c4d.ID_CA_CONSTRAINT_TAG_LOCAL_R] = True
            if not constraint.SkipX():
                constraintTag[c4d.ID_CA_CONSTRAINT_TAG_PSR_CONSTRAIN_R_X] = True
            if not constraint.SkipY():
                constraintTag[c4d.ID_CA_CONSTRAINT_TAG_PSR_CONSTRAIN_R_Y] = True
            if not constraint.SkipZ():
                constraintTag[c4d.ID_CA_CONSTRAINT_TAG_PSR_CONSTRAIN_R_Z] = True
        else:
            continue

        if constraint.Name() is not None:
            constraintTag[c4d.ID_BASELIST_NAME] = constraint.Name()


def importSkeletonIKNode(doc, modelNull, skeleton, bones):
    if skeleton is None or not skeleton.IKHandles():
        return

    ikParentNull = BaseObject(c4d.Onull)
    ikParentNull.SetName("IK_Handles")
    doc.InsertObject(ikParentNull, modelNull)
    for handle in skeleton.IKHandles():
        startBone = bones[handle.StartBone().Hash()]
        endBone = bones[handle.EndBone().Hash()]

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
            poleVector = bones[poleVectorBone.Hash()]
            ikTag[c4d.ID_CA_IK_TAG_POLE] = poleVector
            ikTag[c4d.ID_CA_IK_TAG_POLE_AXIS] = c4d.ID_CA_IK_TAG_POLE_AXIS_X
            ikTag[c4d.ID_CA_IK_TAG_POLE_TWIST] = poleVector[c4d.ID_BASEOBJECT_REL_ROTATION, c4d.VECTOR_X]

        # TODO: This shouldn't need emulation.
        poleBone = handle.PoleBone()
        if poleBone is not None:
            # Warn until we figure out how to emulate this effectively.
            gui.MessageDialog(text="Unable to setup %s fully due to Cinema 4D not supporting pole (twist) bones." %
                              poleBone.Name(), type=c4d.GEMB_ICONEXCLAMATION)
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

        rotation = utilityQuaternionToEuler(bone.LocalRotation())

        scale = bone.Scale() or (1.0, 1.0, 1.0)
        scale = Vector(scale[0], scale[1], scale[2])

        newBone.SetAbsPos(translation)
        newBone.SetAbsRot(rotation)
        newBone.SetAbsScale(scale)

        handles[i] = newBone
        boneIndexes[bone.Hash() or i] = newBone

    for i, bone in enumerate(bones):
        if bone.ParentIndex() > -1:
            handles[i].InsertUnder(handles[bone.ParentIndex()])
        else:
            handles[i].InsertUnder(modelNull)

    return boneIndexes


def importAnimationNode():
    gui.MessageDialog(
        text="Animations are currently not supported.", type=c4d.GEMB_ICONSTOP)


def importInstanceNodes(doc, nodes, node, path):
    rootPath = c4d.storage.LoadDialog(
        title='Select the root directory where instance scenes are located', flags=2)

    if rootPath is None:
        return gui.MessageDialog(text="Unable to import instances without a root directory!", type=c4d.GEMB_ICONSTOP)

    uniqueInstances = {}

    for instance in nodes:
        refs = os.path.join(rootPath, instance.ReferenceFile().Path())

        if refs in uniqueInstances:
            uniqueInstances[refs].append(instance)
        else:
            uniqueInstances[refs] = [instance]

    name = os.path.splitext(os.path.basename(path))[0]

    # Create a collection for our objects
    rootNull = BaseObject(c4d.Onull)
    rootNull.SetName(name)

    doc.InsertObject(rootNull)

    instanceNull = BaseObject(c4d.Onull)
    instanceNull.SetName("%s_instances" % name)
    instanceNull.InsertUnder(rootNull)

    sceneNull = BaseObject(c4d.Onull)
    sceneNull.SetName("%s_scenes" % name)
    sceneNull.InsertUnder(rootNull)

    # Disable source models visibility
    sceneNull[c4d.ID_BASEOBJECT_VISIBILITY_EDITOR] = c4d.OBJECT_OFF
    sceneNull[c4d.ID_BASEOBJECT_VISIBILITY_RENDER] = c4d.OBJECT_OFF

    for instancePath, instances in uniqueInstances.items():
        instanceName = os.path.splitext(os.path.basename(instancePath))[0]

        try:
            cast = Cast.load(instancePath)
            for root in cast.Roots():
                for child in root.ChildrenOfType(Model):
                    modelNull = importModelNode(doc, node, child, instancePath)
            modelNull.InsertUnder(sceneNull)
        except:
            print("Failed to import instance: %s" % instancePath)
            continue

        for instance in instances:
            # Creates instance object
            newInstance = c4d.InstanceObject()

            newInstance.SetName(instance.Name() or instanceName)
            newInstance.InsertUnder(instanceNull)

            tX, tY, tZ = instance.Position()
            translation = Vector(tX, tY, -tZ)

            tempQuat = instance.Rotation()
            rotation = utilityQuaternionToEuler(tempQuat)

            scaleTuple = instance.Scale() or (1.0, 1.0, 1.0)
            scale = Vector(scaleTuple[0], scaleTuple[1], scaleTuple[2])

            newInstance.SetAbsPos(translation)
            newInstance.SetAbsRot(rotation)
            newInstance.SetAbsScale(scale)

            newInstance.SetReferenceObject(modelNull)


if __name__ == '__main__':
    reg = plugins.RegisterSceneLoaderPlugin(id=PLUGIN_ID,
                                            str=__pluginname__,
                                            info=0,
                                            g=CastLoader,
                                            description="fcastloader",
                                            )
