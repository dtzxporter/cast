# Cast | A new open-source container for models, animations, and materials

The goal of cast is to create an engine agnostic format that can be parsed and written with ease. In addition, cast should have very similar output on any engine.

<TODO: Cast logo>

## File stucture:
All files start with a cast header:
```c++
struct CastHeader
{
	uint32_t Magic;			// char[4] cast	(0x74736163)
	uint32_t Version;		// 0x1
	uint32_t RootNodes;		// Number of root nodes, which contain various sub nodes if necessary
	uint32_t Flags;			// Reserved for flags, or padding, whichever is needed
};
```
A cast file is basically a group of generic nodes. Nodes are given a unique registered id, which can tell the loader what the data is, and how to handle it.

Following the cast header is a collection of nodes which must be of type CastId::Root.

A node looks like:
```c++
struct CastNodeHeader
{
	CastId Identifier;		// Used to signify which class this node uses
	uint32_t NodeSize;		// Size of all data and sub data following the node
	uint64_t NodeHash;		// Unique hash, like an id, used to link nodes together
	uint32_t PropertyCount;	// The count of properties
	uint32_t ChildCount;	// The count of direct children nodes

	// We must read until the node size hits, and that means we are done.
	// The nodes are in a stack layout, so it's easy to load, FILO order.
};
```
There are several registered cast ids available:
```c++
enum class CastId : uint32_t
{
	Root = 0x746F6F72,
	Model = 0x6C646F6D,
	Mesh = 0x6873656D,
	Skeleton = 0x6C656B73,
	Bone = 0x656E6F62,
	Animation = 0x6D696E61,
	Material = 0x6C74616D,
};
```

Following a node, is the list of properties [Node.PropertyCount], a property looks like:
```c++
struct CastPropertyHeader
{
	CastPropertyId Identifier;	// The element type of this property
	uint16_t NameSize;			// The size of the name of this property
	uint32_t ArrayLength;		// The number of elements this property contains (1 for single)

	// Following is UTF-8 string lowercase, size of namesize, NOT null terminated
	// cast_property[ArrayLength] array of data
};

```
For properties, cast has several built in types:
```c++
enum class CastPropertyId : uint16_t
{
	Byte = 'b',			// <uint8_t>
	Short = 'h',		// <uint16_t>
	Integer32 = 'i',	// <uint32_t>
	Integer64 = 'l',	// <uint64_t>

	Float = 'f',		// <float>
	Double = 'd',		// <double>

	String = 's',		// Null terminated UTF-8 string

	Vector2 = 'v2',		// Float precision vector XY
	Vector3 = 'v3',		// Float precision vector XYZ
	Vector4 = 'v4'		// Float precision vector XYZW
};
```

## Parsing
To read a cast file, you just need to traverse the root nodes and their children. Properties always come before a nodes children. Each node has the total size of itself, and all children, so if a processor doesn't understand a node id, it can skip the entire node and continue reading.

Cast ids are integers for performance, unlike FBX where nodes are full strings.

## Cast processors : TODO Define all processors and data required.