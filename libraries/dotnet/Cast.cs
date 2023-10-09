using System;
using System.IO;
using System.Text;
using System.Collections.Generic;
using System.Runtime.CompilerServices;

namespace Cast
{
    class Globals
    {
        private static ulong NEXT_HASH = 0;
        private static readonly object HASH_LOCK = new object();

        [MethodImpl(MethodImplOptions.AggressiveInlining)]
        public static ulong CastNextHash()
        {
            lock (HASH_LOCK)
            {
                return NEXT_HASH++;
            }
        }

        [MethodImpl(MethodImplOptions.AggressiveInlining)]
        public static CastNode CastNodeSwitcher(uint Identifier)
        {
            switch (Identifier)
            {
                case 0x6C646F6D:
                    return new Model();
                case 0x6C656B73:
                    return new Skeleton();
                case 0x656E6F62:
                    return new Bone();
                case 0x6873656D:
                    return new Mesh();
                case 0x6C74616D:
                    return new Material();
                default:
                    return new CastNode(Identifier);
            }
        }

        [MethodImpl(MethodImplOptions.AggressiveInlining)]
        public static object CastPropertyLoad(BinaryReader Reader, string Type)
        {
            switch (Type)
            {
                case "b":
                    return Reader.ReadByte();
                case "h":
                    return Reader.ReadUInt16();
                case "i":
                    return Reader.ReadUInt32();
                case "l":
                    return Reader.ReadUInt64();
                case "f":
                    return Reader.ReadSingle();
                case "d":
                    return Reader.ReadDouble();
                case "s":
                    return ReadNullTerminatedString(Reader);
                case "2v":
                    return new Vector2()
                    {
                        X = Reader.ReadSingle(),
                        Y = Reader.ReadSingle()
                    };
                case "3v":
                    return new Vector3()
                    {
                        X = Reader.ReadSingle(),
                        Y = Reader.ReadSingle(),
                        Z = Reader.ReadSingle(),
                    };
                case "4v":
                    return new Vector4()
                    {
                        X = Reader.ReadSingle(),
                        Y = Reader.ReadSingle(),
                        Z = Reader.ReadSingle(),
                        W = Reader.ReadSingle(),
                    };
                default:
                    throw new Exception("Unsupported cast property type");
            }
        }

        public static string ReadNullTerminatedString(BinaryReader Reader)
        {
            var Buffer = new List<byte>(256);
            var Byte = Reader.ReadByte();

            while (Byte != 0)
            {
                Buffer.Add(Byte);
                Byte = Reader.ReadByte();
            }

            return Encoding.UTF8.GetString(Buffer.ToArray());
        }

        public static void WriteNullTerminatedStrring(BinaryWriter Writer, string Value)
        {
            Writer.Write(Encoding.UTF8.GetBytes(Value));
            Writer.Write((byte)0x0);
        }

        public static string BytesToString(byte[] Value)
        {
            return Encoding.UTF8.GetString(Value).Replace("\0", "");
        }

        public static byte[] StringToBytes(string Value)
        {
            return Encoding.UTF8.GetBytes(Value);
        }
    }

    class CastHeader
    {
        public uint Magic { get; set; }
        public uint Version { get; set; }
        public uint RootNodeCount { get; set; }
        public uint Flags { get; set; }

        public CastHeader()
        {
            Magic = 0x74736163;
            Version = 0x1;
            RootNodeCount = 0;
            Flags = 0;
        }

        public static CastHeader Load(BinaryReader Reader)
        {
            return new CastHeader()
            {
                Magic = Reader.ReadUInt32(),
                Version = Reader.ReadUInt32(),
                RootNodeCount = Reader.ReadUInt32(),
                Flags = Reader.ReadUInt32(),
            };
        }

        public void Save(BinaryWriter Writer)
        {
            Writer.Write(Magic);
            Writer.Write(Version);
            Writer.Write(RootNodeCount);
            Writer.Write(Flags);
        }
    }

    class CastNodeHeader
    {
        public uint Identifier { get; set; }
        public uint NodeSize { get; set; }
        public ulong NodeHash { get; set; }
        public uint PropertyCount { get; set; }
        public uint ChildCount { get; set; }

