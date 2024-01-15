import struct

castHashBase = 0x534E495752545250


def castNextHash():
    global castHashBase

    hash = castHashBase
    castHashBase += 1

    return hash


def castTypeForMaximum(values):
    maximum = max(values)

    if maximum <= 0xFF:
        return "b"
    elif maximum <= 0xFFFF:
        return "h"
    else:
        return "i"


class CastString_t(object):
    __slots__ = ("value")

    def __init__(self, file=None):
        self.value = ""

        if file is not None:
            self.load(file)

    def load(self, file):
        bytes = b''
        b = file.read(1)
        while not b == b'\x00':
            bytes += b
            b = file.read(1)
        self.value = bytes.decode("utf-8")

    def save(self, file):
        file.write(self.value.encode("utf-8"))
        file.write(b'\x00')


class CastProperty_t(object):
    __slots__ = ("size", "fmt", "identifier", "array")

    def __init__(self, identifier=None):
        switcher = {
            'b': [1, "B", 1],
            'h': [2, "H", 1],
            'i': [4, "I", 1],
            'l': [8, "Q", 1],
            'f': [4, "f", 1],
            'd': [8, "d", 1],
            's': [0, "s", 1],
            '2v': [8, "2f", 2],
            '3v': [12, "3f", 3],
            '4v': [16, "4f", 4]
        }

        if identifier is None:
            self.size = 0
            self.fmt = ""
            self.identifier = None
            self.array = 1
            return

        self.size = switcher[identifier][0]
        self.fmt = switcher[identifier][1]
        self.array = switcher[identifier][2]
        self.identifier = identifier


class CastColor:
    """Utility methods for working with colors."""

    @staticmethod
    def fromInteger(color):
        """Unpacks a color value to a tuple of rgba (float)."""
        bytes = bytearray(struct.pack("<I", color))

        return (bytes[0] / 255.0, bytes[1] / 255.0, bytes[2] / 255.0, bytes[3] / 255.0)

    @staticmethod
    def toInteger(color):
        """Packs a tuple of rgba (float) to a color value."""
        r = int(max(min(color[0] * 255.0, 255.0), 0.0))
        g = int(max(min(color[1] * 255.0, 255.0), 0.0))
        b = int(max(min(color[2] * 255.0, 255.0), 0.0))
        a = int(max(min(color[3] * 255.0, 255.0), 0.0))

        return struct.unpack("<I", bytearray([r, g, b, a]))[0]


class CastProperty(object):
    """A single property for a cast node."""

    __slots__ = ("name", "type", "values")

    def __init__(self, file=None, name=None, type=None):
        self.name = name or ""
        self.type = CastProperty_t(type)
        self.values = []

        if file is not None:
            self.load(file)

    def load(self, file):
        """Loads a cast property from the given file."""
        header = struct.unpack("2sHI", file.read(0x8))

        self.name = struct.unpack(("%ds" % header[1]), file.read(header[1]))[
            0].decode("utf-8")
        self.type = CastProperty_t(header[0].decode("utf-8").strip('\0'))

        if (self.type.size == 0 and self.type.fmt == "s"):
            self.values = [CastString_t(file).value]
        else:
            self.values = [None] * header[2]
            self.values = struct.unpack(
                self.type.fmt * header[2], file.read(self.type.size * header[2]))

    def save(self, file):
        """Saves this cast property to the given file."""
        identifier = self.type.identifier.encode("utf-8")
        name = self.name.encode("utf-8")

        file.write(struct.pack(
            "2sHI", identifier, len(name), int(len(self.values) / self.type.array)))
        file.write(name)

        if self.type.size == 0 and self.type.fmt == "s":
            string = CastString_t()
            string.value = self.values[0]

            string.save(file)
        else:
            file.write(struct.pack(self.type.fmt *
                                   int(len(self.values) / self.type.array), *self.values))

    def length(self):
        """Returns the length in bytes of this cast property."""
        result = 0x8

        result += len(self.name.encode("utf-8"))

        if self.type.size == 0 and self.type.fmt == "s":
            result += len(self.values[0].encode("utf-8")) + 1
        else:
            result += self.type.size * int(len(self.values) / self.type.array)

        return result


