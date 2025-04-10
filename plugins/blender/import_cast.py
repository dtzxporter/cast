import bpy
import os
import array
import sys

from mathutils import *
from bpy_extras.io_utils import unpack_list
from .cast import Cast, CastColor, Model, Animation, Instance, File, Color


def utilityBuildPath(root, asset):
    if os.path.isabs(asset):
        return asset

    root = os.path.dirname(root)
    return os.path.join(root, asset)


def utilityStashCurveComponent(component, curve, name, index):
    if name in component:
        component[name][index] = curve
    else:
        value = [None] * 3
        value[index] = curve
        component[name] = value


def utilityIsVersionAtLeast(major, minor):
    if bpy.app.version[0] > major:
        return True
    elif bpy.app.version[0] == major and bpy.app.version[1] >= minor:
        return True
    return False


def utilityClearKeyframePoints(fcurve):
    if utilityIsVersionAtLeast(4, 0):
        return fcurve.keyframe_points.clear()

    for keyframe in reversed(fcurve.keyframe_points.values()):
        fcurve.keyframe_points.remove(keyframe)


def utilityAddKeyframe(fcurve, frame, value, interpolation):
    keyframe = \
        fcurve.keyframe_points.insert(frame, value=value, options={'FAST'})
    keyframe.interpolation = interpolation


def utilityFindShaderNode(material, bl_idname):
    for node in material.node_tree.nodes.values():
        if node.bl_idname == bl_idname:
            return node

    return None


def utilityAssignMaterialSlots(material, slots, path):
    # Find the principled shader.
    shader = utilityFindShaderNode(material, "ShaderNodeBsdfPrincipled")
    # Determine workflow, metalness/roughness or specular/gloss
    metalness = "metal" in slots

    if metalness:
        switcher = {
            "albedo": "Base Color",
            "diffuse": "Base Color",
            "specular": "Specular IOR Level" if utilityIsVersionAtLeast(4, 0) else "Specular",
            "metal": "Metallic",
            "roughness": "Roughness",
            "gloss": "Roughness",
            "normal": "Normal",
            "emissive": "Emission Color" if utilityIsVersionAtLeast(4, 0) else "Emission",
            "emask": "Emission Strength",
        }
    else:
        # Set reasonable defaults for specular/gloss workflow.
        shader.inputs["Metallic"].default_value = 0.0
        shader.inputs["IOR"].default_value = 1.5

        switcher = {
            "albedo": "Base Color",
            "diffuse": "Base Color",
            "specular": "Specular Tint" if utilityIsVersionAtLeast(4, 0) else "Specular",
            "roughness": "Roughness",
            "gloss": "Roughness",
            "normal": "Normal",
            "emissive": "Emission Color" if utilityIsVersionAtLeast(4, 0) else "Emission",
            "emask": "Emission Strength",
        }

    # Prevent duplicate connections if one or more conflict occurs.
    used = []

    # Loop and connect the slots
    for slot in slots:
        connection = slots[slot]

        if not slot in switcher:
            continue
        if switcher[slot] in used:
            continue

        used.append(switcher[slot])

        if connection.__class__ is File:
            node = material.node_tree.nodes.new("ShaderNodeTexImage")

            try:
                node.image = bpy.data.images.load(
                    utilityBuildPath(path, connection.Path()))

                # The following slots are non-color data.
                if slot in ["metal", "normal", "gloss", "roughness"] \
                        or (metalness and slot == "specular"):
                    node.image.colorspace_settings.name = "Non-Color"

                # This is a sane setting for most textures, as they will use the alpha channel separately.
                # Blender also has broken straight/premultiplied modes.
                node.image.alpha_mode = "CHANNEL_PACKED"
            except RuntimeError:
                # Occurs if texture was unsupported or failed to load.
                pass
        elif connection.__class__ is Color:
            node = material.node_tree.nodes.new("ShaderNodeRGB")

            if connection.Name() is not None:
                node.label = connection.Name()
            else:
                node.label = ("Color: %s" % switcher[slot])

            # Handle color conversion if necessary, blender color node is linear.
            if connection.ColorSpace() == "srgb":
                # Set the color value, converted to linear, see below for more info.
                node.outputs["Color"].default_value = \
                    CastColor.toLinearFromSRGB(connection.Rgba())
            else:
                # Set the color value, even though we can't separate the alpha channel from this node.
                # It becomes premultiplied alpha no matter what, which is a pain.
                node.outputs["Color"].default_value = connection.Rgba()
        else:
            continue

        if slot == "normal":
            normalMap = material.node_tree.nodes.new("ShaderNodeNormalMap")
            material.node_tree.links.new(
                normalMap.inputs["Color"], node.outputs["Color"])
            material.node_tree.links.new(
                shader.inputs[switcher[slot]], normalMap.outputs["Normal"])
        elif slot == "gloss":
            invert = material.node_tree.nodes.new("ShaderNodeInvert")
            material.node_tree.links.new(
                invert.inputs["Color"], node.outputs["Color"])
            material.node_tree.links.new(
                shader.inputs[switcher[slot]], invert.outputs["Color"])
        else:
            material.node_tree.links.new(
                shader.inputs[switcher[slot]], node.outputs["Color"])


def utilitySetVertexNormals(mesh, vertexNormals, faces):
    if not vertexNormals:
        return mesh.validate(clean_customdata=False)

    if utilityIsVersionAtLeast(4, 1):
        mesh.validate(clean_customdata=False)
        mesh.normals_split_custom_set_from_vertices(
            tuple(zip(*(iter(vertexNormals),) * 3)))
    else:
        mesh.create_normals_split()
        mesh.loops.foreach_set("normal", unpack_list(
            [(vertexNormals[x * 3], vertexNormals[(x * 3) + 1], vertexNormals[(x * 3) + 2]) for x in faces]))

        mesh.validate(clean_customdata=False)
        clnors = array.array('f', [0.0] * (len(mesh.loops) * 3))
        mesh.loops.foreach_get("normal", clnors)

        mesh.polygons.foreach_set(
            "use_smooth", [True] * len(mesh.polygons))

        mesh.normals_split_custom_set(
            tuple(zip(*(iter(clnors),) * 3)))
        mesh.use_auto_smooth = True


