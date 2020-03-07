import struct


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


class CastProperty_t(object):
    __slots__ = ("size", "fmt")

    def __init__(self, identifier=None):
        switcher = {
            'b': [1, "B"],
            'h': [2, "H"],
            'i': [4, "I"],
            'l': [8, "Q"],
            'f': [4, "f"],
            'd': [8, "d"],
            's': [0, "s"],
            '2v': [8, "2f"],        # byteswapped for performance
            '3v': [12, "3f"],      # byteswapped for performance
            '4v': [16, "4f"]      # byteswapped for performance
        }

        if identifier is None:
            self.size = 0
            self.fmt = ""
            return

        self.size = switcher[identifier][0]
        self.fmt = switcher[identifier][1]


class CastProperty(object):
    __slots__ = ("name", "type", "values")

    def __init__(self, file=None):
        self.name = ""
        self.type = CastProperty_t()
        self.values = []

        if file is not None:
            self.load(file)

    def load(self, file):
        header = struct.unpack("2sHI", file.read(0x8))

        self.name = struct.unpack(("%ds" % header[1]), file.read(header[1]))[0]
        self.type = CastProperty_t(header[0].strip("\0"))

        if (self.type.size == 0 and self.type.fmt == "s"):
            self.values = [CastString_t(file).value]
        else:
            self.values = [None] * header[2]
            self.values = struct.unpack(
                self.type.fmt * header[2], file.read(self.type.size * header[2]))


class CastNode(object):
    __slots__ = ("identifier", "hash", "parentNode",
                 "childNodes", "properties")

    def __init__(self):
        self.childNodes = []
        self.properties = {}
        self.identifier = 0
        self.hash = 0
        self.parentNode = None

    def ChildrenOfType(self, pType):
        return [x for x in self.childNodes if x.__class__ is pType]

    def ChildByHash(self, hash):
        find = [x for x in self.childNodes if x.hash == hash]
        if len(find) > 0:
            return find[0]
        return None

    @staticmethod
    def load(file):
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


class Model(CastNode):
    def __init__(self):
        super(Model, self).__init__()

    def Skeleton(self):
        find = self.ChildrenOfType(Skeleton)
        if len(find) > 0:
            return find[0]
        return None

    def Meshes(self):
        return self.ChildrenOfType(Mesh)

    def Materials(self):
        return self.ChildrenOfType(Material)


class Mesh(CastNode):
    def __init__(self):
        super(Mesh, self).__init__()

    def VertexCount(self):
        vp = self.properties.get("vp")
        if vp is not None:
            return len(vp.values) / 3

    def FaceCount(self):
        f = self.properties.get("f")
        if f is not None:
            return len(f.values) / 3

    def UVLayerCount(self):
        uc = self.properties.get("ul")
        if uc is not None:
            return uc.values[0]
        return 0

    def MaximumWeightInfluence(self):
        mi = self.properties.get("mi")
        if mi is not None:
            return mi.values[0]
        return 0

    def FaceBuffer(self):
        f = self.properties.get("f")
        if f is not None:
            return f.values
        return None

    def VertexPositionBuffer(self):
        vp = self.properties.get("vp")
        if vp is not None:
            return vp.values
        return None

    def VertexNormalBuffer(self):
        vn = self.properties.get("vn")
        if vn is not None:
            return vn.values
        return None

    def VertexColorBuffer(self):
        vc = self.properties.get("vc")
        if vc is not None:
            return vc.values
        return None

    def VertexUVLayerBuffer(self, index):
        ul = self.properties.get("u%d" % index)
        if ul is not None:
            return ul.values
        return None

    def VertexWeightBoneBuffer(self):
        wb = self.properties.get("wb")
        if wb is not None:
            return wb.values
        return None

    def VertexWeightValueBuffer(self):
        wv = self.properties.get("wv")
        if wv is not None:
            return wv.values
        return None

    def Material(self):
        m = self.properties.get("m")
        if m is not None:
            return self.parentNode.ChildByHash(m.values[0])
        return None


class Skeleton(CastNode):
    def __init__(self):
        super(Skeleton, self).__init__()

    def Bones(self):
        return self.ChildrenOfType(Bone)


class Bone(CastNode):
    def __init__(self):
        super(Bone, self).__init__()

    def Name(self):
        name = self.properties.get("n")
        if name is not None:
            return name.values[0]
        return None

    def ParentIndex(self):
        parent = self.properties.get("p")
        if parent is not None:
            # Since cast uses unsigned types, we must
            # convert to a signed integer, as the range is -1 - INT32_MAX
            parentUnsigned = parent.values[0]
            parentUnsigned = parentUnsigned & 0xffffffff
            return (parentUnsigned ^ 0x80000000) - 0x80000000
        return -1

    def SegmentScaleCompensate(self):
        ssc = self.properties.get("ssc")
        if ssc is not None:
            return ssc.values[0] == 1
        return None

    def LocalPosition(self):
        localPos = self.properties.get("lp")
        if localPos is not None:
            return localPos.values
        return None

    def LocalRotation(self):
        localRot = self.properties.get("lr")
        if localRot is not None:
            return localRot.values
        return None

    def WorldPosition(self):
        worldPos = self.properties.get("wp")
        if worldPos is not None:
            return worldPos.values
        return None

    def WorldRotation(self):
        worldRot = self.properties.get("wr")
        if worldRot is not None:
            return worldRot.values
        return None

    def Scale(self):
        scale = self.properties.get("s")
        if scale is not None:
            return scale.values
        return None


class Material(CastNode):
    def __init__(self):
        super(Material, self).__init__()

    def Name(self):
        name = self.properties.get("n")
        if name is not None:
            return name.values[0]
        return None

    def Type(self):
        tp = self.properties.get("t")
        if tp is not None:
            return tp.values[0]
        return None

    def Slots(self):
        slots = {}
        for slot in self.properties:
            if slot != "n" and slot != "t":
                slots[slot] = self.ChildByHash(self.properties[slot].values[0])
        return slots


class File(CastNode):
    def __init__(self):
        super(File, self).__init__()

    def Path(self):
        path = self.properties.get("p")
        if path is not None:
            return path.values[0]
        return None


typeSwitcher = {
    None: CastNode,
    0x6C646F6D: Model,
    0x6873656D: Mesh,
    0x6C656B73: Skeleton,
    0x656E6F62: Bone,
    0x6C74616D: Material,
    0x656C6966: File
}


class Cast(object):
    __slots__ = ("rootNodes")

    def __init__(self):
        self.rootNodes = []

    def load(self, path):
        try:
            file = open(path, "rb")
        except IOError:
            print("Could not open file for reading: %s\n" % path)
            return

        header = struct.unpack("IIII", file.read(0x10))
        if header[0] != 0x74736163:
            print("Invalid cast file magic")
            return

        self.rootNodes = [None] * header[2]
        for i in range(header[2]):
            self.rootNodes[i] = CastNode.load(file)

    def Roots(self):
        return [x for x in self.rootNodes]