class CastNode(object):
    """A single generic cast node."""

    __slots__ = ("identifier", "hash", "parentNode",
                 "childNodes", "properties")

    def __init__(self, identifier=0):
        self.childNodes = []
        self.properties = {}
        self.identifier = identifier
        self.hash = castNextHash()
        self.parentNode = None

    def ChildrenOfType(self, pType):
        """Finds all children that match the given type."""
        return [x for x in self.childNodes if x.__class__ is pType]

    def ChildByHash(self, hash):
        """Finds a child by the given hash."""
        find = [x for x in self.childNodes if x.hash == hash]
        if len(find) > 0:
            return find[0]
        return None

    def Hash(self):
        """The unique hash of this node."""
        return self.hash

    def CreateProperty(self, name, type):
        """Creates a new property with the given name and type."""
        property = CastProperty(file=None, name=name, type=type)
        self.properties[name] = property
        return property

    def CreateChild(self, child):
        """Creates a new child in this node."""
        child.parentNode = self
        self.childNodes.append(child)
        return child

    @staticmethod
    def load(file):
        """Loads a cast node from the given file."""
        header = struct.unpack("IIQII", file.read(0x18))

        if header[0] in typeSwitcher:
            node = typeSwitcher[header[0]]()
        else:
            node = typeSwitcher[None]()

        node.identifier = header[0]
        node.childNodes = [None] * header[4]
        node.hash = header[2]

        for i in range(header[3]):
            prop = CastProperty(file)
            node.properties[prop.name] = prop
        for i in range(header[4]):
            node.childNodes[i] = CastNode.load(file)
            node.childNodes[i].parentNode = node

        return node

    def save(self, file):
        """Saves this cast node to the given file."""
        file.write(struct.pack("IIQII", self.identifier, self.length(),
                               self.hash, len(self.properties), len(self.childNodes)))

        for property in self.properties.values():
            property.save(file)
        for childNode in self.childNodes:
            childNode.save(file)

    def length(self):
        """Returns the length in bytes of this cast node."""
        result = 0x18

        for property in self.properties.values():
            result += property.length()
        for childNode in self.childNodes:
            result += childNode.length()

        return result


class Model(CastNode):
    """A 3d model with meshes, materials, and a skeleton."""

    def __init__(self):
        super(Model, self).__init__(0x6C646F6D)

    def Name(self):
        """The name of this model."""
        n = self.properties.get("n")
        if n is not None:
            return n.values[0]
        return None

    def SetName(self, name):
        """Sets the name of this model."""
        self.CreateProperty("n", "s").values = [name]

    def Skeleton(self):
        """The skeleton embedded in this model."""
        find = self.ChildrenOfType(Skeleton)
        if len(find) > 0:
            return find[0]
        return None

    def CreateSkeleton(self):
        """Creates a new skeleton in this model."""
        return self.CreateChild(Skeleton())

    def Meshes(self):
        """A collection of meshes for this model."""
        return self.ChildrenOfType(Mesh)

    def CreateMesh(self):
        """Creates a new mesh in this model."""
        return self.CreateChild(Mesh())

    def Materials(self):
        """A colection of materials for this model."""
        return self.ChildrenOfType(Material)

    def CreateMaterial(self):
        """Creates a new material in this model."""
        return self.CreateChild(Material())

    def BlendShapes(self):
        """A collection of blend shapes for this model."""
        return self.ChildrenOfType(BlendShape)

    def CreateBlendShape(self):
        """Creates a new blend shape in this model."""
        return self.CreateChild(BlendShape())