def utilityGetOrCreateCurve(fcurves, poseBones, name, curve):
    if not name in poseBones:
        return None

    bone = poseBones[name]

    return fcurves.find(data_path="pose.bones[\"%s\"].%s" %
                        (bone.name, curve[0]), index=curve[1]) or fcurves.new(data_path="pose.bones[\"%s\"].%s" %
                                                                              (bone.name, curve[0]), index=curve[1], action_group=bone.name)


def utilityGetOrCreateSlot(action):
    slot = None

    for existingSlot in action.slots:
        if existingSlot.target_id_type == "OBJECT" and existingSlot.name_display == "cast":
            slot = existingSlot
            break

    if slot is None:
        slot = action.slots.new(id_type="OBJECT", name="cast")

    action.slots.active = slot

    return slot


def utilityResolveCurveModeOverride(bone, mode, overrides, isTranslate=False, isRotate=False, isScale=False):
    if not overrides:
        return mode

    for parent in bone.parent_recursive:
        for override in overrides:
            if isTranslate and not override.OverrideTranslationCurves():
                continue
            elif isRotate and not override.OverrideRotationCurves():
                continue
            elif isScale and not override.OverrideScaleCurves():
                continue

            if parent.name == override.NodeName():
                return override.Mode()


def utilityGetBindposeScale(poseBone):
    bindPoseScale = Matrix.LocRotScale(None, None, Vector((1.0, 1.0, 1.0)))

    if poseBone is not None:
        bindPoseScale = bindPoseScale @ Matrix.LocRotScale(None, None, Vector(
            getattr(poseBone, "cast_bind_pose_scale", (1.0, 1.0, 1.0))))

    return bindPoseScale


def importSkeletonConstraintNode(self, skeleton, poses):
    if skeleton is None:
        return

    for constraint in skeleton.Constraints():
        constraintBone = poses[constraint.ConstraintBone().Name()]
        targetBone = poses[constraint.TargetBone().Name()]

        type = constraint.ConstraintType()
        customOffset = constraint.CustomOffset()
        maintainOffset = constraint.MaintainOffset()

        if type == "pt":
            if customOffset:
                constraintBone.location = Vector(customOffset)

            ct = constraintBone.constraints.new("COPY_LOCATION")

            if maintainOffset or customOffset:
                ct.use_offset = True
            else:
                ct.use_offset = False
        elif type == "or":
            if customOffset:
                constraintBone.rotation_mode = 'QUATERNION'
                constraintBone.rotation_quaternion = Quaternion(
                    (customOffset[3], customOffset[0], customOffset[1], customOffset[2]))

            ct = constraintBone.constraints.new("COPY_ROTATION")

            if maintainOffset or customOffset:
                ct.mix_mode = 'OFFSET'
            else:
                ct.mix_mode = 'REPLACE'
        elif type == "sc":
            if customOffset:
                constraintBone.scale = Vector(customOffset)

            ct = constraintBone.constraints.new("COPY_SCALE")

            if maintainOffset or customOffset:
                ct.use_offset = True
            else:
                ct.use_offset = False
        else:
            continue

        ct.owner_space = 'LOCAL'
        ct.target_space = 'LOCAL'

        if constraint.Name() is not None:
            ct.name = constraint.Name()

        ct.influence = constraint.Weight()

        ct.use_x = not constraint.SkipX()
        ct.use_y = not constraint.SkipY()
        ct.use_z = not constraint.SkipZ()

        ct.target = targetBone.id_data
        ct.subtarget = targetBone.name

        # We have to configure this after setting a target because the enum
        # option isn't available unless orient is supported by the target itself.
        if type == "or":
            ct.target_space = 'LOCAL_OWNER_ORIENT'


def importMergeModel(self, selectedObj, skeletonObj, poses):
    if skeletonObj is None:
        return

    # Find matching root bones in the selected object.
    # If we had none by the end of the transaction, warn the user that the models aren't compatible.
    foundMatchingRoot = False

    missingBones = []

    for bone in skeletonObj.pose.bones:
        if not bone.name in selectedObj.pose.bones:
            missingBones.append(bone.name)
            continue

        if bone.parent is not None:
            continue

        foundMatchingRoot = True

        # Move the models bone to the existing bone in the scene's position.
        bone.matrix = selectedObj.pose.bones[bone.name].matrix

    if not foundMatchingRoot:
        self.report(
            {"WARNING"}, "Could not find compatible root bones make sure the skeletons are compatible.")
        return

    bpy.context.view_layer.objects.active = skeletonObj
    bpy.ops.object.mode_set(mode='EDIT')

    # Create missing bones.
    while missingBones:
        for bone in [x for x in missingBones]:
            bone = skeletonObj.data.edit_bones[bone]

            # If the parent doesn't exist yet, skip it.
            if bone.parent and not bone.parent.name in selectedObj.data.edit_bones:
                continue
            elif bone.parent:
                parent = selectedObj.data.edit_bones[bone.parent.name]
            else:
                parent = None

            # Calculate the new world space matrix.
            newParent = parent.matrix if parent else Matrix.Identity()
            oldParent = skeletonObj.data.edit_bones[bone.name].parent.matrix \
                if newParent else Matrix.Identity()

            relative = oldParent.inverted() @ \
                skeletonObj.data.edit_bones[bone.name].matrix
            world = newParent @ relative

            newBone = selectedObj.data.edit_bones.new(bone.name)
            newBone.tail = 0, 0.0025, 0  # I am sorry but blender sucks
            newBone.parent = parent
            newBone.matrix = world

            missingBones.remove(bone.name)

    bpy.context.view_layer.objects.active = skeletonObj
    bpy.ops.object.mode_set(mode='POSE')

    # Make sure that any bone in poses update for ik/constraints later.
    for bone in poses.keys():
        poses[bone] = skeletonObj.pose.bones[bone]

    bpy.context.view_layer.objects.active = skeletonObj
    bpy.ops.object.mode_set(mode='OBJECT')

    for child in skeletonObj.children:
        if not child.type == "MESH":
            continue

        shapes = []

        if child.data.shape_keys:
            for shape in child.data.shape_keys.key_blocks:
                shapes.append(shape)

        child.select_set(True)

        # Bake the new mesh rest position so that we can copy the weights and modifiers.
        bpy.context.view_layer.objects.active = child
        bpy.ops.object.convert(target="MESH")

        child.select_set(False)
        child.parent = selectedObj

        for shape in shapes:
            newShape = child.shape_key_add(name=shape.name, from_mix=False)
            newShape.interpolation = shape.interpolation
            newShape.slider_max = shape.slider_max

            points = [None] * (len(shape.data) * 3)

            shape.data.foreach_get("co", points)
            newShape.data.foreach_set("co", points)

        for collection in list(child.users_collection):
            collection.objects.unlink(child)
        for collection in selectedObj.users_collection:
            collection.objects.link(child)

        # Create a new armature modifier as the old one gets destroyed. The vertex groups stay.
        modifier = child.modifiers.new('Armature Rig', 'ARMATURE')
        modifier.object = selectedObj
        modifier.use_bone_envelopes = False
        modifier.use_vertex_groups = True

    # Remove the armature, bones, and then the collection created for this mesh.
    oldCollection = skeletonObj.users_collection[0]

    bpy.data.objects.remove(skeletonObj, do_unlink=True)
    bpy.data.collections.remove(oldCollection, do_unlink=True)


