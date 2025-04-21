# Cast | An open-source container for models, animations, and more

The goal of cast is to create an easy to use format for models, animations, materials, and game worlds. In addition, cast should be able to produce the same scenes in any 3d software.

<p align="center">
	<img src="images/cast-icon-md.png" alt="Cast"/>
</p>

## 3D Engine Plugins:
- Autodesk Maya (2016+): [Releases](https://github.com/dtzxporter/cast/releases)
- Blender (3.6+): [Releases](https://github.com/dtzxporter/cast/releases)

# Programming libraries:
- .NET Framework (Reference): [Libraries/DotNet](https://github.com/dtzxporter/cast/tree/master/libraries/dotnet)
- .NET Framework (by Scobalula): [Cast.NET](https://github.com/Scobalula/Cast.NET)
- Python: [Libraries/Python](https://github.com/dtzxporter/cast/tree/master/libraries/python)

# Viewers:
- CastModelViewer (By echo000): [Github](https://github.com/echo000/CastModelViewer)

# Coming from SEAnim/SEModel:
- SECast, a lossless converter to cast: [SECast](https://dtzxporter.com/tools/secast)
- **Note:** If your tool supports exporting to cast directly, that is always better.

# FAQ:
- Frequently asked questions: [FAQ](FAQ.md)

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
	Hair = 0x72696168,
	BlendShape = 0x68736C62,
	Skeleton = 0x6C656B73,
	Bone = 0x656E6F62,
	IKHandle = 0x64686B69,
	Constraint = 0x74736E63,
	Animation = 0x6D696E61,
	Curve = 0x76727563,
	CurveModeOverride = 0x564F4D43,
	NotificationTrack = 0x6669746E,
	Material = 0x6C74616D,
	File = 0x656C6966,
	Color = 0x726C6F63,
	Instance = 0x74736E69,
	Metadata = 0x6174656D,
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

Cast ids are stored as integers to make it faster to serialize and deserialize.

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
   		<td>Skeleton, Mesh, Hair, Blend Shape, Material</td>
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
		<td>False</td>
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
  		<td>Name (n)</td>
   		<td>String (s)</td>
		<td>False</td>
		<td>False</td>
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
  		<td>Vertex Color Buffer (c%d)</td>
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
  		<td>Color Layer Count (cl)</td>
   		<td>Integer 32 (i), Short (h), Byte (b)</td>
		<td>False</td>
		<td>True if has color layers else False</td>
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
  		<td>Skinning Method (sm)</td>
   		<td>String (s) [linear, quaternion]</td>
		<td>False</td>
		<td>False</td>
 	</tr>
	 <tr>
  		<td>Material (Hash of CastNode:Material) (m)</td>
   		<td>Integer 64 (l)</td>
		<td>False</td>
		<td>False</td>
 	</tr>
</table>

**Notes**:
- `Face Buffer` is an index into the current meshes vertex data buffers where (0, 1, 2) are the first three vertices from this mesh.
- The `Face Buffer` follows CCW (right-handed) winding order, this may be different in other apis, where you may have to remap the indices.
- If a face contains an invalid index combination `(0, 1, 1), (0, 1, 0), (0, 0, 0)` where two or more indices are the same, it is acceptable for the user processing these faces to ignore them in order to properly render the mesh. It would be wise to present the user with a warning stating that this happened.
- Each vertex descriptor buffer must contain the same number of elements ex: if you have 16 vertices, you must have 16 normals if they exist, 16 colors if the buffer exists. Otherwise it's assumed they are default / skipped.
- Weights are additive which means having the same bone with `0.5` and `0.5` would end up making that bones influence `1.0` for example.
- The default skinning method is `linear`. When set to `quaternion` dual quaternion skinning is used.
- **NEW 8/18/2024**: The vertex color specification has **changed**, in order to support multiple color layers, a new `Color Layer Count (cl)` was added which mimics the `UV Layer Count (ul)` property.
  - To be backwards compatible, cast processors should check for `cl`, and use that by default along with the new `c%d` layer properties.
  - If the `cl` property does not exist, a processor should check for the legacy `vc` property which is the one and only color layer if it exists.

### Hair:
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
  		<td>Name (n)</td>
   		<td>String (s)</td>
		<td>False</td>
		<td>False</td>
 	</tr>
	<tr>
  		<td>Segments Buffer (se)</td>
   		<td>Integer 32 (i), Short (h), Byte (b)</td>
		<td>True</td>
		<td>True</td>
 	</tr>
	<tr>
  		<td>Particle Buffer (pt)</td>
   		<td>Vector 3 (v3)</td>
		<td>True</td>
		<td>True</td>
 	</tr>
	<tr>
  		<td>Material (Hash of CastNode:Material) (m)</td>
   		<td>Integer 64 (l)</td>
		<td>False</td>
		<td>False</td>
 	</tr>
</table>

**Notes**:
- The `Particle Buffer` stores the particles in order by each strand, in world space.
- For each strand, there is a count in `Segments Buffer`, there is `count + 1` particles for each strand.
  - A segment is the connection between two particles.
  - The sequence `1 -> 2 -> 3` is two segments `1 -> 2, 2 -> 3`.

### Blend Shape:
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
  		<td>Name (n)</td>
   		<td>String (s)</td>
		<td>False</td>
		<td>True</td>
 	</tr>
	<tr>
  		<td>Base Shape (Hash of CastNode:Mesh) (b)</td>
   		<td>Integer 64 (l)</td>
		<td>False</td>
		<td>True</td>
 	</tr>
	<tr>
  		<td>Target Shape Vertex Indices (vi)</td>
   		<td>Byte (b), Short (h), Integer 32 (i)</td>
		<td>True</td>
		<td>True</td>
 	</tr>
	<tr>
		<td>Target Shape Vertex Positions (vp)</td>
		<td>Vector 3 (v3)</td>
		<td>True</td>
		<td>True</td>
	</tr>
	<tr>
  		<td>Target Weight Scale (ts)</td>
   		<td>Float (f)</td>
		<td>True</td>
		<td>False</td>
 	</tr>
</table>

**Notes**:
- The `Base Shape` must be an existing cast mesh.
- The `Target Shape Vertex Indices` and `Target Shape Vertex Positions` must be the same length as they are paired together.
- `Target Shape Vertex Positions` is the final value of each changed vertex position ignoring the `Base Shape`'s corresponding vertex.
- `Target Weight Scale` indicates the maximum value the target shape can deform to and should default to `1.0`.

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
   		<td>Bone, IKHandle, Constraint</td>
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

**Notes**:
- `Segment Scale Compensate` should default to `True` when not specified.
- `Scale` is always local to the current bone.

### IKHandle:
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
		<td>False</td>
 	</tr>
	<tr>
  		<td>Start Bone Hash (sb)</td>
   		<td>Integer 64 (l)</td>
		<td>False</td>
		<td>True</td>
 	</tr>
	<tr>
  		<td>End Bone Hash (eb)</td>
   		<td>Integer 64 (l)</td>
		<td>False</td>
		<td>True</td>
 	</tr>
	<tr>
  		<td>Target Bone Hash (tb)</td>
   		<td>Integer 64 (l)</td>
		<td>False</td>
		<td>False</td>
 	</tr>
	<tr>
  		<td>Pole Vector Bone Hash (pv)</td>
   		<td>Integer 64 (l)</td>
		<td>False</td>
		<td>False</td>
 	</tr>
	<tr>
  		<td>Pole Bone Hash (pb)</td>
   		<td>Integer 64 (l)</td>
		<td>False</td>
		<td>False</td>
 	</tr>
	<tr>
  		<td>Use Target Rotation (tr)</td>
   		<td>Byte (b) [True, False]</td>
		<td>False</td>
		<td>False</td>
 	</tr>
</table>

**Notes**:
- `Use Target Rotation` should default to `False` when not specified.
- `Pole Bone` must only effect the twist of the chain, in general you either have a `Pole Bone` or a `Pole Vector Bone`.

### Constraint:
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
		<td>False</td>
 	</tr>
	<tr>
  		<td>Constraint Type (ct)</td>
   		<td>String (s) [pt, or, sc]</td>
		<td>False</td>
		<td>True</td>
 	</tr>
	<tr>
  		<td>Constraint Bone Hash (cb)</td>
   		<td>Integer 64 (l)</td>
		<td>False</td>
		<td>True</td>
 	</tr>
	<tr>
  		<td>Target Bone Hash (tb)</td>
   		<td>Integer 64 (l)</td>
		<td>False</td>
		<td>True</td>
 	</tr>
	<tr>
  		<td>Maintain Offset (mo)</td>
   		<td>Byte (b) [True, False]</td>
		<td>False</td>
		<td>False</td>
 	</tr>
	<tr>
  		<td>Custom Offset (co)</td>
   		<td>Vector3, Vector 4 (v3, v4)</td>
		<td>False</td>
		<td>False</td>
 	</tr>
	<tr>
  		<td>Weight (wt)</td>
   		<td>Float (f)</td>
		<td>False</td>
		<td>False</td>
 	</tr>
	<tr>
  		<td>Skip X (sx)</td>
   		<td>Byte (b) [True, False]</td>
		<td>False</td>
		<td>False</td>
 	</tr>
	<tr>
  		<td>Skip Y (sy)</td>
   		<td>Byte (b) [True, False]</td>
		<td>False</td>
		<td>False</td>
 	</tr>
	<tr>
  		<td>Skip Z (sz)</td>
   		<td>Byte (b) [True, False]</td>
		<td>False</td>
		<td>False</td>
 	</tr>
</table>

**Notes**:
- The constraint type values correspond to:
  - `pt` Point Constraint, which applies to translations.
  - `or` Orient Constraint, which applies to rotations.
  - `sc` Scale Constraint, which applies to scales.
- Maintain offset should default to `False` when not specified.
- Custom offset should match the following for the constraint types:
  - `pt`: Vector 3, default: `[0.0, 0.0, 0.0]`.
  - `or`: Vector 4, default: `[0.0, 0.0, 0.0, 1.0]`.
  - `sc`: Vector 3, default: `[1.0, 1.0, 1.0]`.
- Skip X, Skip Y, and Skip Z should default to `False` when not specified and refer to ignoring that axis in the constraint.

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
   		<td>File, Color</td>
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
   		<td>String (s) [pbr]</td>
		<td>False</td>
		<td>True</td>
 	</tr>
	  <tr>
  		<td>Albedo Hash (albedo)</td>
   		<td>Integer 64 (l)</td>
		<td>False</td>
		<td>False</td>
 	</tr>
	 <tr>
  		<td>Diffuse Hash (diffuse)</td>
   		<td>Integer 64 (l)</td>
		<td>False</td>
		<td>False</td>
 	</tr>
	 <tr>
  		<td>Normal Hash (normal)</td>
   		<td>Integer 64 (l)</td>
		<td>False</td>
		<td>False</td>
 	</tr>
	 <tr>
  		<td>Specular Hash (specular)</td>
   		<td>Integer 64 (l)</td>
		<td>False</td>
		<td>False</td>
 	</tr>
	 <tr>
  		<td>Gloss Hash (gloss)</td>
   		<td>Integer 64 (l)</td>
		<td>False</td>
		<td>False</td>
 	</tr>
	 <tr>
  		<td>Roughness Hash (roughness)</td>
   		<td>Integer 64 (l)</td>
		<td>False</td>
		<td>False</td>
 	</tr>
	<tr>
  		<td>Emissive Hash (emissive)</td>
   		<td>Integer 64 (l)</td>
		<td>False</td>
		<td>False</td>
	</tr>
	<tr>
  		<td>Emissive Mask Hash (emask)</td>
   		<td>Integer 64 (l)</td>
		<td>False</td>
		<td>False</td>
	</tr>
	 <tr>
  		<td>Ambient Occlusion Hash (ao)</td>
   		<td>Integer 64 (l)</td>
		<td>False</td>
		<td>False</td>
 	</tr>
	 <tr>
  		<td>Cavity Hash (cavity)</td>
   		<td>Integer 64 (l)</td>
		<td>False</td>
		<td>False</td>
 	</tr>
	<tr>
  		<td>Anisotropy Hash (aniso)</td>
   		<td>Integer 64 (l)</td>
		<td>False</td>
		<td>False</td>
 	</tr>
	 <tr>
  		<td>Extra (x) Hash (extra%d)</td>
   		<td>Integer 64 (l)</td>
		<td>False</td>
		<td>False</td>
 	</tr>
</table>

**Notes**:
- The hash properties link to children of the material which can be:
  - A `File` which points to a texture.
  - A `Color` which has a single rgba value.

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
   		<td>Material, Instance</td>
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

### Color:
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
   		<td>Material</td>
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
		<td>False</td>
 	</tr>
	<tr>
  		<td>Color Space (cs)</td>
   		<td>String (s) [srgb, linear]</td>
		<td>False</td>
		<td>False</td>
 	</tr>
	<tr>
  		<td>Rgba Color (rgba)</td>
   		<td>Vector 4 (v4)</td>
		<td>False</td>
		<td>True</td>
 	</tr>
</table>

**Notes**:
- The `Color Space` property should default to `srgb` when not specified.

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
   		<td>Skeleton, Curve, CurveModeOverride, NotificationTrack</td>
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
		<td>Name (n)</td>
   		<td>String (s)</td>
		<td>False</td>
		<td>False</td>
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
   		<td>String (s) [rq, tx, ty, tz, sx, sy, sz, bs, vb]</td>
		<td>False</td>
		<td>True</td>
 	</tr>
	 <tr>
  		<td>Key Frame Buffer (kb)</td>
   		<td>Byte (b), Short (h), Integer 32 (i)</td>
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
	 <tr>
  		<td>Additive Blend Weight (ab)</td>
   		<td>Float (f)</td>
		<td>False</td>
		<td>False</td>
 	</tr>
</table>

**Notes**:
- All curve keyframes are in object/node space.
- The `Mode` determines how each curve keyframe is applied to the node.
  - `additive`: The keyframe is added to the current scene frame value of the nodes property.
  - `absolute`: The keyframe is the exact value for the given frame.
  - `relative`: The keyframe is added to the rest position value of the nodes property.
- The property values correspond to:
  - `rq` Rotation Quaternion and expects `v4` values.
  - `tx` Translation 'X' and expects `f` values.
  - `ty` Translation 'Y' and expects `f` values.
  - `tz` Translation 'Z' and expects `f` values.
  - `sx` Scale 'X' and expects `f` values.
  - `sy` Scale 'Y' and expects `f` values.
  - `sz` Scale 'Z' and expects `f` values.
  - `bs` BlendShape Weight and expects `f` values.
  - `vb` Visibility and expects `b`, `h`, or `i` values.
    - `=0` = hidden.
    - `>=1` = visible.
- The properties `tx`, `ty`, `tz`, `sx`, `sy`, `sz`, `bs`, `vb` should interpolate linearly.
- The property `rq` should interpolate with quaternion slerp.

### CurveModeOverride:
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
  		<td>Mode (m)</td>
   		<td>String (s) [additive, absolute, relative]</td>
		<td>False</td>
		<td>True</td>
 	</tr>
	<tr>
  		<td>Override Translation Curves (ot)</td>
   		<td>Byte (b) [True, False]</td>
		<td>False</td>
		<td>False</td>
 	</tr>
	<tr>
  		<td>Override Rotation Curves (or)</td>
   		<td>Byte (b) [True, False]</td>
		<td>False</td>
		<td>False</td>
 	</tr>
	<tr>
  		<td>Override Scale Curves (os)</td>
   		<td>Byte (b) [True, False]</td>
		<td>False</td>
		<td>False</td>
 	</tr>
</table>

**Notes:**
- See `Curve` notes above for the definition of each `Mode` value.
- `Override Translation Curves` should default to `False` when not specified.
- `Override Rotation Curves` should default to `False` when not specified.
- `Override Scale Curves` should default to `False` when not specified.
- The override node and all of it's children should override their curves mode to the new mode.
- The override node must be present at the time of processing in order to determine if a child bone is a descendent.

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
   		<td>Byte (b), Short (h), Integer 32 (i)</td>
		<td>True</td>
		<td>True</td>
 	</tr>
</table>

### Instance:
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
  		<td>Name (n)</td>
   		<td>String (s)</td>
		<td>False</td>
		<td>False</td>
 	</tr>
	<tr>
  		<td>Reference File (Hash of CastNode:File) (rf)</td>
   		<td>Integer 64 (l)</td>
		<td>False</td>
		<td>True</td>
 	</tr>
	<tr>
  		<td>Position (p)</td>
   		<td>Vector 3 (v3)</td>
		<td>False</td>
		<td>True</td>
 	</tr>
	<tr>
  		<td>Rotation (r)</td>
   		<td>Vector 4 (v4)</td>
		<td>False</td>
		<td>True</td>
 	</tr>
	<tr>
		<td>Scale (s)</td>
   		<td>Vector 3 (v3)</td>
		<td>False</td>
		<td>True</td>
	</tr>
</table>

### Metadata:
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
  		<td>Author (a)</td>
   		<td>String (s)</td>
		<td>False</td>
		<td>False</td>
 	</tr>
	<tr>
  		<td>Software (s)</td>
   		<td>String (s)</td>
		<td>False</td>
		<td>False</td>
 	</tr>
	<tr>
  		<td>Up Axis (up)</td>
   		<td>String (s) [x, y, z]</td>
		<td>False</td>
		<td>False</td>
 	</tr>
</table>

**Notes:**
- `Author` and `Software` are just for tagging cast files and have no use outside of metadata.
- `Up Axis` can be used as a hint to software to adjust the scene to match a specific up axis.
- A cast file can have any number of meta nodes but properties designed for hinting should only use the first metadata node instance.

<br>

- Format designed by DTZxPorter with input from the community.
- Icons by Smashicons