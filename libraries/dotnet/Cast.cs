using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.CompilerServices;
using System.Text;

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
                case 0x6873656D:
                    return new Mesh();
                case 0x6C74616D:
                    return new Material();
                case 0x656E6F62:
                    return new Bone();
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
                    return Reader.ReadInt16();
                case "i":
                    return Reader.ReadInt32();
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
            return Encoding.UTF8.GetBytes(Value.Replace("\0", ""));
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

    public class Vector2
    {
        public float X { get; set; }
        public float Y { get; set; }
    }

    public class Vector3
    {
        public float X { get; set; }
        public float Y { get; set; }
        public float Z { get; set; }
    }

    public class Vector4
    {
        public float X { get; set; }
        public float Y { get; set; }
        public float Z { get; set; }
        public float W { get; set; }
    }

    public class Skeleton : CastNode
    {
        public Skeleton()
            : base(0x6C656B73)
        {
        }

        public List<Bone> Bones()
        {
            var Result = ChildrenOfType<Bone>();
            if (Result.Count > 0)
            {
                return Result;
            }
            return null;
        }
    }

    public class Bone : CastNode
    {
        public Bone()
            : base(0x656E6F62)
        {
        }
    }

    public class Mesh : CastNode
    {
        public Mesh()
            : base(0x6873656D)
        {
        }
    }

    public class Material : CastNode
    {
        public Material()
            : base(0x6C74616D)
        {
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
            
            //Check if the Header has a hash, and set the node hash to it if it does
            if (Header.NodeHash != 0)
                Node.Hash = Header.NodeHash;

            for (var i = 0; i < Header.ChildCount; i++)
            {
                Node.ChildNodes.Add(Load(Reader));
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

        public static CastFile Load(string Path)
        {
            var Reader = new BinaryReader(File.OpenRead(Path));
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

        //Load cast model from stream
        public static CastFile Load(Stream s)
        {
            var Reader = new BinaryReader(s);
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

        public void Save(string Path)
        {
            var Writer = new BinaryWriter(File.Create(Path));
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
    }
}