def importSkeletonIKNode(self, skeleton, poses):
    if skeleton is None:
        return

    for handle in skeleton.IKHandles():
        startBone = poses[handle.EndBone().Name()]
        endBone = poses[handle.StartBone().Name()]

        ik = startBone.constraints.new("IK")

        if handle.Name() is not None:
            ik.name = handle.Name()

        # We need to create the ik constraint for the start bone, and set the chain length
        # so that it makes it to end end bone (Walk the parent tree and count.)
        ik.chain_count = 0
        ik.use_tail = True

        bone = startBone

        while True:
            ik.chain_count += 1
            bone = bone.parent

            if bone is None:
                break
            elif bone.name == endBone.name:
                ik.chain_count += 1
                break

        targetBone = handle.TargetBone()

        if targetBone is not None:
            target = poses[targetBone.Name()]

            ik.target = target.id_data
            ik.subtarget = target.name
            ik.use_location = True

            if handle.UseTargetRotation():
                ik.use_rotation = True

        poleVectorBone = handle.PoleVectorBone()

        if poleVectorBone is not None:
            poleVector = poses[poleVectorBone.Name()]

            ik.pole_target = target.id_data
            ik.pole_subtarget = poleVector.name

        poleBone = handle.PoleBone()

        if poleBone is not None:
            # Warn until we figure out how to emulate this effectively.
            self.report(
                {"WARNING"}, "Unable to setup %s fully due to blender not supporting pole (twist) bones." % ik.name)


def importSkeletonNode(name, skeleton, collection):
    if skeleton is None:
        return (None, None)

    armature = bpy.data.armatures.new("Joints")
    armature.display_type = "STICK"

    skeletonObj = bpy.data.objects.new(name, armature)
    skeletonObj.show_in_front = True

    collection.objects.link(skeletonObj)
    bpy.context.view_layer.objects.active = skeletonObj
    bpy.ops.object.mode_set(mode='EDIT')

    bones = skeleton.Bones()
    handles = [None] * len(bones)
    poses = {}
    matrices = {}
    scales = {}

    for i, bone in enumerate(bones):
        newBone = armature.edit_bones.new(bone.Name())
        newBone.tail = 0, 0.0025, 0  # I am sorry but blender sucks

        tempQuat = bone.LocalRotation()  # Also sucks, WXYZ? => XYZW master race
        rotation = Quaternion(
            (tempQuat[3], tempQuat[0], tempQuat[1], tempQuat[2]))

        translation = Vector(bone.LocalPosition())

        scale = Vector(bone.Scale() or (1.0, 1.0, 1.0))

        matrices[newBone.name] = Matrix.LocRotScale(
            translation, rotation, None)
        scales[newBone.name] = scale
        handles[i] = newBone

    for i, bone in enumerate(bones):
        if bone.ParentIndex() > -1:
            handles[i].parent = handles[bone.ParentIndex()]

    bpy.context.view_layer.objects.active = skeletonObj
    bpy.ops.object.mode_set(mode='POSE')

    for bone in skeletonObj.pose.bones:
        bone.cast_bind_pose_scale = scales[bone.name]

        bone.matrix_basis.identity()
        bone.matrix = matrices[bone.name]

        poses[bone.name] = bone

    bpy.ops.pose.armature_apply()
    return (skeletonObj, poses)


def importMaterialNode(path, material):
    # If you already created the material, ignore this
    materialNew = bpy.data.materials.get(material.Name())
    if materialNew is not None:
        return material.Name(), materialNew

    materialNew = bpy.data.materials.new(name=material.Name())
    materialNew.use_nodes = True

    utilityAssignMaterialSlots(materialNew, material.Slots(), path)

    return material.Name(), materialNew