class Animation(CastNode):
    """A 3d animation and it's collection of curves."""

    def __init__(self):
        super(Animation, self).__init__(0x6D696E61)

    def Name(self):
        """The name of this animation."""
        n = self.properties.get("n")
        if n is not None:
            return n.values[0]
        return None

    def SetName(self, name):
        """Sets the name of this animation."""
        self.CreateProperty("n", "s").values = [name]

    def Skeleton(self):
        """The skeleton embedded in this animation."""
        find = self.ChildrenOfType(Skeleton)
        if len(find) > 0:
            return find[0]
        return None

    def CreateSkeleton(self):
        """Creates a new skeleton in this animation."""
        return self.CreateChild(Skeleton())

    def Curves(self):
        """The collection of curves for this animation."""
        return self.ChildrenOfType(Curve)

    def CreateCurve(self):
        """Creates a new curve in this animation."""
        return self.CreateChild(Curve())

    def Notifications(self):
        """The collection of notification tracks for this animation."""
        return self.ChildrenOfType(NotificationTrack)

    def CreateNotification(self):
        """Creates a new notification track in this animation."""
        return self.CreateChild(NotificationTrack())

    def Framerate(self):
        """The framerate this animation plays at."""
        fr = self.properties.get("fr")
        if fr is not None:
            return fr.values[0]
        return None

    def SetFramerate(self, framerate):
        """Sets the framerate this animation plays at."""
        self.CreateProperty("fr", "f").values = [framerate]

    def Looping(self):
        """Whether or not this animation should loop."""
        lo = self.properties.get("lo")
        if lo is not None:
            return lo.values[0] >= 1
        return False

    def SetLooping(self, enabled):
        """Sets whether or not this animation should loop."""
        if enabled:
            self.CreateProperty("lo", "b").values = [1]
        else:
            self.CreateProperty("lo", "b").values = [0]


class Curve(CastNode):
    """A curve from an animation that animates a node's property."""

    def __init__(self):
        super(Curve, self).__init__(0x76727563)

    def NodeName(self):
        """The name of the node to animate."""
        nn = self.properties.get("nn")
        if nn is not None:
            return nn.values[0]
        return None

    def SetNodeName(self, name):
        """Sets the name of the node to animate."""
        self.CreateProperty("nn", "s").values = [name]

    def KeyPropertyName(self):
        """The property of the node to animate."""
        kp = self.properties.get("kp")
        if kp is not None:
            return kp.values[0]
        return None

    def SetKeyPropertyName(self, name):
        """Sets the property of the node to animate."""
        self.CreateProperty("kp", "s").values = [name]

    def KeyFrameBuffer(self):
        """The collection of keyframes."""
        kb = self.properties.get("kb")
        if kb is not None:
            return kb.values
        return None

    def SetKeyFrameBuffer(self, values):
        """Sets the collection of keyframes."""
        self.CreateProperty("kb", castTypeForMaximum(
            values)).values = list(values)

    def KeyValueBuffer(self):
        """The collection of keyframe values."""
        kv = self.properties.get("kv")
        if kv is not None:
            return kv.values
        return None

    def SetFloatKeyValueBuffer(self, values):
        """Sets the collection of keyframe values as a collection of floats."""
        self.CreateProperty("kv", "f").values = list(values)

    def SetVec4KeyValueBuffer(self, values):
        """Sets the collection of keyframe values as a collection of vec4s."""
        self.CreateProperty("kv", "4v").values = list(sum(values, ()))

    def SetByteKeyValueBuffer(self, values):
        """Sets the collection of keyframe values as a collection of bytes."""
        self.CreateProperty("kv", "b").values = list(values)

    def Mode(self):
        """The mode for this animation."""
        m = self.properties.get("m")
        if m is not None:
            return m.values[0]
        return None

    def SetMode(self, mode):
        """Sets the mode for this animation."""
        self.CreateProperty("m", "s").values = [mode]

    def AdditiveBlendWeight(self):
        """The weight to use when blending this animation."""
        ab = self.properties.get("ab")
        if ab is not None:
            return ab.values[0]
        return 1.0

    def SetAdditiveBlendWeight(self, value):
        """Sets the weight to use when blending this animation."""
        self.CreateProperty("ab", "f").values = [value]


class NotificationTrack(CastNode):
    """The notification track for an animation."""

    def __init__(self):
        super(NotificationTrack, self).__init__(0x6669746E)

    def Name(self):
        """The name of the notification."""
        n = self.properties.get("n")
        if n is not None:
            return n.values[0]
        return None

    def SetName(self, name):
        """Sets the name of the notification."""
        self.CreateProperty("n", "s").values = [name]

    def KeyFrameBuffer(self):
        """A collection of keyframes this notification fires on."""
        kb = self.properties.get("kb")
        if kb is not None:
            return kb.values
        return None

    def SetKeyFrameBuffer(self, values):
        """Sets the collection of keyframes this notification fires on."""
        self.CreateProperty("kb", castTypeForMaximum(
            values)).values = list(values)


