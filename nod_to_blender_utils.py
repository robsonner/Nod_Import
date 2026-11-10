import math
import os

import bpy

from .binary_reader import BinaryReader
from .debug_logging import debug_print
from .import_settings import ImportSettings
from .nod_file import NodFile
from .nod_skinning import (
    attach_nod_mesh_to_armature,
    create_blender_skeleton_from_nod_with_mesh,
)


def LoadModel(data) -> NodFile:
    bs = BinaryReader(data, "little")  # the files are in little-endian
    nod_file = NodFile(bs)
    debug_print("We read everything, now position of buffer: ",
                bs.position, " and length: ", bs.length)
    return nod_file


def _normalize_normals(normals):
    normalized = []
    for nx, ny, nz in normals:
        length_sq = nx * nx + ny * ny + nz * nz
        if length_sq > 1e-12:
            inv_len = 1.0 / math.sqrt(length_sq)
            normalized.append((nx * inv_len, ny * inv_len, nz * inv_len))
        else:
            normalized.append((0.0, 0.0, 1.0))
    return normalized


def add_mesh(name, verts, faces, normals, edges=None, collection=None):
    if edges is None:
        edges = []

    num_vertices = len(verts)
    valid_faces = []
    rejected_faces = 0
    for f in faces:
        v0, v1, v2 = f[0], f[1], f[2]
        if (
            v0 < 0 or v0 >= num_vertices or
            v1 < 0 or v1 >= num_vertices or
            v2 < 0 or v2 >= num_vertices or
            v0 == v1 or v1 == v2 or v0 == v2
        ):
            rejected_faces += 1
        else:
            valid_faces.append(f)

    if rejected_faces > 0:
        print(f"WARNING: mesh '{name}': rejected {rejected_faces} invalid face(s)")

    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(mesh.name, mesh)

    target_collection = collection or bpy.context.collection
    if target_collection is None and bpy.context.scene is not None:
        target_collection = bpy.context.scene.collection
    if target_collection is not None:
        target_collection.objects.link(obj)

    mesh.from_pydata(verts, edges, valid_faces)
    mesh.validate(verbose=False)

    if len(mesh.polygons) > 0:
        mesh.polygons.foreach_set("use_smooth", [True] * len(mesh.polygons))

    if normals:
        mesh.normals_split_custom_set_from_vertices(_normalize_normals(normals))

    return mesh, obj


def add_uv(mesh, uvs):
    uv_layer = mesh.uv_layers.new(name="UVMap")
    num_loops = len(mesh.loops)
    if num_loops == 0:
        return
    loop_vert_indices = [0] * num_loops
    mesh.loops.foreach_get("vertex_index", loop_vert_indices)
    flat_uvs = [coord for vi in loop_vert_indices for coord in uvs[vi]]
    uv_layer.data.foreach_set("uv", flat_uvs)


def _find_file_in_dirs(target_filename: str, candidate_dirs: list, dir_cache: dict):
    lower_target = target_filename.lower()
    for raw_dir in candidate_dirs:
        directory = bpy.path.abspath(raw_dir)
        if not os.path.isdir(directory):
            continue
        exact_path = os.path.join(directory, target_filename)
        if os.path.isfile(exact_path):
            return exact_path
        if directory not in dir_cache:
            try:
                dir_cache[directory] = {f.lower(): f for f in os.listdir(directory)}
            except OSError:
                dir_cache[directory] = {}
        matched_filename = dir_cache[directory].get(lower_target)
        if matched_filename:
            candidate_path = os.path.join(directory, matched_filename)
            if os.path.isfile(candidate_path):
                return candidate_path
    return None