def importModelNode(self, model, path, selectedObject):
    # Extract the name of this model from the path
    modelName = model.Name() or os.path.splitext(os.path.basename(path))[0]

    # Create a collection for our objects
    collection = bpy.data.collections.new(modelName)
    bpy.context.scene.collection.children.link(collection)

    # Import skeleton for binds, materials for meshes
    (skeletonObj, poses) = importSkeletonNode(
        modelName, model.Skeleton(), collection)
    materialArray = {key: value for (key, value) in (
        importMaterialNode(path, x) for x in model.Materials())}

    # For mesh import performance, unlink from scene until we're done
    bpy.context.scene.collection.children.unlink(collection)

    meshes = model.Meshes()
    meshHandles = {}

    for mesh in meshes:
        newMesh = bpy.data.meshes.new("polySurfaceMesh")
        meshObj = bpy.data.objects.new(mesh.Name() or "CastMesh", newMesh)

        # Store for later creating blend shapes if necessary.
        meshHandles[mesh.Hash()] = (meshObj, newMesh)

        vertexPositions = mesh.VertexPositionBuffer()
        newMesh.vertices.add(int(len(vertexPositions) / 3))
        newMesh.vertices.foreach_set("co", vertexPositions)

        faces = mesh.FaceBuffer()
        faceIndicesCount = len(faces)
        facesCount = int(faceIndicesCount / 3)

        # Remap face indices to match blender's winding order
        faces = unpack_list([(faces[x + 1], faces[x + 2], faces[x + 0])
                             for x in range(0, faceIndicesCount, 3)])

        newMesh.loops.add(faceIndicesCount)
        newMesh.polygons.add(facesCount)

        newMesh.loops.foreach_set("vertex_index", faces)
        newMesh.polygons.foreach_set(
            "loop_start", [x for x in range(0, faceIndicesCount, 3)])
        newMesh.polygons.foreach_set("loop_total", [3] * facesCount)
        newMesh.polygons.foreach_set("material_index", [0] * facesCount)

        for i in range(mesh.UVLayerCount()):
            uvBuffer = mesh.VertexUVLayerBuffer(i)
            newMesh.uv_layers.new(do_init=False)
            newMesh.uv_layers[i].data.foreach_set("uv", unpack_list(
                [(uvBuffer[x * 2], 1.0 - uvBuffer[(x * 2) + 1]) for x in faces]))

        for i in range(mesh.ColorLayerCount()):
            vertexColors = mesh.VertexColorLayerBuffer(i)
            newMesh.vertex_colors.new(do_init=False)
            newMesh.vertex_colors[i].data.foreach_set(
                "color", unpack_list([CastColor.fromInteger(vertexColors[x]) for x in faces]))

        vertexNormals = mesh.VertexNormalBuffer()
        utilitySetVertexNormals(newMesh, vertexNormals, faces)

        meshMaterial = mesh.Material()
        if meshMaterial is not None:
            newMesh.materials.append(materialArray[meshMaterial.Name()])

        if skeletonObj is not None and self.import_skin:
            boneGroups = []
            for bone in model.Skeleton().Bones():
                boneGroups.append(meshObj.vertex_groups.new(name=bone.Name()))

            meshObj.parent = skeletonObj
            modifier = meshObj.modifiers.new('Armature Rig', 'ARMATURE')
            modifier.object = skeletonObj
            modifier.use_bone_envelopes = False
            modifier.use_vertex_groups = True

            skinningMethod = mesh.SkinningMethod()

            if skinningMethod == "linear":
                modifier.use_deform_preserve_volume = False
            elif skinningMethod == "quaternion":
                modifier.use_deform_preserve_volume = True

            maximumInfluence = mesh.MaximumWeightInfluence()
            if maximumInfluence > 1:  # Slower path for complex weights
                weightBoneBuffer = mesh.VertexWeightBoneBuffer()
                weightValueBuffer = mesh.VertexWeightValueBuffer()

                for x in range(len(newMesh.vertices)):
                    for j in range(maximumInfluence):
                        i = j + (x * maximumInfluence)

                        boneGroups[weightBoneBuffer[i]].add(
                            (x,), weightValueBuffer[i], "ADD")
            elif maximumInfluence > 0:  # Fast path for simple weighted meshes
                weightBoneBuffer = mesh.VertexWeightBoneBuffer()
                for x in range(len(newMesh.vertices)):
                    boneGroups[weightBoneBuffer[x]].add((x,), 1.0, "REPLACE")

        collection.objects.link(meshObj)

    # Import hairs if necessary.
    if self.import_hair:
        hairs = model.Hairs()

        for hair in hairs:
            segmentsBuffer = hair.SegmentsBuffer()
            particleBuffer = hair.ParticleBuffer()
            particleOffset = 0

            strandCount = hair.StrandCount()

            # Curve hair is the best option for accuracy
            # Mesh hair can be used as a light weight fallback method.
            if self.create_hair_type == "curve" and \
                    self.create_hair_subtype == "bevel":
                hairData = bpy.data.curves.new(name="curve", type="CURVE")
                hairData.dimensions = '3D'
                hairData.resolution_u = 3

                hairObj = \
                    bpy.data.objects.new(hair.Name() or "CastHair", hairData)

                for s in range(strandCount):
                    segment = segmentsBuffer[s]

                    strand = hairData.splines.new(type="NURBS")
                    strand.points.add(segment)

                    for pt in range(segment + 1):
                        strand.points[pt].co = (
                            particleBuffer[particleOffset * 3],
                            particleBuffer[particleOffset * 3 + 1],
                            particleBuffer[particleOffset * 3 + 2], 1.0)
                        particleOffset += 1

                # Setup curve rendering because we don't want the particle system.
                # Curves don't render by default, so we need to enable them to.
                hairData.use_fill_caps = True
                hairData.bevel_depth = 0.001

                hairMaterial = hair.Material()
                if hairMaterial is not None:
                    hairData.materials.append(
                        materialArray[hairMaterial.Name()])
            elif self.create_hair_type == "mesh":
                vertexBuffer = []
                normalBuffer = []
                faceBuffer = []

                def createNormal(v1, v2, v3):
                    return (v3 - v1).cross((v2 - v1).normalized()).normalized()

                def createVertex(position, normal):
                    index = int(len(vertexBuffer) / 3)

                    vertexBuffer.extend([position.x, position.y, position.z])
                    normalBuffer.extend([normal.x, normal.y, normal.z])

                    return index

                particleExtrusion = Vector((0.0, 0.0, 0.010))
                particleOffset = 0

                for s in range(strandCount):
                    segment = segmentsBuffer[s]

                    for i in range(segment):
                        a = Vector((particleBuffer[particleOffset * 3],
                                    particleBuffer[particleOffset * 3 + 1],
                                    particleBuffer[particleOffset * 3 + 2]))
                        particleOffset += 1
                        b = Vector((particleBuffer[particleOffset * 3],
                                    particleBuffer[particleOffset * 3 + 1],
                                    particleBuffer[particleOffset * 3 + 2]))

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

                        faceBuffer.extend([b1, aUp1, a1])
                        faceBuffer.extend([b2, bUp2, a2])

                    particleOffset += 1

                vertexCount = int(len(vertexBuffer) / 3)
                faceIndicesCount = len(faceBuffer)
                facesCount = int(faceIndicesCount / 3)

                hairMesh = bpy.data.meshes.new("polySurfaceMesh")
                hairObj = bpy.data.objects.new(
                    hair.Name() or "CastHair", hairMesh)

                hairMesh.vertices.add(vertexCount)
                hairMesh.vertices.foreach_set("co", vertexBuffer)

                hairMesh.loops.add(faceIndicesCount)
                hairMesh.polygons.add(facesCount)

                hairMesh.loops.foreach_set("vertex_index", faceBuffer)
                hairMesh.polygons.foreach_set(
                    "loop_start", [x for x in range(0, faceIndicesCount, 3)])
                hairMesh.polygons.foreach_set("loop_total", [3] * facesCount)
                hairMesh.polygons.foreach_set(
                    "material_index", [0] * facesCount)

                utilitySetVertexNormals(hairMesh, normalBuffer, faceBuffer)

                hairMaterial = hair.Material()
                if hairMaterial is not None:
                    hairMesh.materials.append(
                        materialArray[hairMaterial.Name()])

            # Parent hair to skeleton if necessary:
            if skeletonObj is not None and self.import_skin:
                hairObj.parent = skeletonObj

            collection.objects.link(hairObj)

    # Import blend shape controllers if necessary.
    if self.import_blend_shapes:
        blendShapes = model.BlendShapes()
        blendShapesByBaseShape = {}

        # Merge the blend shapes together by their base shapes, so we only create a basis once.
        for blendShape in blendShapes:
            baseShapeHash = blendShape.BaseShape().Hash()

            if baseShapeHash not in meshHandles:
                continue
            if baseShapeHash not in blendShapesByBaseShape:
                blendShapesByBaseShape[baseShapeHash] = [blendShape]
            else:
                blendShapesByBaseShape[baseShapeHash].append(blendShape)

        # Iterate over the blend shapes by base shapes.
        for blendShapes in blendShapesByBaseShape.values():
            baseShape = meshHandles[blendShapes[0].BaseShape().Hash()]

            # The basis will automatically load the base shape's vertex positions.
            basis = baseShape[0].shape_key_add(name="Basis")
            basis.interpolation = "KEY_LINEAR"

            for blendShape in blendShapes:
                newShape = baseShape[0].shape_key_add(
                    name=blendShape.Name(), from_mix=False)
                newShape.interpolation = "KEY_LINEAR"
                newShape.slider_max = min(
                    10.0, blendShape.TargetWeightScale() or 1.0)

                indices = blendShape.TargetShapeVertexIndices()
                positions = blendShape.TargetShapeVertexPositions()

                if not indices or not positions:
                    self.report(
                        {'WARNING'}, "Ignoring blend shape \"%s\" for mesh \"%s\" no indices or positions specified." % (blendShape.Name(), baseShape[0].name))
                    continue

                for i, vertexIndex in enumerate(indices):
                    newShape.data[vertexIndex].co = Vector(
                        (positions[i * 3], positions[(i * 3) + 1], positions[(i * 3) + 2]))

    # Relink the collection after the mesh is built.
    bpy.context.view_layer.active_layer_collection.collection.children.link(
        collection)

    # Merge with the existing skeleton here if one is selected and we have a skeleton.
    if self.import_merge:
        if selectedObject and selectedObject.type == 'ARMATURE':
            importMergeModel(self, selectedObject, skeletonObj, poses)
        else:
            self.report(
                {'WARNING'}, "You must select an armature to merge to.")

    # Import any ik handles now that the meshes are bound because the constraints may effect the bind pose.
    if self.import_ik:
        importSkeletonIKNode(self, model.Skeleton(), poses)

    # Import any constraints after ik.
    if self.import_constraints:
        importSkeletonConstraintNode(self, model.Skeleton(), poses)

    # If we merged this model, select the target armature again.
    if self.import_merge:
        if selectedObject and selectedObject.type == 'ARMATURE':
            bpy.context.view_layer.objects.active = selectedObject
            bpy.ops.object.mode_set(mode='OBJECT')


