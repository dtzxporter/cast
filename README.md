# Cast | A new open-source container for models, animations, and materials

The goal of cast is to create an engine agnostic format that can be parsed and written with ease. In addition, cast should have very similar output on any engine.

<p align="center">
	<img src="images/cast-icon-md.png" alt="SEAnim"/>
</p>

## 3D Engine Plugins:
- Autodesk Maya (Beta): [Releases](https://github.com/dtzxporter/cast/releases)
- Blender (2.8+) (Beta): [Releases](https://github.com/dtzxporter/cast/releases)
- 3DS Max: (COMING SOON)

# Programming libraries:
- .NET Framework: (COMING SOON)
- Python: [Libraries/Python](https://github.com/dtzxporter/cast/tree/master/libraries/python)
- C++: (COMMING SOON)

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
	Curve = 0x76727563,
	NotificationTrack = 0x6669746E,
	Material = 0x6C74616D,
	File = 0x656C6966,
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

## Cast processors:

### Model:
<table>
	<tr>
		<th>Field</th>
		<th>Type(s)</th>
		<th>IsArray</th>
		<th>Required</th>
 	</tr>
 	<tr>
  		<td>Children</td>
   		<td>Skeleton, Mesh, Material</td>
		<td>True</td>
		<td>False</td>
 	</tr>
	 <tr>
  		<td>Parent</td>
   		<td>Root</td>
		<td>False</td>
		<td>True</td>
 	</tr>
</table>

### Mesh:
<table>
	<tr>
		<th>Field</th>
		<th>Type(s)</th>
		<th>IsArray</th>
		<th>Required</th>
 	</tr>
 	<tr>
  		<td>Children</td>
   		<td>None</td>
		<td>True</td>
		<td>False</td>
 	</tr>
	 <tr>
  		<td>Parent</td>
   		<td>Model</td>
		<td>False</td>
		<td>True</td>
 	</tr>
</table>
<table>
<tr>
		<th>Property (id)</th>
		<th>Type(s)</th>
		<th>IsArray</th>
		<th>Required</th>
 	</tr>
	 <tr>
  		<td>Vertex Position Buffer (vp)</td>
   		<td>Vector 3 (v3)</td>
		<td>True</td>
		<td>True</td>
 	</tr>
	 <tr>
  		<td>Vertex Normal Buffer (vn)</td>
   		<td>Vector 3 (v3)</td>
		<td>True</td>
		<td>False</td>
 	</tr>
	 <tr>
  		<td>Vertex Tangent Buffer (vt)</td>
   		<td>Vector 3 (v3)</td>
		<td>True</td>
		<td>False</td>
 	</tr>
	 <tr>
  		<td>Vertex Color Buffer (vc)</td>
   		<td>Integer 32 (i)</td>
		<td>True</td>
		<td>False</td>
 	</tr>
	  <tr>
  		<td>Vertex UV Buffer (u%d)</td>
   		<td>Vector 2 (v2)</td>
		<td>True</td>
		<td>False</td>
 	</tr>
	 <tr>
  		<td>Vertex Weight Bone Buffer (wb)</td>
   		<td>Integer 32 (i), Short (h), Byte (b)</td>
		<td>True</td>
		<td>False</td>
 	</tr>
	 <tr>
  		<td>Vertex Weight Value Buffer (wv)</td>
   		<td>Float (f)</td>
		<td>True</td>
		<td>False</td>
 	</tr>
	  <tr>
  		<td>Face Buffer (f)</td>
   		<td>Integer 32 (i), Short (h), Byte (b)</td>
		<td>True</td>
		<td>True</td>
 	</tr>
	 <tr>
  		<td>UV Layer Count (ul)</td>
   		<td>Integer 32 (i), Short (h), Byte (b)</td>
		<td>False</td>
		<td>True if has uv layers else False</td>
 	</tr>
	 <tr>
  		<td>Maximum Weight Influence (mi)</td>
   		<td>Integer 32 (i), Short (h), Byte (b)</td>
		<td>False</td>
		<td>True if has weights else False</td>
 	</tr>
	 <tr>
  		<td>Material (Hash of CastNode:Material) (m)</td>
   		<td>Integer 64 (l)</td>
		<td>False</td>
		<td>False</td>
 	</tr>
</table>

**Notes**:
- FaceBuffer is an index into the current meshes vertex data buffers where (0, 1, 2) are the first three vertices from this mesh.
- Each vertex descriptor buffer must contain the same number of elements ex: if you have 16 vertices, you must have 16 normals if they exist, 16 colors if the buffer exists. Otherwise it's assumed they are default / skipped.

### Skeleton:
<table>
	<tr>
		<th>Field</th>
		<th>Type(s)</th>
		<th>IsArray</th>
		<th>Required</th>
 	</tr>
 	<tr>
  		<td>Children</td>
   		<td>Bone</td>
		<td>True</td>
		<td>False</td>
 	</tr>
	 <tr>
  		<td>Parent</td>
   		<td>Model</td>
		<td>False</td>
		<td>True</td>
 	</tr>
</table>

### Bone:
<table>
	<tr>
		<th>Field</th>
		<th>Type(s)</th>
		<th>IsArray</th>
		<th>Required</th>
 	</tr>
 	<tr>
  		<td>Children</td>
   		<td>None</td>
		<td>True</td>
		<td>False</td>
 	</tr>
	 <tr>
  		<td>Parent</td>
   		<td>Skeleton</td>
		<td>False</td>
		<td>True</td>
 	</tr>
</table>
<table>
<tr>
		<th>Property (id)</th>
		<th>Type(s)</th>
		<th>IsArray</th>
		<th>Required</th>
 	</tr>
	 <tr>
  		<td>Name (n)</td>
   		<td>String (s)</td>
		<td>False</td>
		<td>True</td>
 	</tr>
	 <tr>
  		<td>Parent Index (p)</td>
   		<td>Integer 32 (i)</td>
		<td>False</td>
		<td>False</td>
 	</tr>
	 <tr>
  		<td>Segment Scale Compensate (ssc)</td>
   		<td>Byte (b) [True, False]</td>
		<td>False</td>
		<td>False</td>
 	</tr>
	 <tr>
  		<td>Local Position (lp)</td>
   		<td>Vector 3 (v3)</td>
		<td>False</td>
		<td>False</td>
 	</tr>
	 <tr>
  		<td>Local Rotation (lr)</td>
   		<td>Vector 4 (v4)</td>
		<td>False</td>
		<td>False</td>
 	</tr>
	  <tr>
  		<td>World Position (wp)</td>
   		<td>Vector 3 (v3)</td>
		<td>False</td>
		<td>False</td>
 	</tr>
	 <tr>
  		<td>World Rotation (wr)</td>
   		<td>Vector 4 (v4)</td>
		<td>False</td>
		<td>False</td>
 	</tr>
	 <tr>
  		<td>Scale (s)</td>
   		<td>Vector 3 (v3)</td>
		<td>False</td>
		<td>False</td>
 	</tr>
</table>

### Material:
<table>
	<tr>
		<th>Field</th>
		<th>Type(s)</th>
		<th>IsArray</th>
		<th>Required</th>
 	</tr>
 	<tr>
  		<td>Children</td>
   		<td>File</td>
		<td>True</td>
		<td>False</td>
 	</tr>
	 <tr>
  		<td>Parent</td>
   		<td>Model</td>
		<td>False</td>
		<td>True</td>
 	</tr>
</table>
<table>
<tr>
		<th>Property (id)</th>
		<th>Type(s)</th>
		<th>IsArray</th>
		<th>Required</th>
 	</tr>
	 <tr>
  		<td>Name (n)</td>
   		<td>String (s)</td>
		<td>False</td>
		<td>True</td>
 	</tr>
	 <tr>
  		<td>Type (t)</td>
   		<td>String (s)</td>
		<td>False</td>
		<td>True</td>
 	</tr>
	  <tr>
  		<td>Albedo File Hash (albedo)</td>
   		<td>Integer 64 (l)</td>
		<td>False</td>
		<td>True</td>
 	</tr>
	 <tr>
  		<td>Diffuse File Hash (diffuse)</td>
   		<td>Integer 64 (l)</td>
		<td>False</td>
		<td>True</td>
 	</tr>
	 <tr>
  		<td>Normal File Hash (normal)</td>
   		<td>Integer 64 (l)</td>
		<td>False</td>
		<td>True</td>
 	</tr>
	 <tr>
  		<td>Specular File Hash (specular)</td>
   		<td>Integer 64 (l)</td>
		<td>False</td>
		<td>True</td>
 	</tr>
	 <tr>
  		<td>Emissive File Hash (emissive)</td>
   		<td>Integer 64 (l)</td>
		<td>False</td>
		<td>True</td>
 	</tr>
	 <tr>
  		<td>Gloss File Hash (gloss)</td>
   		<td>Integer 64 (l)</td>
		<td>False</td>
		<td>True</td>
 	</tr>
	 <tr>
  		<td>Roughness File Hash (roughness)</td>
   		<td>Integer 64 (l)</td>
		<td>False</td>
		<td>True</td>
 	</tr>
	 <tr>
  		<td>Ambient Occlusion File Hash (ao)</td>
   		<td>Integer 64 (l)</td>
		<td>False</td>
		<td>True</td>
 	</tr>
	 <tr>
  		<td>Cavity File Hash (cavity)</td>
   		<td>Integer 64 (l)</td>
		<td>False</td>
		<td>True</td>
 	</tr>
	 <tr>
  		<td>Extra (x) File Hash (extra%d)</td>
   		<td>Integer 64 (l)</td>
		<td>False</td>
		<td>True</td>
 	</tr>
</table>

### File:
<table>
	<tr>
		<th>Field</th>
		<th>Type(s)</th>
		<th>IsArray</th>
		<th>Required</th>
 	</tr>
 	<tr>
  		<td>Children</td>
   		<td>None</td>
		<td>True</td>
		<td>False</td>
 	</tr>
	 <tr>
  		<td>Parent</td>
   		<td>CastNode</td>
		<td>False</td>
		<td>True</td>
 	</tr>
</table>
<table>
<tr>
		<th>Property (id)</th>
		<th>Type(s)</th>
		<th>IsArray</th>
		<th>Required</th>
 	</tr>
	 <tr>
  		<td>Path (p)</td>
   		<td>String (s)</td>
		<td>False</td>
		<td>True</td>
 	</tr>
</table>

### Animation:
<table>
	<tr>
		<th>Field</th>
		<th>Type(s)</th>
		<th>IsArray</th>
		<th>Required</th>
 	</tr>
 	<tr>
  		<td>Children</td>
   		<td>Skeleton, Curve, NotificiationTrack</td>
		<td>True</td>
		<td>True</td>
 	</tr>
	 <tr>
  		<td>Parent</td>
   		<td>Root</td>
		<td>False</td>
		<td>True</td>
 	</tr>
</table>
<table>
<tr>
		<th>Property (id)</th>
		<th>Type(s)</th>
		<th>IsArray</th>
		<th>Required</th>
 	</tr>
	 <tr>
  		<td>Framerate (fr)</td>
   		<td>Float (f)</td>
		<td>False</td>
		<td>True</td>
 	</tr>
	 <tr>
  		<td>Looping (lo)</td>
   		<td>Byte (b) [True, False]</td>
		<td>False</td>
		<td>False</td>
 	</tr>
	 <tr>
  		<td>Transform Space (ts)</td>
   		<td>String (s) [local, world]</td>
		<td>False</td>
		<td>False</td>
 	</tr>
</table>

### Curve:
<table>
	<tr>
		<th>Field</th>
		<th>Type(s)</th>
		<th>IsArray</th>
		<th>Required</th>
 	</tr>
 	<tr>
  		<td>Children</td>
   		<td>None</td>
		<td>True</td>
		<td>False</td>
 	</tr>
	 <tr>
  		<td>Parent</td>
   		<td>Animation</td>
		<td>False</td>
		<td>True</td>
 	</tr>
</table>
<table>
<tr>
		<th>Property (id)</th>
		<th>Type(s)</th>
		<th>IsArray</th>
		<th>Required</th>
 	</tr>
	 <tr>
  		<td>Node Name (nn)</td>
   		<td>String (s)</td>
		<td>False</td>
		<td>True</td>
 	</tr>
	 <tr>
  		<td>Key Property Name (kp)</td>
   		<td>String (s) [rq, rx, ry, rz, tx, ty, tz, sx, sy, sz, vb]</td>
		<td>False</td>
		<td>True</td>
 	</tr>
	 <tr>
  		<td>Key Frame Buffer (kb)</td>
   		<td>Byte (b), Short (h), Integer 32 (i), Float (f)</td>
		<td>True</td>
		<td>True</td>
 	</tr>
	 <tr>
  		<td>Key Value Buffer (kv)</td>
   		<td>Byte (b), Short (h), Integer 32 (i), Float (f), Vector 4 (v4)</td>
		<td>True</td>
		<td>True</td>
 	</tr>
	 <tr>
  		<td>Mode (m)</td>
   		<td>String (s) [additive, absolute, relative]</td>
		<td>False</td>
		<td>True</td>
 	</tr>
</table>

### NotificationTrack:
<table>
	<tr>
		<th>Field</th>
		<th>Type(s)</th>
		<th>IsArray</th>
		<th>Required</th>
 	</tr>
 	<tr>
  		<td>Children</td>
   		<td>None</td>
		<td>True</td>
		<td>False</td>
 	</tr>
	 <tr>
  		<td>Parent</td>
   		<td>Animation</td>
		<td>False</td>
		<td>True</td>
 	</tr>
</table>
<table>
<tr>
		<th>Property (id)</th>
		<th>Type(s)</th>
		<th>IsArray</th>
		<th>Required</th>
 	</tr>
	 <tr>
  		<td>Name (n)</td>
   		<td>String (s)</td>
		<td>False</td>
		<td>True</td>
 	</tr>
	 <tr>
  		<td>Key Frame Buffer (kb)</td>
   		<td>Byte (b), Short (h), Integer 32 (i), Float (f)</td>
		<td>True</td>
		<td>True</td>
 	</tr>
</table>

<br>

- Format designed by DTZxPorter with input from various developers.
- Icons by Smashicons