class Mesh(CastNode):
    """A 3d mesh for a model."""

    def __init__(self):
        super(Mesh, self).__init__(0x6873656D)

    def Name(self):
        """The name of this mesh."""
        n = self.properties.get("n")
        if n is not None:
            return n.values[0]
        return None

    def SetName(self, name):
        """Sets the name of this mesh."""
        self.CreateProperty("n", "s").values = [name]

    def VertexCount(self):
        """Gets the number of vertices in this mesh."""
        vp = self.properties.get("vp")
        if vp is not None:
            return int(len(vp.values) / 3)

    def FaceCount(self):
        """Gets the number of faces in this mesh."""
        f = self.properties.get("f")
        if f is not None:
            return int(len(f.values) / 3)

    def UVLayerCount(self):
        """Gets the number of uv layers in this mesh."""
        uc = self.properties.get("ul")
        if uc is not None:
            return uc.values[0]
        return 0

    def SetUVLayerCount(self, count):
        """Sets the number of uv layers in this mesh."""
        self.CreateProperty("ul", "b").values = [count]

    def MaximumWeightInfluence(self):
        """The maximum weight influence for this mesh."""
        mi = self.properties.get("mi")
        if mi is not None:
            return mi.values[0]
        return 0

    def SetMaximumWeightInfluence(self, maximum):
        """Sets the maximum weight influence for this mesh."""
        self.CreateProperty("mi", "b").values = [maximum]

    def SkinningMethod(self):
        """The skinning method used for this mesh."""
        sm = self.properties.get("sm")
        if sm is not None:
            return sm.values[0]
        return "linear"

    def SetSkinningMethod(self, method):
        """Sets the skinning method used for this mesh."""
        self.CreateProperty("sm", "s").values = [method]

    def FaceBuffer(self):
        """The collection of faces for this mesh."""
        f = self.properties.get("f")
        if f is not None:
            return f.values
        return None

    def SetFaceBuffer(self, values):
        """Sets the collection of faces for this mesh."""
        self.CreateProperty("f", castTypeForMaximum(values)
                            ).values = list(values)

    def VertexPositionBuffer(self):
        """The collection of vertex positions for this mesh."""
        vp = self.properties.get("vp")
        if vp is not None:
            return vp.values
        return None

    def SetVertexPositionBuffer(self, values):
        """Sets the collection of vertex positions for this mesh."""
        self.CreateProperty("vp", "3v").values = list(sum(values, ()))

    def VertexNormalBuffer(self):
        """The collection of vertex normals for this mesh."""
        vn = self.properties.get("vn")
        if vn is not None:
            return vn.values
        return None

    def SetVertexNormalBuffer(self, values):
        """Sets the collection of vertex normals for this mesh."""
        self.CreateProperty("vn", "3v").values = list(sum(values, ()))

    def VertexTangentBuffer(self):
        """The collection of vertex tangents for this mesh."""
        vt = self.properties.get("vt")
        if vt is not None:
            return vt.values
        return None

    def SetVertexTangentBuffer(self, values):
        """Sets the collection of vertex tangents for this mesh."""
        self.CreateProperty("vt", "3v").values = list(sum(values, ()))

    def VertexColorBuffer(self):
        """The collection of vertex colors for this mesh."""
        vc = self.properties.get("vc")
        if vc is not None:
            return vc.values
        return None

    def SetVertexColorBuffer(self, values):
        """Sets the collection of vertex colors for this mesh."""
        self.CreateProperty("vc", "i").values = list(values)

    def VertexUVLayerBuffer(self, index):
        """The uv layer collection for the given layer index."""
        ul = self.properties.get("u%d" % index)
        if ul is not None:
            return ul.values
        return None

    def SetVertexUVLayerBuffer(self, index, values):
        """Sets the uv layer collection for the given layer index."""
        self.CreateProperty("u%d" % index, "2v").values = list(sum(values, ()))

    def VertexWeightBoneBuffer(self):
        """Gets the vertex weight bone index buffer."""
        wb = self.properties.get("wb")
        if wb is not None:
            return wb.values
        return None

    def SetVertexWeightBoneBuffer(self, values):
        """Sets the vertex weight bone index buffer."""
        self.CreateProperty("wb", castTypeForMaximum(
            values)).values = list(values)

    def VertexWeightValueBuffer(self):
        """Gets the vertex weight value buffer."""
        wv = self.properties.get("wv")
        if wv is not None:
            return wv.values
        return None

    def SetVertexWeightValueBuffer(self, values):
        """Sets the vertex weight value buffer."""
        self.CreateProperty("wv", "f").values = list(values)

    def Material(self):
        """Gets the material used for this mesh."""
        m = self.properties.get("m")
        if m is not None:
            return self.parentNode.ChildByHash(m.values[0])
        return None

    def SetMaterial(self, hash):
        """Sets the material hash for this mesh."""
        self.CreateProperty("m", "l").values = [hash]


