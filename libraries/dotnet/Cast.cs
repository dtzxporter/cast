using System;
using System.IO;
using System.Text;
using System.Collections.Generic;
using System.Runtime.CompilerServices;

namespace Cast
{
    class Globals
    {
        private static ulong NEXT_HASH = 0x534E495752545250;

        [MethodImpl(MethodImplOptions.AggressiveInlining)]
        public static ulong CastNextHash()
        {
            return NEXT_HASH++;
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
                case 0x64686B69:
                    return new IKHandle();
                case 0x74736E63:
                    return new Constraint();
                case 0x6873656D:
                    return new Mesh();
                case 0x6C74616D:
                    return new Material();
                case 0x656C6966:
                    return new File();
                case 0x6D696E61:
                    return new Animation();
                case 0x76727563:
                    return new Curve();
                case 0x564F4D43:
                    return new CurveModeOverride();
                case 0x6669746E:
                    return new NotificationTrack();
                case 0x68736C62:
                    return new BlendShape();
                case 0x746F6F72:
                    return new Root();
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

        [MethodImpl(MethodImplOptions.AggressiveInlining)]
        public static uint CastPropertyByteLength(string Type)
        {
            switch (Type)
            {
                case "b":
                    return 1u;
                case "h":
                    return 2u;
                case "i":
                case "f":
                    return 4u;
                case "l":
                case "d":
                case "2v":
                    return 8u;
                case "3v":
                    return 12u;
                case "4v":
                    return 16u;
                default:
                    throw new Exception("Unsupported cast property type");
            }
        }

        [MethodImpl(MethodImplOptions.AggressiveInlining)]
        public static void CastPropertyWrite(BinaryWriter Writer, string Type, object Value)
        {
            switch (Type)
            {
                case "b":
                    Writer.Write((byte)Value);
                    break;
                case "h":
                    Writer.Write((ushort)Value);
                    break;
                case "i":
                    Writer.Write((uint)Value);
                    break;
                case "l":
                    Writer.Write((ulong)Value);
                    break;
                case "f":
                    Writer.Write((float)Value);
                    break;
                case "d":
                    Writer.Write((double)Value);
                    break;
                case "2v":
                    Writer.Write(((Vector2)Value).X);
                    Writer.Write(((Vector2)Value).Y);
                    break;
                case "3v":
                    Writer.Write(((Vector3)Value).X);
                    Writer.Write(((Vector3)Value).Y);
                    Writer.Write(((Vector3)Value).Z);
                    break;
                case "4v":
                    Writer.Write(((Vector4)Value).X);
                    Writer.Write(((Vector4)Value).Y);
                    Writer.Write(((Vector4)Value).Z);
                    Writer.Write(((Vector4)Value).W);
                    break;
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

        public static void WriteNullTerminatedString(BinaryWriter Writer, string Value)
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

    /// <summary>
    /// A blend shape deformer that defines a base mesh shape, and corrosponding target mesh shapes.
    /// </summary>
    public class BlendShape : CastNode
    {
        public BlendShape()
            : base(0x68736C62)
        {
        }

        /// <summary>
        /// The name of this blend shape deformer.
        /// </summary>
        /// <returns></returns>
        public string Name()
        {
            if (Properties.TryGetValue("n", out CastProperty Value))
            {
                return (string)Value.Values[0];
            }

            return null;
        }

        /// <summary>
        /// The base mesh shape.
        /// </summary>
        /// <returns></returns>
        public Mesh BaseShape()
        {
            if (Properties.TryGetValue("b", out CastProperty Value))
            {
                return (Mesh)ChildByHash((ulong)Value.Values[0]);
            }

            return null;
        }

        /// <summary>
        /// A collection of target mesh shapes.
        /// </summary>
        /// <returns></returns>
        public IEnumerable<Mesh> TargetShapes()
        {
            if (Properties.TryGetValue("t", out CastProperty Value))
            {
                foreach (var Item in Value.Values)
                {
                    yield return (Mesh)ChildByHash((ulong)Item);
                }
            }
        }

        /// <summary>
        /// A collection of target mesh scale values.
        /// </summary>
        /// <returns></returns>
        public IEnumerable<float> TargetWeightScales()
        {
            if (Properties.TryGetValue("ts", out CastProperty Value))
            {
                foreach (var Item in Value.Values)
                {
                    yield return (float)Item;
                }
            }
        }
    }

    /// <summary>
    /// A 3d bone that belongs to a <see cref="Skeleton"/>.
    /// </summary>
    public class Bone : CastNode
    {
        public Bone()
            : base(0x656E6F62)
        {
        }

        /// <summary>
        /// The name of this bone.
        /// </summary>
        /// <returns></returns>
        public string Name()
        {
            if (Properties.TryGetValue("n", out CastProperty Value))
            {
                return (string)Value.Values[0];
            }

            return null;
        }

        /// <summary>
        /// The index of the parent bone in the skeleton. -1 is a root bone.
        /// </summary>
        /// <returns></returns>
        public int ParentIndex()
        {
            if (Properties.TryGetValue("p", out CastProperty Value))
            {
                return unchecked((int)(uint)Value.Values[0]);
            }

            return -1;
        }

        /// <summary>
        /// Whether or not children bones are effected by the scale of this bone.
        /// </summary>
        /// <returns></returns>
        public bool SegmentScaleCompensate()
        {
            if (Properties.TryGetValue("ssc", out CastProperty Value))
            {
                return (uint)Value.Values[0] >= 1;
            }

            return true;
        }

        /// <summary>
        /// The local space position of this bone.
        /// </summary>
        /// <returns></returns>
        public Vector3 LocalPosition()
        {
            if (Properties.TryGetValue("lp", out CastProperty Value))
            {
                return (Vector3)Value.Values[0];
            }

            return null;
        }

        /// <summary>
        /// The local space rotation of this bone.
        /// </summary>
        /// <returns></returns>
        public Vector4 LocalRotation()
        {
            if (Properties.TryGetValue("lr", out CastProperty Value))
            {
                return (Vector4)Value.Values[0];
            }

            return null;
        }

        /// <summary>
        /// The world position of this bone.
        /// </summary>
        /// <returns></returns>
        public Vector3 WorldPosition()
        {
            if (Properties.TryGetValue("wp", out CastProperty Value))
            {
                return (Vector3)Value.Values[0];
            }

            return null;
        }

        /// <summary>
        /// The world rotation of this bone.
        /// </summary>
        /// <returns></returns>
        public Vector4 WorldRotation()
        {
            if (Properties.TryGetValue("wr", out CastProperty Value))
            {
                return (Vector4)Value.Values[0];
            }

            return null;
        }

        /// <summary>
        /// The scale of this bone.
        /// </summary>
        /// <returns></returns>
        public Vector3 Scale()
        {
            if (Properties.TryGetValue("s", out CastProperty Value))
            {
                return (Vector3)Value.Values[0];
            }

            return null;
        }
    }

    /// <summary>
    /// Defines an ik chain and its constraints in the skeleton.
    /// </summary>
    public class IKHandle : CastNode
    {
        public IKHandle()
            : base(0x64686B69)
        {
        }

        /// <summary>
        /// The name of this ik handle.
        /// </summary>
        /// <returns></returns>
        public string Name()
        {
            if (Properties.TryGetValue("n", out CastProperty Value))
            {
                return (string)Value.Values[0];
            }

            return null;
        }

        /// <summary>
        /// The bone which starts the chain.
        /// </summary>
        /// <returns></returns>
        public Bone StartBone()
        {
            if (Properties.TryGetValue("sb", out CastProperty Value))
            {
                return (Bone)ParentNode.ChildByHash((ulong)Value.Values[0]);
            }

            return null;
        }

        /// <summary>
        /// The bone which ends the chain.
        /// </summary>
        /// <returns></returns>
        public Bone EndBone()
        {
            if (Properties.TryGetValue("eb", out CastProperty Value))
            {
                return (Bone)ParentNode.ChildByHash((ulong)Value.Values[0]);
            }

            return null;
        }

        /// <summary>
        /// The bone that acts as a target for the chain.
        /// </summary>
        /// <returns></returns>
        public Bone TargetBone()
        {
            if (Properties.TryGetValue("tb", out CastProperty Value))
            {
                return (Bone)ParentNode.ChildByHash((ulong)Value.Values[0]);
            }

            return null;
        }

        /// <summary>
        /// The bone that acts as a pole vector for this chain.
        /// </summary>
        /// <returns></returns>
        public Bone PoleVectorBone()
        {
            if (Properties.TryGetValue("pv", out CastProperty Value))
            {
                return (Bone)ParentNode.ChildByHash((ulong)Value.Values[0]);
            }

            return null;
        }

        /// <summary>
        /// The bone that acts as the pole (twist) for this chain.
        /// </summary>
        /// <returns></returns>
        public Bone PoleBone()
        {
            if (Properties.TryGetValue("pb", out CastProperty Value))
            {
                return (Bone)ParentNode.ChildByHash((ulong)Value.Values[0]);
            }

            return null;
        }

        /// <summary>
        /// Whether or not the target rotation effects the chain.
        /// </summary>
        /// <returns></returns>
        public bool UseTargetRotation()
        {
            if (Properties.TryGetValue("tr", out CastProperty Value))
            {
                return (uint)Value.Values[0] >= 1;
            }

            return false;
        }
    }

    /// <summary>
    /// Defines a bone constraint in a skeleton.
    /// </summary>
    public class Constraint : CastNode
    {
        public Constraint()
            : base(0x74736E63)
        {
        }

        /// <summary>
        /// The name of this constraint.
        /// </summary>
        /// <returns></returns>
        public string Name()
        {
            if (Properties.TryGetValue("n", out CastProperty Value))
            {
                return (string)Value.Values[0];
            }

            return null;
        }

        /// <summary>
        /// The type of constraint to configure.
        /// </summary>
        /// <returns></returns>
        public string ConstraintType()
        {
            if (Properties.TryGetValue("ct", out CastProperty Value))
            {
                return (string)Value.Values[0];
            }

            return null;
        }

        /// <summary>
        /// The bone that is being constrained.
        /// </summary>
        /// <returns></returns>
        public Bone ConstraintBone()
        {
            if (Properties.TryGetValue("cb", out CastProperty Value))
            {
                return (Bone)ParentNode.ChildByHash((ulong)Value.Values[0]);
            }

            return null;
        }

        /// <summary>
        /// The bone that is the target for the constraint.
        /// </summary>
        /// <returns></returns>
        public Bone TargetBone()
        {
            if (Properties.TryGetValue("tb", out CastProperty Value))
            {
                return (Bone)ParentNode.ChildByHash((ulong)Value.Values[0]);
            }

            return null;
        }

        /// <summary>
        /// Whether or not the original offset is maintained.
        /// </summary>
        /// <returns></returns>
        public bool MaintainOffset()
        {
            if (Properties.TryGetValue("mo", out CastProperty Value))
            {
                return (uint)Value.Values[0] >= 1;
            }

            return false;
        }

        /// <summary>
        /// Whether or not to skip the x axis when constraining.
        /// </summary>
        /// <returns></returns>
        public bool SkipX()
        {
            if (Properties.TryGetValue("sx", out CastProperty Value))
            {
                return (uint)Value.Values[0] >= 1;
            }

            return false;
        }

        /// <summary>
        /// Whether or not to skip the y axis when constraining.
        /// </summary>
        /// <returns></returns>
        public bool SkipY()
        {
            if (Properties.TryGetValue("sy", out CastProperty Value))
            {
                return (uint)Value.Values[0] >= 1;
            }

            return false;
        }

        /// <summary>
        /// Whether or not to skip the z axis when constraining.
        /// </summary>
        /// <returns></returns>
        public bool SkipZ()
        {
            if (Properties.TryGetValue("sz", out CastProperty Value))
            {
                return (uint)Value.Values[0] >= 1;
            }

            return false;
        }
    }

    /// <summary>
    /// A collection of bones for a model or animation.
    /// </summary>
    public class Skeleton : CastNode
    {
        public Skeleton()
            : base(0x6C656B73)
        {
        }

        /// <summary>
        /// The collection of bones in this skeleton.
        /// </summary>
        /// <returns></returns>
        public List<Bone> Bones()
        {
            return ChildrenOfType<Bone>();
        }

        /// <summary>
        /// The collection of ik handles in this skeleton.
        /// </summary>
        /// <returns></returns>
        public List<IKHandle> IKHandles()
        {
            return ChildrenOfType<IKHandle>();
        }

        /// <summary>
        /// The collection of constraints in this skeleton.
        /// </summary>
        /// <returns></returns>
        public List<Constraint> Constraints()
        {
            return ChildrenOfType<Constraint>();
        }
    }

    /// <summary>
    /// A 3d mesh for a model.
    /// </summary>
    public class Mesh : CastNode
    {
        public Mesh()
            : base(0x6873656D)
        {
        }

        /// <summary>
        /// The name of this mesh.
        /// </summary>
        /// <returns></returns>
        public string Name()
        {
            if (Properties.TryGetValue("n", out CastProperty Value))
            {
                return (string)Value.Values[0];
            }

            return null;
        }

        /// <summary>
        /// The number of vertices in this mesh.
        /// </summary>
        /// <returns></returns>
        public int VertexCount()
        {
            if (Properties.TryGetValue("vp", out CastProperty Value))
            {
                return Value.Values.Count;
            }

            return 0;
        }

        /// <summary>
        /// The number of faces in this mesh.
        /// </summary>
        /// <returns></returns>
        public int FaceCount()
        {
            if (Properties.TryGetValue("f", out CastProperty Value))
            {
                return Value.Values.Count / 3;
            }

            return 0;
        }

        /// <summary>
        /// The number of uv layers in this mesh.
        /// </summary>
        /// <returns></returns>
        public int UVLayerCount()
        {
            if (Properties.TryGetValue("ul", out CastProperty Value))
            {
                return (int)Value.Values[0];
            }

            return 0;
        }

        /// <summary>
        /// The maximum weight influence for this mesh.
        /// </summary>
        /// <returns></returns>
        public int MaximumWeightInfluence()
        {
            if (Properties.TryGetValue("mi", out CastProperty Value))
            {
                return (int)Value.Values[0];
            }

            return 0;
        }

        /// <summary>
        /// The collection of faces for this mesh.
        /// </summary>
        /// <returns></returns>
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

        /// <summary>
        /// The collection of vertex positions for this mesh.
        /// </summary>
        /// <returns></returns>
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

        /// <summary>
        /// The collection of vertex normals for this mesh.
        /// </summary>
        /// <returns></returns>
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

        /// <summary>
        /// The collection of vertex tangents for this mesh.
        /// </summary>
        /// <returns></returns>
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

        /// <summary>
        /// The collection of vertex colors for this mesh.
        /// </summary>
        /// <returns></returns>
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

        /// <summary>
        /// The uv layer collection for the given layer index.
        /// </summary>
        /// <param name="Index">The uv layer index, starting from 0</param>
        /// <returns></returns>
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

        /// <summary>
        /// The collection of weight bone indices for this mesh.
        /// </summary>
        /// <returns></returns>
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

        /// <summary>
        /// The collection of weight bone values for this mesh.
        /// </summary>
        /// <returns></returns>
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

        /// <summary>
        /// The method used for skinning this mesh.
        /// </summary>
        /// <returns></returns>
        public string SkinningMethod()
        {
            if (Properties.TryGetValue("sm", out CastProperty Value))
            {
                return (string)Value.Values[0];
            }

            return "linear";
        }

        /// <summary>
        /// The material for this mesh.
        /// </summary>
        /// <returns></returns>
        public Material Material()
        {
            if (Properties.TryGetValue("m", out CastProperty Value))
            {
                return (Material)ChildByHash((ulong)Value.Values[0]);
            }

            return null;
        }
    }

    /// <summary>
    /// Material contains a collection of slot:file mappings.
    /// </summary>
    public class Material : CastNode
    {
        public Material()
            : base(0x6C74616D)
        {
        }

        /// <summary>
        /// The name for this material.
        /// </summary>
        /// <returns></returns>
        public string Name()
        {
            if (Properties.TryGetValue("n", out CastProperty Value))
            {
                return (string)Value.Values[0];
            }

            return null;
        }

        /// <summary>
        /// The type of this material (pbr).
        /// </summary>
        /// <returns></returns>
        public string Type()
        {
            if (Properties.TryGetValue("t", out CastProperty Value))
            {
                return (string)Value.Values[0];
            }

            return null;
        }

        /// <summary>
        /// A collection of slots for this material.
        /// </summary>
        /// <returns></returns>
        public Dictionary<string, File> Slots()
        {
            var Result = new Dictionary<string, File>();

            foreach (var Slot in Properties)
            {
                if (Slot.Value.Name == "n" || Slot.Value.Name == "t")
                {
                    continue;
                }

                if (!Result.ContainsKey(Slot.Value.Name))
                {
                    Result.Add(Slot.Value.Name, (File)ChildByHash((ulong)Slot.Value.Values[0]));
                }
            }

            return Result;
        }
    }

    /// <summary>
    /// A 3d animation and it's collection of curves.
    /// </summary>
    public class Animation : CastNode
    {
        public Animation()
            : base(0x6D696E61)
        {
        }

        /// <summary>
        /// The name of the animation.
        /// </summary>
        /// <returns></returns>
        public string Name()
        {
            if (Properties.TryGetValue("n", out CastProperty Value))
            {
                return (string)Value.Values[0];
            }

            return null;
        }

        /// <summary>
        /// The skeleton embedded in this animation.
        /// </summary>
        /// <returns></returns>
        public Skeleton Skeleton()
        {
            var Result = ChildrenOfType<Skeleton>();

            if (Result.Count > 0)
            {
                return Result[0];
            }

            return null;
        }

        /// <summary>
        /// The collection of curves for this animation.
        /// </summary>
        /// <returns></returns>
        public List<Curve> Curves()
        {
            return ChildrenOfType<Curve>();
        }

        /// <summary>
        /// The collection of curve mode overrides for this animation.
        /// </summary>
        /// <returns></returns>
        public List<CurveModeOverride> CurveModeOverrides()
        {
            return ChildrenOfType<CurveModeOverride>();
        }

        /// <summary>
        /// The collection of notification tracks for this animation.
        /// </summary>
        /// <returns></returns>
        public List<NotificationTrack> Notifications()
        {
            return ChildrenOfType<NotificationTrack>();
        }

        /// <summary>
        /// The framerate this animation plays at.
        /// </summary>
        /// <returns></returns>
        public float Framerate()
        {
            if (Properties.TryGetValue("fr", out CastProperty Value))
            {
                return (float)Value.Values[0];
            }

            return 30.0f;
        }

        /// <summary>
        /// Whether or not this animation should loop.
        /// </summary>
        /// <returns></returns>
        public bool Looping()
        {
            if (Properties.TryGetValue("lo", out CastProperty Value))
            {
                return (uint)Value.Values[0] >= 1;
            }

            return false;
        }
    }

    /// <summary>
    /// A curve from an animation that animates a node's property.
    /// </summary>
    public class Curve : CastNode
    {
        public Curve()
            : base(0x76727563)
        {
        }

        /// <summary>
        /// The name of the node to animate.
        /// </summary>
        /// <returns></returns>
        public string NodeName()
        {
            if (Properties.TryGetValue("nn", out CastProperty Value))
            {
                return (string)Value.Values[0];
            }

            return null;
        }

        /// <summary>
        /// The property of the node to animate.
        /// </summary>
        /// <returns></returns>
        public string KeyPropertyName()
        {
            if (Properties.TryGetValue("kp", out CastProperty Value))
            {
                return (string)Value.Values[0];
            }

            return null;
        }

        /// <summary>
        /// The collection of keyframes.
        /// </summary>
        /// <returns></returns>
        public IEnumerable<int> KeyFrameBuffer()
        {
            if (Properties.TryGetValue("kb", out CastProperty Value))
            {
                foreach (var Item in Value.Values)
                {
                    yield return (int)Item;
                }
            }
        }

        /// <summary>
        /// The collection of keyframe values.
        /// </summary>
        /// <typeparam name="T"></typeparam>
        /// <returns></returns>
        public IEnumerable<T> KeyValueBuffer<T>()
        {
            if (Properties.TryGetValue("kv", out CastProperty Value))
            {
                foreach (var Item in Value.Values)
                {
                    yield return (T)Item;
                }
            }
        }

        /// <summary>
        /// The mode for this animation.
        /// </summary>
        /// <returns></returns>
        public string Mode()
        {
            if (Properties.TryGetValue("m", out CastProperty Value))
            {
                return (string)Value.Values[0];
            }

            return null;
        }

        /// <summary>
        /// The weight to use when blending this animation.
        /// </summary>
        /// <returns></returns>
        public float AdditiveBlendWeight()
        {
            if (Properties.TryGetValue("ab", out CastProperty Value))
            {
                return (float)Value.Values[0];
            }

            return 1.0f;
        }
    }

    /// <summary>
    /// An override for an animation curves mode.
    /// </summary>
    public class CurveModeOverride : CastNode
    {
        public CurveModeOverride()
            : base(0x564F4D43)
        {
        }

        /// <summary>
        /// Sets the name of the node that is the start of this override.
        /// </summary>
        /// <returns></returns>
        public string NodeName()
        {
            if (Properties.TryGetValue("nn", out CastProperty Value))
            {
                return (string)Value.Values[0];
            }

            return null;
        }

        /// <summary>
        /// The mode for this override.
        /// </summary>
        /// <returns></returns>
        public string Mode()
        {
            if (Properties.TryGetValue("m", out CastProperty Value))
            {
                return (string)Value.Values[0];
            }

            return null;
        }
    }

    /// <summary>
    /// The notification track for an animation.
    /// </summary>
    public class NotificationTrack : CastNode
    {
        public NotificationTrack()
            : base(0x6669746E)
        {
        }

        /// <summary>
        /// The name of the notification.
        /// </summary>
        /// <returns></returns>
        public string Name()
        {
            if (Properties.TryGetValue("n", out CastProperty Value))
            {
                return (string)Value.Values[0];
            }

            return null;
        }

        /// <summary>
        /// A collection of keyframes this notification fires on.
        /// </summary>
        /// <returns></returns>
        public IEnumerable<int> KeyFrameBuffer()
        {
            if (Properties.TryGetValue("kb", out CastProperty Value))
            {
                foreach (var Item in Value.Values)
                {
                    yield return (int)Item;
                }
            }
        }
    }

    /// <summary>
    /// An external file reference.
    /// </summary>
    public class File : CastNode
    {
        public File()
            : base(0x656C6966)
        {
        }

        /// <summary>
        /// The path of this file reference.
        /// </summary>
        /// <returns></returns>
        public string Path()
        {
            if (Properties.TryGetValue("p", out CastProperty Value))
            {
                return (string)Value.Values[0];
            }

            return null;
        }
    }

    /// <summary>
    /// A root node.
    /// </summary>
    public class Root : CastNode
    {
        public Root()
            : base(0x746F6F72)
        {
        }
    }

    /// <summary>
    /// A 3d model with meshes, materials, and a skeleton.
    /// </summary>
    public class Model : CastNode
    {
        public Model()
            : base(0x6C646F6D)
        {
        }

        /// <summary>
        /// The name of the model.
        /// </summary>
        /// <returns></returns>
        public string Name()
        {
            if (Properties.TryGetValue("n", out CastProperty Value))
            {
                return (string)Value.Values[0];
            }

            return null;
        }

        /// <summary>
        /// The skeleton embedded in this model.
        /// </summary>
        /// <returns></returns>
        public Skeleton Skeleton()
        {
            var Result = ChildrenOfType<Skeleton>();

            if (Result.Count > 0)
            {
                return Result[0];
            }

            return null;
        }

        /// <summary>
        /// A collection of meshes for this model.
        /// </summary>
        /// <returns></returns>
        public List<Mesh> Meshes()
        {
            return ChildrenOfType<Mesh>();
        }

        /// <summary>
        /// A collection of materials for this model.
        /// </summary>
        /// <returns></returns>
        public List<Material> Materials()
        {
            return ChildrenOfType<Material>();
        }

        /// <summary>
        /// A collection of blend shapes for this model.
        /// </summary>
        /// <returns></returns>
        public List<BlendShape> BlendShapes()
        {
            return ChildrenOfType<BlendShape>();
        }
    }

    /// <summary>
    /// A single property for a cast node.
    /// </summary>
    public class CastProperty
    {
        /// <summary>
        /// The name for this property.
        /// </summary>
        public string Name { get; set; }
        /// <summary>
        /// The value type for this property.
        /// </summary>
        public string Type { get; set; }
        /// <summary>
        /// A collection of values for this property.
        /// </summary>
        public List<object> Values { get; set; }

        public CastProperty(string Name, string Type)
        {
            this.Name = Name;
            this.Type = Type;

            Values = new List<object>();
        }

        /// <summary>
        /// Loads a cast property from the given reader.
        /// </summary>
        /// <param name="Reader"></param>
        /// <returns></returns>
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

        /// <summary>
        /// Saves this cast property to the given writer.
        /// </summary>
        /// <param name="Writer"></param>
        public void Save(BinaryWriter Writer)
        {
            var PropertyName = Encoding.UTF8.GetBytes(Name);
            var PropertyType = Encoding.UTF8.GetBytes(Type);

            if (PropertyType.Length == 1)
            {
                PropertyType = new byte[2] { PropertyType[0], 0x0 };
            }

            var PropertyHeader = new CastPropertyHeader()
            {
                Type = PropertyType,
                NameLength = (ushort)PropertyName.Length,
                ValueCount = (uint)Values.Count,
            };

            PropertyHeader.Save(Writer);

            Writer.Write(PropertyName);

            if (Type == "s")
            {
                Globals.WriteNullTerminatedString(Writer, (string)Values[0]);
            }
            else
            {
                foreach (var Value in Values)
                {
                    Globals.CastPropertyWrite(Writer, Type, Value);
                }
            }
        }

        /// <summary>
        /// Returns the length in bytes of this cast property.
        /// </summary>
        /// <returns></returns>
        public uint Length()
        {
            var Result = 0x8u;

            Result += (uint)Encoding.UTF8.GetByteCount(Name);

            if (Type == "s")
            {
                Result += (uint)Encoding.UTF8.GetByteCount((string)Values[0]) + 1;
            }
            else
            {
                Result += Globals.CastPropertyByteLength(Type) * (uint)Values.Count;
            }

            return Result;
        }
    }

    /// <summary>
    /// A single generic cast node.
    /// </summary>
    public class CastNode
    {
        /// <summary>
        /// The unique identifier for this node.
        /// </summary>
        public uint Identifier { get; set; }
        /// <summary>
        /// The unique hash for this node.
        /// </summary>
        public ulong Hash { get; set; }
        /// <summary>
        /// A collection of properties.
        /// </summary>
        public Dictionary<string, CastProperty> Properties { get; set; }
        /// <summary>
        /// A collection of child nodes.
        /// </summary>
        public List<CastNode> ChildNodes { get; set; }

        /// <summary>
        /// The parent node if this node is not a root node.
        /// </summary>
        public CastNode ParentNode { get; set; }

        public CastNode(uint Identifier)
        {
            this.Identifier = Identifier;

            Hash = Globals.CastNextHash();
            Properties = new Dictionary<string, CastProperty>();
            ChildNodes = new List<CastNode>();
            ParentNode = null;
        }

        /// <summary>
        /// Finds all children that match the given type.
        /// </summary>
        /// <typeparam name="T">The type to match.</typeparam>
        /// <returns></returns>
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

        /// <summary>
        /// Finds a child by the given hash.
        /// </summary>
        /// <param name="Hash"></param>
        /// <returns></returns>
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

        /// <summary>
        /// Loads a cast node from the given reader.
        /// </summary>
        /// <param name="Reader"></param>
        /// <returns></returns>
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

        /// <summary>
        /// Saves this cast node to the given writer.
        /// </summary>
        /// <param name="Writer"></param>
        public void Save(BinaryWriter Writer)
        {
            var Header = new CastNodeHeader()
            {
                Identifier = Identifier,
                NodeSize = Length(),
                NodeHash = Hash,
                PropertyCount = (uint)Properties.Count,
                ChildCount = (uint)ChildNodes.Count,
            };

            Header.Save(Writer);

            foreach (var Property in Properties)
            {
                Property.Value.Save(Writer);
            }

            foreach (var ChildNode in ChildNodes)
            {
                ChildNode.Save(Writer);
            }
        }

        /// <summary>
        /// Returns the length in bytes of this cast node.
        /// </summary>
        /// <returns></returns>
        public uint Length()
        {
            var Result = 0x18u;

            foreach (var Property in Properties)
            {
                Result += Property.Value.Length();
            }

            foreach (var ChildNode in ChildNodes)
            {
                Result += ChildNode.Length();
            }

            return Result;
        }
    }

    /// <summary>
    /// The container file that holds cast nodes.
    /// </summary>
    public class CastFile
    {
        /// <summary>
        /// A collection of root nodes in this file.
        /// </summary>
        public List<CastNode> RootNodes { get; set; }

        public CastFile()
        {
            RootNodes = new List<CastNode>();
        }

        /// <summary>
        /// Loads a cast file from the given stream.
        /// </summary>
        /// <param name="IOStream"></param>
        /// <returns></returns>
        /// <exception cref="Exception"></exception>
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

        /// <summary>
        /// Loads a cast file from the given path.
        /// </summary>
        /// <param name="Path"></param>
        /// <returns></returns>
        public static CastFile Load(string Path)
        {
            using (var File = System.IO.File.OpenRead(Path))
            {
                return Load(File);
            }
        }

        /// <summary>
        /// Saves a cast file to the given stream.
        /// </summary>
        /// <param name="IOStream"></param>
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

        /// <summary>
        /// Saves a cast file to the given path.
        /// </summary>
        /// <param name="Path"></param>
        public void Save(string Path)
        {
            using (var File = System.IO.File.Create(Path))
            {
                Save(File);
            }
        }
    }
}