        public static CastNodeHeader Load(BinaryReader Reader)
        {
            return new CastNodeHeader()
            {
                Identifier = Reader.ReadUInt32(),
                NodeSize = Reader.ReadUInt32(),
                NodeHash = Reader.ReadUInt64(),
                PropertyCount = Reader.ReadUInt32(),
                ChildCount = Reader.ReadUInt32(),
            };
        }

        public void Save(BinaryWriter Writer)
        {
            Writer.Write(Identifier);
            Writer.Write(NodeSize);
            Writer.Write(NodeHash);
            Writer.Write(PropertyCount);
            Writer.Write(ChildCount);
        }
    }

    class CastPropertyHeader
    {
        public byte[] Type { get; set; }
        public ushort NameLength { get; set; }
        public uint ValueCount { get; set; }

        public static CastPropertyHeader Load(BinaryReader Reader)
        {
            return new CastPropertyHeader()
            {
                Type = Reader.ReadBytes(2),
                NameLength = Reader.ReadUInt16(),
                ValueCount = Reader.ReadUInt32(),
            };
        }

        public void Save(BinaryWriter Writer)
        {
            Writer.Write(Type);
            Writer.Write(NameLength);
            Writer.Write(ValueCount);
        }
    }

    /// <summary>
    /// A 2 component (XY) vector.
    /// </summary>
    public class Vector2
    {
        public float X { get; set; }
        public float Y { get; set; }
    }

    /// <summary>
    /// A 3 component (XYZ) vector.
    /// </summary>
    public class Vector3
    {
        public float X { get; set; }
        public float Y { get; set; }
        public float Z { get; set; }
    }

    /// <summary>
    /// A 4 component (XYZW) vector.
    /// </summary>
    public class Vector4
    {
        public float X { get; set; }
        public float Y { get; set; }
        public float Z { get; set; }
        public float W { get; set; }
    }

    public class Bone : CastNode
    {
        public Bone()
            : base(0x656E6F62)
        {
        }

        public string Name()
        {
            if (Properties.TryGetValue("n", out CastProperty Value))
            {
                return (string)Value.Values[0];
            }

            return null;
        }

        public int ParentIndex()
        {
            if (Properties.TryGetValue("p", out CastProperty Value))
            {
                return unchecked((int)Value.Values[0]);
            }

            return -1;
        }

        public bool SegmentScaleCompensate()
        {
            if (Properties.TryGetValue("ssc", out CastProperty Value))
            {
                return (int)Value.Values[0] == 1;
            }

            return false;
        }

        public Vector3 LocalPosition()
        {
            if (Properties.TryGetValue("lp", out CastProperty Value))
            {
                return (Vector3)Value.Values[0];
            }

            return null;
        }

        public Vector4 LocalRotation()
        {
            if (Properties.TryGetValue("lr", out CastProperty Value))
            {
                return (Vector4)Value.Values[0];
            }

            return null;
        }

        public Vector3 WorldPosition()
        {
            if (Properties.TryGetValue("wp", out CastProperty Value))
            {
                return (Vector3)Value.Values[0];
            }

            return null;
        }

        public Vector4 WorldRotation()
        {
            if (Properties.TryGetValue("wr", out CastProperty Value))
            {
                return (Vector4)Value.Values[0];
            }

            return null;
        }

        public Vector3 Scale()
        {
            if (Properties.TryGetValue("s", out CastProperty Value))
            {
                return (Vector3)Value.Values[0];
            }

            return null;
        }
    }

    public class Skeleton : CastNode
    {
        public Skeleton()
            : base(0x6C656B73)
        {
        }

        public List<Bone> Bones()
        {
            return ChildrenOfType<Bone>();
        }
    }

    public class Mesh : CastNode
    {
        public Mesh()
            : base(0x6873656D)
        {
        }

        public string Name()
        {
            if (Properties.TryGetValue("n", out CastProperty Value))
            {
                return (string)Value.Values[0];
            }

            return null;
        }

        public int VertexCount()
        {
            if (Properties.TryGetValue("vp", out CastProperty Value))
            {
                return Value.Values.Count;
            }

            return 0;
        }