def importRotCurveNode(node, nodeName, fcurves, poseBones, path, startFrame, overrides):
    smallestFrame = sys.maxsize
    largestFrame = 0

    if not nodeName in poseBones:
        return (smallestFrame, largestFrame)

    bone = poseBones[nodeName]
    mode = utilityResolveCurveModeOverride(
        bone, node.Mode(), overrides, isRotate=True)

    tracks = [utilityGetOrCreateCurve(fcurves, poseBones, nodeName, x) for x in [
        ("rotation_quaternion", 0), ("rotation_quaternion", 1), ("rotation_quaternion", 2), ("rotation_quaternion", 3)]]

    keyFrameBuffer = node.KeyFrameBuffer()
    keyValueBuffer = node.KeyValueBuffer()

    # https://devtalk.blender.org/t/quaternion-interpolation/15883
    # Blender interpolates rotations as-if they are separate components.
    # This logic is of course, broken, so we must interpolate ourselves.
    rotations = []
    keyframes = []

    if len(keyFrameBuffer) > 0:
        minFrame = min(keyFrameBuffer)
        maxFrame = max(keyFrameBuffer)

        existing = {}

        for i in range(0, len(keyValueBuffer), 4):
            existing[keyFrameBuffer[int(i / 4)]] = Quaternion(
                (keyValueBuffer[i + 3], keyValueBuffer[i], keyValueBuffer[i + 1], keyValueBuffer[i + 2]))

        lastKeyframeValue = None
        lastKeyframeFrame = None
        nextKeyframeValue = None
        nextKeyframeFrame = None

        for frame in range(minFrame, maxFrame + 1):
            if frame in existing:
                value = existing[frame]

                lastKeyframeValue = value
                lastKeyframeFrame = frame

                rotations.append(value)
                keyframes.append(frame)
                continue

            if lastKeyframeValue is None or lastKeyframeFrame is None:
                continue

            if nextKeyframeFrame is None or nextKeyframeFrame <= frame:
                for nextFrame in range(frame + 1, maxFrame + 1):
                    if nextFrame in existing:
                        nextKeyframeValue = existing[nextFrame]
                        nextKeyframeFrame = nextFrame
                        break

            if nextKeyframeFrame is not None and nextKeyframeFrame > frame:
                if lastKeyframeValue != nextKeyframeValue:
                    rotations.append(lastKeyframeValue.slerp(
                        nextKeyframeValue, (frame - lastKeyframeFrame) / (nextKeyframeFrame - lastKeyframeFrame)))
                    keyframes.append(frame)
                continue

    # Calculate the inverse rest rotation for this bone.
    bone.matrix_basis.identity()

    if bone.parent is not None:
        inv_parent = bone.parent.matrix.to_3x3().inverted()
        inv_rest_quat = \
            (inv_parent @ bone.matrix.to_3x3()).to_quaternion().inverted()
    else:
        inv_rest_quat = bone.matrix.to_quaternion().inverted()

    # Rotation keyframes in blender are independent from other data.
    for i in range(0, len(keyframes)):
        frame = keyframes[i] + startFrame

        smallestFrame = min(frame, smallestFrame)
        largestFrame = max(frame, largestFrame)

        if mode == "absolute" or mode is None:
            rotation = inv_rest_quat @ rotations[i]

            for axis, track in enumerate(tracks):
                utilityAddKeyframe(track, frame, rotation[axis], "CONSTANT")
        elif mode == "relative" or mode == "additive":
            rotation = rotations[i]

            for axis, track in enumerate(tracks):
                utilityAddKeyframe(track, frame, rotation[axis], "CONSTANT")

    for track in tracks:
        track.update()

    return (smallestFrame, largestFrame)


