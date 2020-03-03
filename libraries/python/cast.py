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

        self.name = struct.unpack(("%ds" % header[1]), file.read(header[1]))
        self.type = CastProperty_t(header[0].strip("\0"))

        if (self.type.size == 0 and self.type.fmt == "s"):
            self.values = [CastString_t(file).value]
        else:
            self.values = [None] * header[2]
            self.values = struct.unpack(
                self.type.fmt * header[2], file.read(self.type.size * header[2]))


class CastNode(object):
    __slots__ = ("identifier", "childNodes", "properties")

    def __init__(self, file=None):
        self.childNodes = []
        self.properties = []
        self.identifier = 0

        if file is not None:
            self.load(file)

    def load(self, file):
        header = struct.unpack("IIQII", file.read(0x18))

        self.identifier = header[0]
        self.properties = [None] * header[3]
        self.childNodes = [None] * header[4]

        for i in range(header[3]):
            self.properties[i] = CastProperty(file)
        for i in range(header[4]):
            self.childNodes[i] = CastNode(file)


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
            self.rootNodes[i] = CastNode(file)