        public int FaceCount()
        {
            if (Properties.TryGetValue("f", out CastProperty Value))
            {
                return Value.Values.Count / 3;
            }

            return 0;
        }

        public int UVLayerCount()
        {
            if (Properties.TryGetValue("ul", out CastProperty Value))
            {
                return (int)Value.Values[0];
            }

            return 0;
        }

        public int MaximumWeightInfluence()
        {
            if (Properties.TryGetValue("mi", out CastProperty Value))
            {
                return (int)Value.Values[0];
            }

            return 0;
        }

        public IEnumerable<int> FaceBuffer()
        {
            if (Properties.TryGetValue("f", out CastProperty Value))
            {
                foreach (var Item in Value.Values)
                {
                    yield return (int)Item;
                }
            }
        }

        public IEnumerable<Vector3> VertexPositionBuffer()
        {
            if (Properties.TryGetValue("vp", out CastProperty Value))
            {
                foreach (var Item in Value.Values)
                {
                    yield return (Vector3)Item;
                }
            }
        }

        public IEnumerable<Vector3> VertexNormalBuffer()
        {
            if (Properties.TryGetValue("vn", out CastProperty Value))
            {
                foreach (var Item in Value.Values)
                {
                    yield return (Vector3)Item;
                }
            }
        }

        public IEnumerable<Vector3> VertexTangentBuffer()
        {
            if (Properties.TryGetValue("vt", out CastProperty Value))
            {
                foreach (var Item in Value.Values)
                {
                    yield return (Vector3)Item;
                }
            }
        }

        public IEnumerable<uint> VertexColorBuffer()
        {
            if (Properties.TryGetValue("vc", out CastProperty Value))
            {
                foreach (var Item in Value.Values)
                {
                    yield return (uint)Item;
                }
            }
        }

        public IEnumerable<Vector2> VertexUVLayerBuffer(int Index)
        {
            if (Properties.TryGetValue("u" + Index, out CastProperty Value))
            {
                foreach (var Item in Value.Values)
                {
                    yield return (Vector2)Item;
                }
            }
        }

        public IEnumerable<int> VertexWeightBoneBuffer()
        {
            if (Properties.TryGetValue("wb", out CastProperty Value))
            {
                foreach (var Item in Value.Values)
                {
                    yield return (int)Item;
                }
            }
        }

        public IEnumerable<float> VertexWeightValueBuffer()
        {
            if (Properties.TryGetValue("wv", out CastProperty Value))
            {
                foreach (var Item in Value.Values)
                {
                    yield return (float)Item;
                }
            }
        }

        public Material Material()
        {
            if (Properties.TryGetValue("m", out CastProperty Value))
            {
                return (Material)ChildByHash((ulong)Value.Values[0]);
            }

            return null;
        }
    }

    public class Material : CastNode
    {
        public Material()
            : base(0x6C74616D)
        {
        }

        public string Name()
        {
            if (Properties.TryGetValue("n", out CastProperty Value))
            {
                return (string)Value.Values[0];
            }

            return null;
        }

        public string Type()
        {
            if (Properties.TryGetValue("t", out CastProperty Value))
            {
                return (string)Value.Values[0];
            }

            return null;
        }

        public Dictionary<string, CastNode> Slots()
        {
            var Result = new Dictionary<string, CastNode>();

            foreach (var Slot in Properties)
            {
                if (Slot.Value.Name == "n" || Slot.Value.Name == "t")
                {
                    continue;
                }

                if (!Result.ContainsKey(Slot.Value.Name))
                {
                    Result.Add(Slot.Value.Name, ChildByHash((ulong)Slot.Value.Values[0]));
                }
            }

            return Result;
        }
    }


    public class Model : CastNode
    {
        public Model()
            : base(0x6C646F6D)
        {
        }

        public Skeleton Skeleton()
        {
            var Result = ChildrenOfType<Skeleton>();

            if (Result.Count > 0)
            {
                return Result[0];
            }

            return null;
        }

        public List<Mesh> Meshes()
        {
            return ChildrenOfType<Mesh>();
        }