def _parse_nam_file(nam_path: str) -> dict:
    """Parse a Nihilistic Animated Material (.nam) ASCII file for texture, twosided, and masked flags."""
    info = {
        "texture": None,
        "twosided": False,
        "masked": False,
    }
    try:
        with open(nam_path, "r", encoding="cp1252", errors="replace") as stream:
            for raw_line in stream:
                line = raw_line.split(";", 1)[0].split("//", 1)[0].strip()
                if not line:
                    continue
                tokens = line.split()
                kw = tokens[0].lower()
                if kw == "texture" and len(tokens) >= 2 and info["texture"] is None:
                    info["texture"] = tokens[1]
                elif kw == "pass" and len(tokens) >= 4 and info["texture"] is None:
                    tex_token = tokens[3] if tokens[2].lower() == "nomip" and len(tokens) >= 5 else tokens[2]
                    if not tex_token.startswith("$"):
                        info["texture"] = tex_token
                elif kw == "twosided":
                    info["twosided"] = True
                elif kw == "masked":
                    info["masked"] = True
    except OSError as exc:
        print(f"WARNING: Failed to read NAM file '{nam_path}': {exc}")
    return info


def _ensure_tga_ext(name: str) -> str:
    if name.lower().endswith(".tga"):
        return name
    return name + ".tga"