class BlendShape(CastNode):
    """A blend shape deformer that defines a base mesh shape, and corrosponding target mesh shapes."""

    def __init__(self):
        super(BlendShape, self).__init__(0x68736C62)

    def Name(self):
        """The name of this blend shape deformer."""
        n = self.properties.get("n")
        if n is not None:
            return n.values[0]
        return None

    def SetName(self, name):
        """Sets the name of this blend shape deformer."""
        self.CreateProperty("n", "s").values = [name]

    def BaseShape(self):
        """The base mesh shape."""
        b = self.properties.get("b")
        if b is not None:
            return self.parentNode.ChildByHash(b.values[0])
        return None

    def SetBaseShape(self, hash):
        """Sets the base mesh shape."""
        self.CreateProperty("b", "l").values = [hash]

    def TargetShapes(self):
        """A collection of target mesh shapes."""
        t = self.properties.get("t")
        if t is not None:
            return [self.parentNode.ChildByHash(x) for x in t.values]
        return None

    def SetTargetShapes(self, hashes):
        """Sets a collection of target mesh shapes."""
        self.CreateProperty("t", "l").values = list(hashes)

    def TargetWeightScales(self):
        """A collection of target mesh scale values."""
        ts = self.properties.get("ts")
        if ts is not None:
            return ts.values
        return None

    def SetTargetWeightScales(self, scales):
        """Sets a collection of target mesh scale values."""
        self.CreateProperty("ts", "f").values = list(scales)


class Skeleton(CastNode):
    """A collection of bones for a model or animation."""

    def __init__(self):
        super(Skeleton, self).__init__(0x6C656B73)

    def Bones(self):
        """The collection of bones in this skeleton."""
        return self.ChildrenOfType(Bone)

    def CreateBone(self):
        """Creates a new bone in this skeleton."""
        return self.CreateChild(Bone())

    def IKHandles(self):
        """The collection of ik handles in this skeleton."""
        return self.ChildrenOfType(IKHandle)

    def CreateIKHandle(self):
        """Creates a new ik handle in this skeleton."""
        return self.CreateChild(IKHandle())

    def Constraints(self):
        """The collection of constraints in this skeleton."""
        return self.ChildrenOfType(Constraint)

    def CreateConstraint(self):
        """Creates a new constraint in this skeleton."""
        return self.CreateChild(Constraint())