        public List<Material> Materials()
        {
            return ChildrenOfType<Material>();
        }
    }

    public class CastProperty
    {
        public string Name { get; set; }
        public string Type { get; set; }
        public List<object> Values { get; set; }

        public CastProperty(string Name, string Type)
        {
            this.Name = Name;
            this.Type = Type;

            Values = new List<object>();
        }

        public static CastProperty Load(BinaryReader Reader)
        {
            var Header = CastPropertyHeader.Load(Reader);
            var Name = Reader.ReadBytes(Header.NameLength);

            var Property = new CastProperty(Globals.BytesToString(Name), Globals.BytesToString(Header.Type));

            Property.Values.Capacity = (int)Header.ValueCount;

            for (var i = 0; i < Header.ValueCount; i++)
            {
                Property.Values.Add(Globals.CastPropertyLoad(Reader, Property.Type));
            }

            return Property;
        }

        public void Save(BinaryWriter Writer)
        {
            // TODO: Property save.
        }
    }

    public class CastNode
    {
        public uint Identifier { get; set; }
        public ulong Hash { get; set; }
        public Dictionary<string, CastProperty> Properties { get; set; }
        public List<CastNode> ChildNodes { get; set; }

        public CastNode ParentNode { get; set; }

        public CastNode(uint Identifier)
        {
            this.Identifier = Identifier;

            Hash = Globals.CastNextHash();
            Properties = new Dictionary<string, CastProperty>();
            ChildNodes = new List<CastNode>();
            ParentNode = null;
        }

        public List<T> ChildrenOfType<T>()
        {
            var Result = new List<T>();

            foreach (var Child in ChildNodes)
            {
                if (Child is T ChildT)
                {
                    Result.Add(ChildT);
                }
            }

            return Result;
        }

        public CastNode ChildByHash(ulong Hash)
        {
            foreach (var Child in ChildNodes)
            {
                if (Child.Hash == Hash)
                {
                    return Child;
                }
            }

            return null;
        }

        public static CastNode Load(BinaryReader Reader)
        {
            var Header = CastNodeHeader.Load(Reader);
            var Node = Globals.CastNodeSwitcher(Header.Identifier);

            Node.Hash = Header.NodeHash;

            for (var i = 0; i < Header.PropertyCount; i++)
            {
                var Property = CastProperty.Load(Reader);

                if (Node.Properties.ContainsKey(Property.Name))
                {
                    continue;
                }

                Node.Properties.Add(Property.Name, Property);
            }

            Node.ChildNodes.Capacity = (int)Header.ChildCount;

            for (var i = 0; i < Header.ChildCount; i++)
            {
                var ChildNode = Load(Reader);

                ChildNode.ParentNode = Node;

                Node.ChildNodes.Add(ChildNode);
            }

            return Node;
        }

        public void Save(BinaryWriter Writer)
        {
            // TODO: Node save.
        }
    }

    public class CastFile
    {
        public List<CastNode> RootNodes { get; set; }

        public CastFile()
        {
            RootNodes = new List<CastNode>();
        }

        public static CastFile Load(Stream IOStream)
        {
            var Reader = new BinaryReader(IOStream);
            var Header = CastHeader.Load(Reader);

            if (Header.Magic != 0x74736163)
            {
                throw new Exception("Invalid cast file magic");
            }

            var Result = new CastFile();

            Result.RootNodes.Capacity = (int)Header.RootNodeCount;

            for (var i = 0; i < Header.RootNodeCount; i++)
            {
                Result.RootNodes.Add(CastNode.Load(Reader));
            }

            return Result;
        }

        public static CastFile Load(string Path)
        {
            return Load(File.OpenRead(Path));
        }

        public void Save(Stream IOStream)
        {
            var Writer = new BinaryWriter(IOStream);
            var Header = new CastHeader
            {
                RootNodeCount = (uint)RootNodes.Count
            };

            Header.Save(Writer);

            foreach (var RootNode in RootNodes)
            {
                RootNode.Save(Writer);
            }
        }

        public void Save(string Path)
        {
            Save(File.Create(Path));
        }
    }
}