def importBlendShapeCurveNode(node, nodeName, animName, armature, startFrame):
    smallestFrame = sys.maxsize
    largestFrame = 0

    # We need to find every instance of the shape key in the armatures available meshes.
    # Each mesh has it's own copy of the key, which needs it's own curve...
    curves = []

    for child in armature.children_recursive:
        if child.type != "MESH":
            continue
        if not child.data.shape_keys:
            continue
        if not nodeName in child.data.shape_keys.key_blocks:
            continue

        mesh = child.data

        # Each mesh has it's own animation action, which contains the curves for each key.
        try:
            mesh.animation_data.action
        except:
            mesh.animation_data_create()

        action = mesh.animation_data.action or bpy.data.actions.new(
            animName)

        mesh.animation_data.action = action
        mesh.animation_data.action.use_fake_user = True

        if utilityIsVersionAtLeast(4, 4):
            mesh.animation_data.action_slot = \
                utilityGetOrCreateSlot(action)

        curve = action.fcurves.find(data_path="shape_keys.key_blocks[\"%s\"].value" %
                                    nodeName, index=0) or action.fcurves.new(data_path="shape_keys.key_blocks[\"%s\"].value" %
                                                                             nodeName, index=0, action_group=nodeName)

        # We found a mesh that has a matching shape key, add the curve.
        curves.append(curve)

    # For every curve add the values directly.
    keyFrameBuffer = node.KeyFrameBuffer()
    keyValueBuffer = node.KeyValueBuffer()

    for curve in curves:
        for frame, value in zip(keyFrameBuffer, keyValueBuffer):
            frame = frame + startFrame

            smallestFrame = min(frame, smallestFrame)
            largestFrame = max(frame, largestFrame)

            utilityAddKeyframe(curve, frame, value, "LINEAR")

    return (smallestFrame, largestFrame)


def importScaleCurveNodes(nodes, nodeName, fcurves, poseBones, path, startFrame, overrides):
    smallestFrame = sys.maxsize
    largestFrame = 0

    if not nodeName in poseBones:
        return (smallestFrame, largestFrame)

    bone = poseBones[nodeName]
    mode = None

    for node in nodes:
        if node is not None:
            mode = node.Mode()

    mode = utilityResolveCurveModeOverride(bone, mode, overrides, isScale=True)

    tracks = [utilityGetOrCreateCurve(fcurves, poseBones, nodeName, x) for x in [
        ("scale", 0), ("scale", 1), ("scale", 2)]]

    # This works around the issue where EditBone.matrix destroys the scale which means that
    # a model which has an non-1.0 scale when the bind pose is applied will not scale correctly.
    bindPoseInvMatrix = utilityGetBindposeScale(bone).inverted()

    # Scale keyframes are independant from other data.
    for axis, node in enumerate(nodes):
        if node is None:
            continue

        keyFrameBuffer = node.KeyFrameBuffer()
        keyValueBuffer = node.KeyValueBuffer()

        scale = Vector((1.0, 1.0, 1.0))

        for i, frame in enumerate(keyFrameBuffer):
            frame = frame + startFrame

            smallestFrame = min(frame, smallestFrame)
            largestFrame = max(frame, largestFrame)

            if mode == "absolute" or mode is None:
                scale[axis] = keyValueBuffer[i]

                value = (bindPoseInvMatrix @
                         Matrix.LocRotScale(None, None, scale)).to_scale()

                utilityAddKeyframe(tracks[axis], frame, value[axis], "LINEAR")
            elif mode == "relative" or mode == "additive":
                utilityAddKeyframe(
                    tracks[axis], frame, keyValueBuffer[i], "LINEAR")

    # Reset temporary matrices used to calculate the keyframe locations.
    bone.matrix_basis.identity()

    for track in tracks:
        track.update()

    return (smallestFrame, largestFrame)