class Bone(CastNode):
    """A 3d bone that belongs to a skeleton."""

    def __init__(self):
        super(Bone, self).__init__(0x656E6F62)

    def Name(self):
        """The name of this bone."""
        name = self.properties.get("n")
        if name is not None:
            return name.values[0]
        return None

    def SetName(self, name):
        """Sets the name of this bone."""
        self.CreateProperty("n", "s").values = [name]

    def ParentIndex(self):
        """The index of the parent bone in the skeleton. -1 is a root bone."""
        parent = self.properties.get("p")
        if parent is not None:
            # Since cast uses unsigned types, we must
            # convert to a signed integer, as the range is -1 - INT32_MAX
            parentUnsigned = parent.values[0]
            parentUnsigned = parentUnsigned & 0xffffffff
            return (parentUnsigned ^ 0x80000000) - 0x80000000
        return -1

    def SetParentIndex(self, index):
        """Sets the index of the parent bone in the skeleton. -1 is a root bone."""
        if index < 0:
            self.CreateProperty("p", "i").values = [index + 2**32]
        else:
            self.CreateProperty("p", "i").values = [index]

    def SegmentScaleCompensate(self):
        """Whether or not children bones are effected by the scale of this bone."""
        ssc = self.properties.get("ssc")
        if ssc is not None:
            return ssc.values[0] >= 1
        return None

    def SetSegmentScaleCompensate(self, enabled):
        """Sets whether or not children bones are effected by the scale of this bone."""
        if enabled:
            self.CreateProperty("ssc", "b").values = [1]
        else:
            self.CreateProperty("ssc", "b").values = [0]

    def LocalPosition(self):
        """The local space position of this bone."""
        localPos = self.properties.get("lp")
        if localPos is not None:
            return localPos.values
        return None

    def SetLocalPosition(self, position):
        """Sets the local space position of this bone."""
        self.CreateProperty("lp", "3v").values = list(position)

    def LocalRotation(self):
        """The local space rotation of this bone."""
        localRot = self.properties.get("lr")
        if localRot is not None:
            return localRot.values
        return None

    def SetLocalRotation(self, rotation):
        """Sets the local space rotation of this bone."""
        self.CreateProperty("lr", "4v").values = list(rotation)

    def WorldPosition(self):
        """The world position of this bone."""
        worldPos = self.properties.get("wp")
        if worldPos is not None:
            return worldPos.values
        return None

    def SetWorldPosition(self, position):
        """Sets the world position of this bone."""
        self.CreateProperty("wp", "3v").values = list(position)

    def WorldRotation(self):
        """The world rotation of this bone."""
        worldRot = self.properties.get("wr")
        if worldRot is not None:
            return worldRot.values
        return None

    def SetWorldRotation(self, rotation):
        """Sets the world rotation of this bone."""
        self.CreateProperty("wr", "4v").values = list(rotation)

    def Scale(self):
        """The scale of this bone."""
        scale = self.properties.get("s")
        if scale is not None:
            return scale.values
        return None

    def SetScale(self, scale):
        """Sets the scale of this bone."""
        self.CreateProperty("s", "3v").values = list(scale)


class IKHandle(CastNode):
    """Defines an ik chain and its constraints in the skeleton."""

    def __init__(self):
        super(IKHandle, self).__init__(0x64686B69)

    def Name(self):
        """The name of this ik handle."""
        name = self.properties.get("n")
        if name is not None:
            return name.values[0]
        return None

    def SetName(self, name):
        """Sets the name for this ik handle."""
        self.CreateProperty("n", "s").values = [name]

    def StartBone(self):
        """The bone which starts the chain."""
        sb = self.properties.get("sb")
        if sb is not None:
            return self.parentNode.ChildByHash(sb.values[0])
        return None

    def SetStartBone(self, hash):
        """Sets the bone which starts the chain."""
        self.CreateProperty("sb", "l").values = [hash]

    def EndBone(self):
        """The bone which ends the chain."""
        eb = self.properties.get("eb")
        if eb is not None:
            return self.parentNode.ChildByHash(eb.values[0])
        return None

    def SetEndBone(self, hash):
        """Sets the bone which ends the chain."""
        self.CreateProperty("eb", "l").values = [hash]

    def TargetBone(self):
        """The bone that acts as a target for the chain."""
        tb = self.properties.get("tb")
        if tb is not None:
            return self.parentNode.ChildByHash(tb.values[0])
        return None

    def SetTargetBone(self, hash):
        """Sets the bone that acts as a target for the chain."""
        self.CreateProperty("tb", "l").values = [hash]

    def PoleVectorBone(self):
        """The bone that acts as a pole vector for this chain."""
        pv = self.properties.get("pv")
        if pv is not None:
            return self.parentNode.ChildByHash(pv.values[0])
        return None

    def SetPoleVectorBone(self, hash):
        """Sets the bone that acts as a pole vector for this chain."""
        self.CreateProperty("pv", "l").values = [hash]

    def PoleBone(self):
        """The bone that acts as the pole (twist) for this chain."""
        pb = self.properties.get("pb")
        if pb is not None:
            return self.parentNode.ChildByHash(pb.values[0])
        return None

    def SetPoleBone(self, hash):
        """Sets the bone that acts as the pole (twist) for this chain."""
        self.CreateProperty("pb", "l").values = [hash]

    def UseTargetRotation(self):
        """Whether or not the target rotation effects the chain."""
        tr = self.properties.get("tr")
        if tr is not None:
            return tr.values[0] >= 1
        return False

    def SetUseTargetRotation(self, enabled):
        """Sets whether or not the target rotation effects the chain."""
        if enabled:
            self.CreateProperty("tr", "b").values = [1]
        else:
            self.CreateProperty("tr", "b").values = [0]