def create_material(materialName: str, texturePath, dir_cache: dict = None) -> bpy.types.Material:
    material = bpy.data.materials.new(name=materialName)
    material["nod_source_name"] = materialName

    # Find or create Principled BSDF node
    bsdf_node = next((n for n in material.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if not bsdf_node:
        bsdf_node = material.node_tree.nodes.new(type='ShaderNodeBsdfPrincipled')
        output_node = next((n for n in material.node_tree.nodes if n.type == 'OUTPUT_MATERIAL'), None)
        if not output_node:
            output_node = material.node_tree.nodes.new(type='ShaderNodeOutputMaterial')
        material.node_tree.links.new(bsdf_node.outputs['BSDF'], output_node.inputs['Surface'])

    if isinstance(texturePath, (list, tuple)):
        candidate_dirs = [str(p).strip() for p in texturePath if p and str(p).strip()]
    elif texturePath and str(texturePath).strip():
        candidate_dirs = [str(texturePath).strip()]
    else:
        candidate_dirs = []

    if not candidate_dirs:
        debug_print(f"No textures directory specified for material '{materialName}'.")
        return material

    if dir_cache is None:
        dir_cache = {}

    twosided = False
    masked = False
    target_tga = _ensure_tga_ext(materialName)

    # 1. Check for a .nam material definition file first (as per NOD Engine SDK nam.htm)
    nam_path = _find_file_in_dirs(materialName + ".nam", candidate_dirs, dir_cache)
    if nam_path:
        nam_info = _parse_nam_file(nam_path)
        twosided = nam_info["twosided"]
        masked = nam_info["masked"]
        if nam_info["texture"]:
            target_tga = _ensure_tga_ext(nam_info["texture"])
        debug_print(
            f"Material '{materialName}': loaded NAM '{nam_path}' "
            f"(texture='{target_tga}', twosided={twosided}, masked={masked})"
        )

    # 2. Search for the resolved .tga file
    found_path = _find_file_in_dirs(target_tga, candidate_dirs, dir_cache)

    # 3. Fallback: if neither .nam nor .tga resolved and material ends with '_dbl', strip '_dbl'
    if not found_path and materialName.lower().endswith("_dbl") and len(materialName) > 4:
        base_name = materialName[:-4]
        fallback_tga = _ensure_tga_ext(base_name)
        print(
            f"WARNING: Material '{materialName}': '{target_tga}' (and '{materialName}.nam') not found; "
            f"falling back to '{fallback_tga}' with two-sided rendering (stripped '_dbl' suffix)"
        )
        twosided = True
        found_path = _find_file_in_dirs(fallback_tga, candidate_dirs, dir_cache)

    material.use_backface_culling = not twosided

    if found_path:
        texture_node = material.node_tree.nodes.new(type='ShaderNodeTexImage')
        texture_node.image = bpy.data.images.load(filepath=found_path, check_existing=True)
        material.node_tree.links.new(texture_node.outputs['Color'], bsdf_node.inputs['Base Color'])

        if masked:
            math_node = material.node_tree.nodes.new(type='ShaderNodeMath')
            math_node.operation = 'GREATER_THAN'
            math_node.inputs[1].default_value = 0.5
            material.node_tree.links.new(texture_node.outputs['Alpha'], math_node.inputs[0])
            material.node_tree.links.new(math_node.outputs['Value'], bsdf_node.inputs['Alpha'])
    else:
        debug_print(f"Texture '{target_tga}' for material '{materialName}' not found in {candidate_dirs}.")

    return material


def CreateMeshes(nodFile: NodFile, settings: ImportSettings, collection=None):
    materials_by_source_name = {}
    dir_cache = {}
    vertPosition = 0
    facePosition = 0
    weighted_meshes = []

    for group_idx, groupMesh in enumerate(nodFile.mesh_groups):
        vertices = []
        faces = []
        normals = []
        uv = []
        for j in range(groupMesh.num_vertices):
            vertice = nodFile.vertices[vertPosition + j]
            vertices.append((vertice.position.x, vertice.position.y, vertice.position.z))
            normals.append((vertice.normal.x, vertice.normal.y, vertice.normal.z))
            uv.append((vertice.uv.x, vertice.uv.y))
        for k in range(groupMesh.num_faces):
            face = nodFile.faces[facePosition + k]
            faces.append((face.x, face.y, face.z))

        vertPosition = vertPosition + groupMesh.num_vertices
        facePosition = facePosition + groupMesh.num_faces

        if 0 <= groupMesh.mesh_num < len(nodFile.mesh_names):
            raw_mesh_name = nodFile.mesh_names[groupMesh.mesh_num]
            mesh_name = raw_mesh_name.split("\x00", 1)[0]
            if not mesh_name:
                mesh_name = f"NOD_Mesh_{group_idx:02d}"
        else:
            mesh_name = f"NOD_Mesh_{group_idx:02d}"

        mesh, obj = add_mesh(mesh_name, vertices, faces, normals, collection=collection)
        obj["nod_group_index"] = int(group_idx)
        obj["nod_mesh_name"] = mesh_name
        obj["nod_group_flags"] = int(groupMesh.group_flags)
        obj["nod_group_bone_num"] = int(groupMesh.bone_num)
        weighted_meshes.append((
            obj,
            nodFile.vertices[vertPosition - groupMesh.num_vertices:vertPosition],
            groupMesh,
        ))

        add_uv(mesh, uv)

        if groupMesh.material_id < 0 or groupMesh.material_id >= len(nodFile.header.material_names):
            print(f"WARNING: mesh '{mesh_name}' has invalid material_id {groupMesh.material_id}, using NOD_Missing")
            mat_key = "NOD_Missing"
            if mat_key not in materials_by_source_name:
                materials_by_source_name[mat_key] = create_material(mat_key, "", dir_cache=dir_cache)
            material = materials_by_source_name[mat_key]
        else:
            raw_mat_name = nodFile.header.material_names[groupMesh.material_id]
            clean_mat_name = raw_mat_name.split("\x00", 1)[0]
            if not clean_mat_name:
                clean_mat_name = f"NOD_Material_{groupMesh.material_id:02d}"

            if clean_mat_name not in materials_by_source_name:
                materials_by_source_name[clean_mat_name] = create_material(
                    clean_mat_name,
                    settings.textures_dir_path,
                    dir_cache=dir_cache,
                )
            material = materials_by_source_name[clean_mat_name]

        mesh.materials.append(material)

    armature_obj = None
    if settings.load_bones:
        armature_obj = create_blender_skeleton_from_nod_with_mesh(
            nodFile.vertices,
            nodFile.bones,
            collection=collection,
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