def importLocCurveNodes(nodes, nodeName, fcurves, poseBones, path, startFrame, overrides):
    smallestFrame = sys.maxsize
    largestFrame = 0

    if not nodeName in poseBones:
        return (smallestFrame, largestFrame)

    bone = poseBones[nodeName]
    mode = None

    for node in nodes:
        if node is not None:
            mode = node.Mode()

    mode = utilityResolveCurveModeOverride(
        bone, mode, overrides, isTranslate=True)

    tracks = [utilityGetOrCreateCurve(fcurves, poseBones, nodeName, x) for x in [
        ("location", 0), ("location", 1), ("location", 2)]]

    lastFrame = 0

    # Location keyframes in blender are post-rotation, and as such, require all components in order to animate properly.
    for axis, node in enumerate(nodes):
        if node is None:
            if bone.parent is None:
                utilityAddKeyframe(
                    tracks[axis], 0, bone.matrix.translation[axis], "LINEAR")
            else:
                utilityAddKeyframe(tracks[axis], 0,
                                   (bone.parent.matrix.inverted() @ bone.matrix).translation[axis], "LINEAR")
        else:
            keyFrameBuffer = node.KeyFrameBuffer()
            keyValueBuffer = node.KeyValueBuffer()

            for i, frame in enumerate(keyFrameBuffer):
                utilityAddKeyframe(
                    tracks[axis], frame, keyValueBuffer[i], "LINEAR")
                lastFrame = max(lastFrame, frame)

    keyFrameBuffer = []
    keyValueBuffer = []

    # Now, we need to bake the curves into sampled keyframes that collectively animate the transform.
    for frame in range(0, lastFrame + 1):
        keyFrameBuffer.append(frame)
        keyValueBuffer.append((tracks[0].evaluate(
            frame), tracks[1].evaluate(frame), tracks[2].evaluate(frame)))

    # Now, we need to actually generate keyframes for each of the tracks based on the mode.
    for track in tracks:
        utilityClearKeyframePoints(track)

    for i, frame in enumerate(keyFrameBuffer):
        offset = Vector(keyValueBuffer[i])

        frame = frame + startFrame

        smallestFrame = min(frame, smallestFrame)
        largestFrame = max(frame, largestFrame)

        if mode == "absolute" or mode is None:
            if bone.parent is not None:
                bone.matrix.translation = bone.parent.matrix @ offset
            else:
                bone.matrix.translation = offset
        elif mode == "relative" or mode == "additive":
            bone.matrix_basis.translation = bone.bone.matrix.inverted() @ offset

        for axis, track in enumerate(tracks):
            utilityAddKeyframe(track, frame, bone.location[axis], "LINEAR")

    # Reset temporary matrices used to calculate the keyframe locations.
    bone.matrix_basis.identity()

    for track in tracks:
        track.update()

    return (smallestFrame, largestFrame)


def importNotificationTrackNode(node, action, frameStart):
    smallestFrame = sys.maxsize
    largestFrame = 0

    frameBuffer = node.KeyFrameBuffer()

    for frame in frameBuffer:
        frame = frame + frameStart

        notetrack = action.pose_markers.new(node.Name())
        notetrack.frame = frame

        smallestFrame = min(frame, smallestFrame)
        largestFrame = max(frame, largestFrame)

    return (smallestFrame, largestFrame)