class Constraint(CastNode):
    """Defines a bone constraint in a skeleton."""

    def __init__(self):
        super(Constraint, self).__init__(0x74736E63)

    def Name(self):
        """The name of this constraint."""
        name = self.properties.get("n")
        if name is not None:
            return name.values[0]
        return None

    def SetName(self, name):
        """Sets the name for this constraint."""
        self.CreateProperty("n", "s").values = [name]

    def ConstraintType(self):
        """The type of constraint to configure."""
        ct = self.properties.get("ct")
        if ct is not None:
            return ct.values[0]
        return None

    def SetConstraintType(self, type):
        """Sets the type of constraint to configure."""
        self.CreateProperty("ct", "s").values = [type]

    def ConstraintBone(self):
        """The bone that is being constrained."""
        cb = self.properties.get("cb")
        if cb is not None:
            return self.parentNode.ChildByHash(cb.values[0])
        return None

    def SetConstraintBone(self, hash):
        """Sets the bone that is being constrained."""
        self.CreateProperty("cb", "l").values = [hash]

    def TargetBone(self):
        """The bone that is the target for the constraint."""
        tb = self.properties.get("tb")
        if tb is not None:
            return self.parentNode.ChildByHash(tb.values[0])
        return None

    def SetTargetBone(self, hash):
        """Sets the bone that is the target for the constraint."""
        self.CreateProperty("tb", "l").values = [hash]

    def MaintainOffset(self):
        """Whether or not the original offset is maintained."""
        mo = self.properties.get("mo")
        if mo is not None:
            return mo.values[0] >= 1
        return False

    def SetMaintainOffset(self, enabled):
        """Sets whether or not the original offset is maintained."""
        if enabled:
            self.CreateProperty("mo", "b").values = [1]
        else:
            self.CreateProperty("mo", "b").values = [0]

    def SkipX(self):
        """Whether or not to skip the x axis when constraining."""
        sx = self.properties.get("sx")
        if sx is not None:
            return sx.values[0] >= 1
        return False

    def SetSkipX(self, enabled):
        """Sets whether or not to skip the x axis when constraining."""
        if enabled:
            self.CreateProperty("sx", "b").values = [1]
        else:
            self.CreateProperty("sx", "b").values = [0]

    def SkipY(self):
        """Whether or not to skip the y axis when constraining."""
        sy = self.properties.get("sy")
        if sy is not None:
            return sy.values[0] >= 1
        return False

    def SetSkipY(self, enabled):
        """Sets whether or not to skip the y axis when constraining."""
        if enabled:
            self.CreateProperty("sy", "b").values = [1]
        else:
            self.CreateProperty("sy", "b").values = [0]

    def SkipZ(self):
        """Whether or not to skip the z axis when constraining."""
        sz = self.properties.get("sz")
        if sz is not None:
            return sz.values[0] >= 1
        return False

    def SetSkipZ(self, enabled):
        """Sets whether or not to skip the z axis when constraining."""
        if enabled:
            self.CreateProperty("sz", "b").values = [1]
        else:
            self.CreateProperty("sz", "b").values = [0]


class Material(CastNode):
    """Material contains a collection of slot:file mappings."""

    def __init__(self):
        super(Material, self).__init__(0x6C74616D)

    def Name(self):
        """The name for this material."""
        name = self.properties.get("n")
        if name is not None:
            return name.values[0]
        return None

    def SetName(self, name):
        """Sets the name for this material."""
        self.CreateProperty("n", "s").values = [name]

    def Type(self):
        """The type of this material (pbr)."""
        tp = self.properties.get("t")
        if tp is not None:
            return tp.values[0]
        return None

    def SetType(self, type):
        """Sets the type of this material (pbr)."""
        self.CreateProperty("t", "s").values = [type]

    def Slots(self):
        """A collection of slots for this material."""
        slots = {}
        for slot in self.properties:
            if slot != "n" and slot != "t":
                slots[slot] = self.ChildByHash(self.properties[slot].values[0])
        return slots

    def SetSlot(self, slot, hash):
        """Sets a slot for this material."""
        self.CreateProperty(slot, "l").values = [hash]

    def CreateFile(self):
        """Creates a new file reference in this material."""
        return self.CreateChild(File())


