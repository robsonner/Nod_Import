import os
import bpy
import bmesh

from .binary_reader import BinaryReader
from .vector3 import Vector3
from .vector2 import Vector2
from .nod_vertex import NodVertex
from .nod_face import NodFace
from .nod_file import NodFile

def LoadModel(data) -> NodFile:
     bs = BinaryReader(data, "little") #the files are in little-endian
     nod_file = NodFile(bs) 
     print("We read everything, now position of buffer: ",bs.position," and length: ", bs.length)
     return nod_file

def CreateMesh(vertices, faces, edges, meshName):
    new_mesh = bpy.data.meshes.new(meshName)
    new_mesh.from_pydata(vertices, edges, faces)
    new_mesh.update()
    return new_mesh

def add_mesh(name, verts, faces, edges=None, col_name="Collection"):    
    if edges is None:
        edges = []
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(mesh.name, mesh)
    col = bpy.data.collections[col_name]
    col.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    mesh.from_pydata(verts, edges, faces)
    return mesh, obj

def add_normals(mesh, normals):
    return ''

def add_uv(obj, mesh, uvs, textureName):
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(mesh)

    uv_layer = bm.loops.layers.uv.verify()
    #bm.faces.layers.tex.verify()

    for f in bm.faces:
        for l in f.loops:
            luv = l[uv_layer]
            luv.uv = tuple(uvs[l.vert.index])

    bmesh.update_edit_mesh(mesh)
    bpy.ops.object.mode_set(mode='OBJECT')
        
        # Create a new UVMap
    #uv_layer = mesh.uv_layers.new(name="UVMap")

    # Fill in your UVs
    #uv_layer.data.foreach_set("uv", uv)
    """
    uv_layer = mesh.loops.layers.uv.verify()
    mesh.faces.layers.tex.verify()

    face = mesh.faces[-1]
    for i, loop in enumerate(face.loops):
        loop[uv_layer].uv = uv[i]
    
    # assign material
    try:
        material_names = [ m.name for m in obj.data.materials ]
        material_id = material_names.index(textureName)
    except ValueError:
        obj.data.materials.append(bpy.data.materials[textureName])
        material_id = len(obj.data.materials) - 1

    face.material_index = material_id
    """

def add_bones(obj, mesh, bones, nodVertices):
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(mesh)
    vertices = bm.verts

    bmesh.update_edit_mesh(mesh)
    bpy.ops.object.mode_set(mode='OBJECT')   

def create_material(materialName : str, texturePath: str) -> bpy.types.Material:
    material = bpy.data.materials.new(name=materialName)
    material.use_nodes = True  # Enable the use of nodes for this material

    # Get the Principled BSDF node from the material's node tree
    bsdf_node = material.node_tree.nodes.get('Principled BSDF')
    if not bsdf_node:
        raise ValueError("No 'Principled BSDF' node found in the material")

    # Add a texture node to the material
    texture_node = material.node_tree.nodes.new(type='ShaderNodeTexImage')
    material.node_tree.links.new(texture_node.outputs['Color'], bsdf_node.inputs['Base Color'])

    # Set the texture file path (you need to specify a valid image file)

    imagePath= texturePath + materialName + '.tga'
    if os.path.isfile(imagePath):
        texture_node.image = bpy.data.images.load(filepath= imagePath)
    else:
        print(f"The file '{imagePath}' does not exist.")
        
    return material

def CreateMeshes(nodFile : NodFile):
    #cursors positions
    vertPosition = 0 
    facePosition = 0
    materials =[]
    #for i in range(nodFile.header.num_meshes):
    for groupMesh in nodFile.mesh_groups:
        vertices = []
        faces = []
        edges = []
        normals = []
        uv = []
        for j in range(groupMesh.num_vertices):
            vertice = nodFile.vertices[vertPosition + j]
            vertices.append((vertice.position.x,vertice.position.y,vertice.position.z))
            normals.append((vertice.normal.x,vertice.normal.y,vertice.normal.z))
            uv.append((vertice.uv.x,vertice.uv.y))
        for k in range(groupMesh.num_faces):
            face = nodFile.faces[facePosition + k]
            faces.append((face.x,face.y,face.z))

        vertPosition = vertPosition + groupMesh.num_vertices
        facePosition = facePosition + groupMesh.num_faces

        mesh,obj = add_mesh(nodFile.mesh_names[groupMesh.mesh_num],vertices,faces)
        materialName = nodFile.header.material_names[groupMesh.material_id]
        add_uv(obj,mesh,uv,materialName)
        add_bones(obj,mesh, nodFile.bones, vertices)
        
        materialName = materialName.rstrip('\x00')
        material = None
        #TODO: is this needed?
        if len(materials) > 0:
            for m in materials:
                if m.name == str(materialName):
                    material = m
        
        #material = next(x for x in materials if x.name == materialName)
        
        #TODO load this from settings
        if material is None: 
            #TODO check if the file actually exists :P
            material = create_material(materialName, "C:/GOG Games/Vampire The Masquerade - Redemption/Extracted/Resource/3d/Materials/")
            #material = bpy.data.materials.new(materialName)
            materials.append(material)       

        if len(mesh.materials) < 1: #if no materials on the object
            mesh.materials.append(material) 
            #this will create a slot and add the material
        else:
            mesh.materials[mesh.active_material_index].material = material 

        vertices.clear()
        faces.clear()
        edges.clear()
    

#class LoadNodFileOperator(bpy.types.Operator):
#    """Load predefined nod file for testing"""
#    bl_idname = "mesh.load_nod_file"
#    bl_label = "Load Nod File"

#    def execute(self, context):
#        in_file = open("F:\GOG Games\Vampire The Masquerade - Redemption\ExtractedModels\christof.nod", "rb") # opening for [r]eading as [b]inary
#        data = in_file.read()
#        in_file.close()
#        nodFile = LoadModel(data) 
#        CreateMeshes(nodFile)
#        #bpy.ops.mesh.primitive_cube_add(size=2, enter_editmode=False, align='WORLD', location=(0, 0, 0))
#        return {'FINISHED'}
    

#class TestPanel(bpy.types.Panel):
#    """ Displayy panel in 3D view"""
#    bl_label = "Sample Addon"
#    bl_space_type = "VIEW_3D"
#    bl_region_type = "UI"
#    bl_options = {'HEADER_LAYOUT_EXPAND'}
#    
#    def draw(self, context):
#        layout = self.layout
#        col = layout.column(align=True)
#        col.operator("mesh.load_nod_file", icon="MESH_CUBE")
#        #col.operator("mesh.add_material", icon="SHADING_RENDERED")