def importAnimationNode(self, node, path, selectedObject):
    # Check that the selected object is an 'ARMATURE'.
    if selectedObject is None or selectedObject.type != 'ARMATURE':
        raise Exception(
            "You must select an armature to apply the animation to.")

    # Extract the name of this anim from the path.
    animName = node.Name() or os.path.splitext(os.path.basename(path))[0]

    try:
        selectedObject.animation_data.action
    except:
        selectedObject.animation_data_create()

    # Ensure that all pose bones have rotation quaternion values.
    for bone in selectedObject.pose.bones.data.bones:
        bone.rotation_mode = 'QUATERNION'

    bpy.ops.object.mode_set(mode='POSE')

    if self.import_reset:
        action = bpy.data.actions.new(animName)
    else:
        action = selectedObject.animation_data.action or bpy.data.actions.new(
            animName)

    selectedObject.animation_data.action = action
    selectedObject.animation_data.action.use_fake_user = True

    if utilityIsVersionAtLeast(4, 4):
        selectedObject.animation_data.action_slot = \
            utilityGetOrCreateSlot(action)

    scene = bpy.context.scene
    scene.render.fps = round(node.Framerate())
    scene.render.fps_base = scene.render.fps / node.Framerate()

    # We need to determine the proper time to import the curves, for example
    # the user may want to import at the current scene time, and that would require
    # fetching once here, then passing to the curve importer.
    wantedSmallestFrame = sys.maxsize
    wantedLargestFrame = 1

    if self.import_time:
        startFrame = scene.frame_current
    else:
        startFrame = 0

    curves = node.Curves()
    curveModeOverrides = node.CurveModeOverrides()

    # Create a list of pose bones that match the curves.
    poseBones = {}

    for x in curves:
        for bone in selectedObject.pose.bones:
            if x.NodeName().lower() == bone.name.lower():
                poseBones[x.NodeName()] = bone

    if self.import_reset:
        for bone in selectedObject.pose.bones:
            bone.matrix_basis.identity()

        # Make sure the depsgraph is updated before processing the next animation.
        bpy.context.evaluated_depsgraph_get().update()

    # Create a list of the separate location and scale curves because their curves are separate.
    locCurves = {}
    scaleCurves = {}

    # Used to warn the user about the need to blend the additive animation.
    hasAdditiveCurve = False

    for x in curves:
        nodeName = x.NodeName()
        property = x.KeyPropertyName()
        hasAdditiveCurve = hasAdditiveCurve or x.Mode() == "additive"

        if property == "rq":
            (smallestFrame, largestFrame) = importRotCurveNode(
                x, nodeName, action.fcurves, poseBones, path, startFrame, curveModeOverrides)
            wantedSmallestFrame = min(smallestFrame, wantedSmallestFrame)
            wantedLargestFrame = max(largestFrame, wantedLargestFrame)
        elif property == "bs":
            (smallestFrame, largestFrame) = importBlendShapeCurveNode(
                x, nodeName, animName, selectedObject, startFrame)
            wantedSmallestFrame = min(smallestFrame, wantedSmallestFrame)
            wantedLargestFrame = max(largestFrame, wantedLargestFrame)
        elif property == "tx":
            utilityStashCurveComponent(locCurves, x, nodeName, 0)
        elif property == "ty":
            utilityStashCurveComponent(locCurves, x, nodeName, 1)
        elif property == "tz":
            utilityStashCurveComponent(locCurves, x, nodeName, 2)
        elif property == "sx":
            utilityStashCurveComponent(scaleCurves, x, nodeName, 0)
        elif property == "sy":
            utilityStashCurveComponent(scaleCurves, x, nodeName, 1)
        elif property == "sz":
            utilityStashCurveComponent(scaleCurves, x, nodeName, 2)

    for nodeName, x in locCurves.items():
        (smallestFrame, largestFrame) = importLocCurveNodes(
            x, nodeName, action.fcurves, poseBones, path, startFrame, curveModeOverrides)
        wantedSmallestFrame = min(smallestFrame, wantedSmallestFrame)
        wantedLargestFrame = max(largestFrame, wantedLargestFrame)

    for nodeName, x in scaleCurves.items():
        (smallestFrame,  largestFrame) = importScaleCurveNodes(
            x, nodeName, action.fcurves, poseBones, path, startFrame, curveModeOverrides)
        wantedSmallestFrame = min(smallestFrame, wantedSmallestFrame)
        wantedLargestFrame = max(largestFrame, wantedLargestFrame)

    for x in node.Notifications():
        (smallestFrame, largestFrame) = importNotificationTrackNode(
            x, action, startFrame)
        wantedSmallestFrame = min(smallestFrame, wantedSmallestFrame)
        wantedLargestFrame = max(largestFrame, wantedLargestFrame)

    # Tell the user that we had an additive animation if necessary.
    if hasAdditiveCurve:
        self.report(
            {"WARNING"}, "Animation %s is additive and needs to be blended using the NLA editor." % animName)

    # Set the animation segment.
    if wantedSmallestFrame == sys.maxsize:
        wantedSmallestFrame = 0

    scene.frame_start = wantedSmallestFrame
    scene.frame_end = wantedLargestFrame
    scene.frame_current = wantedSmallestFrame

    bpy.context.evaluated_depsgraph_get().update()

    bpy.context.view_layer.objects.active = selectedObject
    bpy.ops.object.mode_set(mode='OBJECT')


def importInstanceNodes(self, nodes, context, path):
    rootPath = context.scene.cast_properties.import_scenes_path

    if len(rootPath) == 0:
        raise Exception("Unable to import instances without a root directory!")

    uniqueInstances = {}

    for instance in nodes:
        refs = os.path.join(rootPath, instance.ReferenceFile().Path())

        if refs in uniqueInstances:
            uniqueInstances[refs].append(instance)
        else:
            uniqueInstances[refs] = [instance]

    name = os.path.splitext(os.path.basename(path))[0]

    # Used to contain the original imported scene, will be set to hidden once completed.
    baseGroup = bpy.data.collections.new("%s_scenes" % name)
    # Used to contain every instance.
    instanceGroup = bpy.data.collections.new("%s_instances" % name)

    for instancePath, instances in uniqueInstances.items():
        instanceName = os.path.splitext(os.path.basename(instancePath))[0]

        try:
            importCast(self, context, instancePath)
        except:
            self.report(
                {'WARNING'}, "Instance: %s failed to import or not found, skipping..." % instancePath)
            continue

        if not bpy.context.view_layer.active_layer_collection.collection.children:
            self.report(
                {'WARNING'}, "Instance: %s did not import anything, skipping..." % instancePath)
            continue

        base = bpy.context.view_layer.active_layer_collection.collection.children[-1]
        bpy.context.view_layer.active_layer_collection.collection.children.unlink(
            base)

        baseGroup.children.link(base)

        for instance in instances:
            newInstance = bpy.data.objects.new(
                instance.Name() or instanceName, None)
            newInstance.instance_type = 'COLLECTION'
            newInstance.instance_collection = base
            newInstance.show_instancer_for_render = False
            newInstance.show_instancer_for_viewport = False

            position = instance.Position()
            rotation = instance.Rotation()
            scale = instance.Scale()

            newInstance.location = Vector(position)
            newInstance.rotation_mode = 'QUATERNION'
            newInstance.rotation_quaternion = Quaternion(
                (rotation[3], rotation[0], rotation[1], rotation[2]))
            newInstance.scale = Vector(scale)

            instanceGroup.objects.link(newInstance)

    baseGroup.hide_viewport = True

    # Link the groups to the scene at the end for performance.
    bpy.context.view_layer.active_layer_collection.collection.children.link(
        baseGroup)
    bpy.context.view_layer.active_layer_collection.collection.children.link(
        instanceGroup)


def importCast(self, context, path):
    cast = Cast.load(path)

    instances = []

    # Grab the selected object before we start importing because it deselects after creating another object.
    selectedObject = bpy.context.object

    for root in cast.Roots():
        for child in root.ChildrenOfType(Model):
            importModelNode(self, child, path, selectedObject)
        for child in root.ChildrenOfType(Animation):
            importAnimationNode(self, child, path, selectedObject)
        for child in root.ChildrenOfType(Instance):
            instances.append(child)

    if len(instances) > 0:
        importInstanceNodes(self, instances, context, path)


def load(self, context, filepath=""):
    importCast(self, context, filepath)

    bpy.context.view_layer.update()