class File(CastNode):
    """An external file reference."""

    def __init__(self):
        super(File, self).__init__(0x656C6966)

    def Path(self):
        """The path of this file reference."""
        path = self.properties.get("p")
        if path is not None:
            return path.values[0]
        return None

    def SetPath(self, path):
        """Sets the path for this file reference."""
        self.CreateProperty("p", "s").values = [path]


class Instance(CastNode):
    """An instance of a cast scene."""

    def __init__(self):
        super(Instance, self).__init__(0x74736E69)

    def Name(self):
        """The name of this instance."""
        name = self.properties.get("n")
        if name is not None:
            return name.values[0]
        return None

    def SetName(self, name):
        """Sets the name of this instance."""
        self.CreateProperty("n", "s").values = [name]

    def ReferenceFile(self):
        """The referenced file for this instance."""
        reference = self.properties.get("rf")
        if reference is not None:
            return self.parentNode.ChildByHash(reference.values[0])
        return None

    def SetReferenceFile(self, hash):
        """Sets the referenced file hash for this instance."""
        self.CreateProperty("rf", "l").values = [hash]

    def Position(self):
        """The position of this instance."""
        position = self.properties.get("p")
        if position is not None:
            return position.values
        return None

    def SetPosition(self, position):
        """Sets the position of this instance."""
        self.CreateProperty("p", "3v").values = list(position)

    def Rotation(self):
        """The rotation of this instance."""
        rotation = self.properties.get("r")
        if rotation is not None:
            return rotation.values
        return None

    def SetRotation(self, rotation):
        """Sets the rotation of this instance."""
        self.CreateProperty("r", "4v").values = list(rotation)

    def Scale(self):
        """The scale of this instance."""
        scale = self.properties.get("s")
        if scale is not None:
            return scale.values
        return None

    def SetScale(self, scale):
        """Sets the scale of this instance."""
        self.CreateProperty("s", "3v").values = list(scale)


class Root(CastNode):
    """A root node."""

    def __init__(self):
        super(Root, self).__init__(0x746F6F72)

    def CreateModel(self):
        """Creates a new model node."""
        return self.CreateChild(Model())

    def CreateAnimation(self):
        """Creates a new animation node."""
        return self.CreateChild(Animation())

    def CreateInstance(self):
        """Creates a new instance node."""
        return self.CreateChild(Instance())


typeSwitcher = {
    None: CastNode,
    0x746F6F72: Root,
    0x6C646F6D: Model,
    0x6873656D: Mesh,
    0x68736C62: BlendShape,
    0x6C656B73: Skeleton,
    0x6D696E61: Animation,
    0x76727563: Curve,
    0x6669746E: NotificationTrack,
    0x656E6F62: Bone,
    0x64686B69: IKHandle,
    0x74736E63: Constraint,
    0x6C74616D: Material,
    0x656C6966: File,
    0x74736E69: Instance,
}


class Cast(object):
    """A cast file that holds a collection of cast nodes."""
    __slots__ = ("rootNodes")

    def __init__(self):
        self.rootNodes = []

    def Roots(self):
        """Returns the collection of root nodes in this cast file."""
        return [x for x in self.rootNodes]

    def CreateRoot(self):
        """Creates a new root node in this cast file."""
        root = Root()
        self.rootNodes.append(root)
        return root

    @staticmethod
    def load(path):
        """Loads a cast file from the given path."""
        try:
            file = open(path, "rb")
        except IOError:
            raise Exception("Could not open file for reading: %s\n" % path)

        header = struct.unpack("IIII", file.read(0x10))
        if header[0] != 0x74736163:
            raise Exception("Invalid cast file magic")

        cast = Cast()
        cast.rootNodes = [None] * header[2]

        for i in range(header[2]):
            cast.rootNodes[i] = CastNode.load(file)

        return cast

    def save(self, path):
        """Saves the cast file to the given path."""
        try:
            file = open(path, "wb")
        except IOError:
            raise Exception("Could not create file for writing: %s\n" % path)

        file.write(struct.pack(
            "IIII", 0x74736163, 0x1, len(self.rootNodes), 0))

        for rootNode in self.rootNodes:
            rootNode.save(file)
