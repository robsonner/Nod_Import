import os
import bpy
import bmesh

from .nod_bone import NodBone
from .binary_reader import BinaryReader
from .vector3 import Vector3
from .vector2 import Vector2
from .nod_vertex import NodVertex
from .nod_face import NodFace
from .nod_file import NodFile
from bpy.types import ArmatureEditBones
from mathutils import Vector, Matrix
from .nod_to_blender_skeleton import *
from .test_weights_bones import *
from .import_settings import ImportSettings

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

def add_mesh(name, verts, faces, normals,edges=None, col_name="Collection"):    
    if edges is None:
        edges = []
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(mesh.name, mesh)
    col = bpy.data.collections[col_name]
    col.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    mesh.from_pydata(verts, edges, faces)
    #added some smoothing
    mesh.update()
    mesh.calc_loop_triangles()

    for i, loop in enumerate(mesh.loops):
        vert_idx = loop.vertex_index
        if vert_idx < len(normals):
            loop.normal = normals[vert_idx]

    # Enable smooth shading
    for face in mesh.polygons:
        face.use_smooth = True
    
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
        print(f"The texture with filepath '{imagePath}' for material '{materialName}' does not exist.")
        
    return material

def CreateMeshes(nodFile : NodFile, settings: ImportSettings):
    #cursors positions
    vertPosition = 0 
    facePosition = 0
    materials =[]
    weighted_meshes = []
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

        mesh,obj = add_mesh(nodFile.mesh_names[groupMesh.mesh_num],vertices,faces,normals)
        weighted_meshes.append((
            obj,
            nodFile.vertices[vertPosition - groupMesh.num_vertices:vertPosition],
            groupMesh,
        ))
        materialName = nodFile.header.material_names[groupMesh.material_id]
        add_uv(obj,mesh,uv,materialName)
        materialName = materialName.rstrip('\x00')
        material = None
        #TODO: is this needed?
        if len(materials) > 0:
            for m in materials:
                if m.name == str(materialName):
                    material = m
        
        #material = next(x for x in materials if x.name == materialName)
        
        if material is None: 
            material = create_material(materialName, settings.textures_dir_path)
            materials.append(material)       

        if len(mesh.materials) < 1: #if no materials on the object
            mesh.materials.append(material) 
            #this will create a slot and add the material
        else:
            mesh.materials[mesh.active_material_index].material = material 

        vertices.clear()
        faces.clear()
        edges.clear()

    armature_obj = None
    if(settings.load_bones):
        #create_blender_skeleton_from_nod(nodFile.bones)
        armature_obj = create_blender_skeleton_from_nod_with_mesh(
            nodFile.vertices, nodFile.bones
        )
        for mesh_obj, group_vertices, group_mesh in weighted_meshes:
            attach_nod_mesh_to_armature(
                mesh_obj,
                group_vertices,
                nodFile.bones,
                armature_obj,
                group_mesh.group_flags,
                group_mesh.bone_num,
            )
    return armature_obj

