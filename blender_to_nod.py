import math
import re
from collections import defaultdict

import bpy
from mathutils import Matrix, Vector

from .debug_logging import debug_print, set_debug_logging
from .export_settings import ExportSettings
from .nod_bone import NodBone
from .nod_face import NodFace
from .nod_file import NodFile
from .nod_math import matrix_to_nod_rest_matrix_inverse, nod_bind_world_matrix
from .nod_mesh_group import NodMeshGroup
from .nod_skinning import (
    NOD_GROUP_KNOWN_FLAGS,
    NOD_GROUP_NOSKINNING,
    NOD_GROUP_NOWEIGHTS,
)
from .nod_vertex import NodVertex
from .vector2 import Vector2
from .vector3 import Vector3
from .vector4 import Vector4

MAX_NOD_BONES = 64
MAX_GROUP_VERTICES = 65535
MAX_GROUP_FACES = 65535

_BLENDER_SUFFIX_RE = re.compile(r"\.\d{3,}$")
_BONE_INDEX_RE = re.compile(r"^Bone_(\d+)$")


def _strip_blender_suffix(name: str) -> str:
    if not name:
        return ""
    return _BLENDER_SUFFIX_RE.sub("", name)


def _find_armature_for_mesh(mesh_obj):
    if mesh_obj.parent is not None and mesh_obj.parent.type == 'ARMATURE':
        return mesh_obj.parent
    for mod in mesh_obj.modifiers:
        if mod.type == 'ARMATURE' and mod.object is not None:
            return mod.object
    return None


def collect_export_targets(context, settings: ExportSettings):
    """Find the target armature (if any) and mesh objects to export."""
    scene = getattr(context, "scene", None)
    scene_objects = list(scene.objects) if scene is not None else list(bpy.data.objects)
    selected_objects = list(getattr(context, "selected_objects", []) or [])

    view_layer_objs = getattr(getattr(context, "view_layer", None), "objects", None)
    active_obj = getattr(view_layer_objs, "active", None) or getattr(context, "active_object", None)

    armature_obj = None
    mesh_objects = []

    if settings.selected_only and selected_objects:
        selected_armatures = [o for o in selected_objects if o.type == 'ARMATURE']
        selected_meshes = [o for o in selected_objects if o.type == 'MESH']
        if selected_armatures:
            armature_obj = selected_armatures[0]
        elif selected_meshes:
            for m in selected_meshes:
                arm = _find_armature_for_mesh(m)
                if arm is not None:
                    armature_obj = arm
                    break

        if selected_meshes:
            mesh_objects = selected_meshes
        elif armature_obj is not None:
            mesh_objects = [
                o for o in scene_objects
                if o.type == 'MESH' and _find_armature_for_mesh(o) == armature_obj
            ]
    else:
        # Automatic detection from active/selected/scene
        if active_obj is not None:
            if active_obj.type == 'ARMATURE':
                armature_obj = active_obj
            elif active_obj.type == 'MESH':
                armature_obj = _find_armature_for_mesh(active_obj)

        if armature_obj is None:
            for o in selected_objects:
                if o.type == 'ARMATURE':
                    armature_obj = o
                    break
                if o.type == 'MESH':
                    arm = _find_armature_for_mesh(o)
                    if arm is not None:
                        armature_obj = arm
                        break

        if armature_obj is None:
            scene_armatures = [o for o in scene_objects if o.type == 'ARMATURE']
            if len(scene_armatures) == 1:
                armature_obj = scene_armatures[0]

        if armature_obj is not None:
            mesh_objects = [
                o for o in scene_objects
                if o.type == 'MESH' and _find_armature_for_mesh(o) == armature_obj
            ]

        if not mesh_objects:
            all_meshes = [o for o in scene_objects if o.type == 'MESH']
            non_cube = [o for o in all_meshes if o.name != "Cube"]
            mesh_objects = non_cube if non_cube else all_meshes

    if not mesh_objects:
        raise ValueError("No mesh objects found to export")

    def _mesh_sort_key(obj):
        grp_idx = obj.get("nod_group_index")
        if grp_idx is not None:
            return (0, int(grp_idx), obj.name)
        return (1, 0, obj.name)

    mesh_objects = sorted(mesh_objects, key=_mesh_sort_key)
    return armature_obj, mesh_objects


def _order_blender_bones(armature_obj):
    bones = list(armature_obj.data.bones)
    if not bones:
        return []

    # Check if bones follow standard Bone_000 .. Bone_{N-1:03d} naming
    indexed = {}
    all_standard = True
    for b in bones:
        m = _BONE_INDEX_RE.match(b.name)
        if m:
            idx = int(m.group(1))
            indexed[idx] = b
        else:
            all_standard = False
            break

    if all_standard and set(indexed.keys()) == set(range(len(bones))):
        return [indexed[i] for i in range(len(bones))]

    # Otherwise topological pre-order traversal starting from roots
    ordered = []
    visited = set()

    def _visit(b):
        if b.name in visited:
            return
        visited.add(b.name)
        ordered.append(b)
        for child in b.children:
            _visit(child)

    roots = [b for b in bones if b.parent is None]
    for r in roots:
        _visit(r)
    for b in bones:
        _visit(b)
    return ordered


def _export_bones(armature_obj, settings: ExportSettings):
    if not settings.export_bones or armature_obj is None:
        return [], {}

    ordered_bones = _order_blender_bones(armature_obj)
    bone_count = len(ordered_bones)
    if bone_count == 0:
        return [], {}
    if bone_count > MAX_NOD_BONES:
        raise ValueError(
            f"NOD format supports at most {MAX_NOD_BONES} bones, "
            f"but armature '{armature_obj.name}' has {bone_count}"
        )

    bone_name_to_index = {b.name: i for i, b in enumerate(ordered_bones)}
    nod_bones = [NodBone() for _ in range(bone_count)]
    children_by_parent = defaultdict(list)

    for i, b in enumerate(ordered_bones):
        if "nod_parent_id" in b and settings.preserve_imported_bind_pose:
            p_id = int(b["nod_parent_id"])
            if not (0 <= p_id < bone_count and p_id != i):
                p_id = -1
        elif b.parent is not None and b.parent.name in bone_name_to_index:
            p_id = bone_name_to_index[b.parent.name]
        else:
            p_id = -1

        nod_bones[i].parent_id = p_id
        nod_bones[i].child_id = -1
        nod_bones[i].sibling_id = -1
        if p_id >= 0:
            children_by_parent[p_id].append(i)

    for p_id, child_indices in children_by_parent.items():
        if not child_indices:
            continue
        nod_bones[p_id].child_id = child_indices[0]
        for idx_pos in range(len(child_indices) - 1):
            curr_c = child_indices[idx_pos]
            next_c = child_indices[idx_pos + 1]
            nod_bones[curr_c].sibling_id = next_c
        nod_bones[child_indices[-1]].sibling_id = -1

    arm_world = armature_obj.matrix_world.copy()
    world_bind_matrices = []

    for i, b in enumerate(ordered_bones):
        nb = nod_bones[i]
        raw_inv = b.get("nod_rest_matrix_inverse") if settings.preserve_imported_bind_pose else None
        if raw_inv is not None and len(raw_inv) == 12:
            vals = [float(x) for x in raw_inv]
            nb.rest_matrix_inverse = [
                Vector4(vals[0], vals[1], vals[2], vals[3]),
                Vector4(vals[4], vals[5], vals[6], vals[7]),
                Vector4(vals[8], vals[9], vals[10], vals[11]),
            ]
            world_bind_matrices.append(nod_bind_world_matrix(nb))
        else:
            bw = arm_world @ b.matrix_local
            world_bind_matrices.append(bw)
            inv_bw = bw.inverted_safe()
            nb.rest_matrix_inverse = matrix_to_nod_rest_matrix_inverse(inv_bw)

    for i, b in enumerate(ordered_bones):
        nb = nod_bones[i]
        raw_trans = b.get("nod_rest_translate") if settings.preserve_imported_bind_pose else None
        if raw_trans is not None and len(raw_trans) == 3:
            nb.rest_translate = Vector3(float(raw_trans[0]), float(raw_trans[1]), float(raw_trans[2]))
        else:
            p_id = nb.parent_id
            if 0 <= p_id < bone_count:
                local_mat = world_bind_matrices[p_id].inverted_safe() @ world_bind_matrices[i]
            else:
                local_mat = world_bind_matrices[i]
            t = local_mat.to_translation()
            nb.rest_translate = Vector3(float(t.x), float(t.y), float(t.z))

    return nod_bones, bone_name_to_index


def _resolve_vertex_skinning(vertex, vgroup_idx_to_bone_idx, nod_bones):
    """Map Blender vertex group weights on one vertex to NOD's (bone_number, weight)."""
    num_bones = len(nod_bones)
    if num_bones == 0:
        return -1, 1.0

    influences = {}
    for g in vertex.groups:
        bone_idx = vgroup_idx_to_bone_idx.get(g.group)
        if bone_idx is not None and 0 <= bone_idx < num_bones and g.weight > 1e-6:
            influences[bone_idx] = influences.get(bone_idx, 0.0) + float(g.weight)

    if not influences:
        return 0, 1.0

    if len(influences) == 1:
        only_bone = next(iter(influences.keys()))
        return only_bone, 1.0

    # Check for child-parent bone pairs (NOD soft-skinning convention)
    best_pair = None
    best_pair_sum = -1.0
    for b_idx, w_child in influences.items():
        parent_idx = nod_bones[b_idx].parent_id
        if parent_idx in influences and parent_idx != b_idx:
            w_parent = influences[parent_idx]
            pair_sum = w_child + w_parent
            if pair_sum > best_pair_sum:
                best_pair_sum = pair_sum
                best_pair = (b_idx, w_child, pair_sum)

    if best_pair is not None and best_pair[2] > 1e-6:
        b_idx, w_child, pair_sum = best_pair
        normalized_w = max(0.0, min(1.0, w_child / pair_sum))
        return b_idx, normalized_w

    # Fallback: pick single highest-weight bone
    dominant_bone = max(influences.items(), key=lambda kv: kv[1])[0]
    return dominant_bone, 1.0


def build_nod_from_blender(
    context,
    settings: ExportSettings = None,
    armature_obj=None,
    mesh_objects=None,
) -> NodFile:
    """Build a complete NodFile structure from Blender armature and mesh objects."""
    if settings is None:
        settings = ExportSettings()

    set_debug_logging(settings.debug_log)

    if armature_obj is None and mesh_objects is None:
        armature_obj, mesh_objects = collect_export_targets(context, settings)
    elif mesh_objects is None:
        scene = getattr(context, "scene", None)
        scene_objects = list(scene.objects) if scene is not None else list(bpy.data.objects)
        mesh_objects = [
            o for o in scene_objects
            if o.type == 'MESH' and _find_armature_for_mesh(o) == armature_obj
        ]

    nod = NodFile()
    nod.header.version = int(settings.model_version)

    nod_bones, bone_name_to_index = _export_bones(armature_obj, settings)
    nod.bones = nod_bones

    material_name_to_id = {}
    mesh_name_to_id = {}

    def _get_or_add_material_id(mat) -> int:
        if mat is None:
            return -1
        src_name = mat.get("nod_source_name") or _strip_blender_suffix(mat.name)
        src_name = (src_name or "").split("\x00", 1)[0].strip()
        if not src_name or src_name == "NOD_Missing":
            return -1
        if src_name not in material_name_to_id:
            material_name_to_id[src_name] = len(nod.header.material_names)
            nod.header.material_names.append(src_name)
        return material_name_to_id[src_name]

    def _get_or_add_mesh_id(mesh_obj) -> int:
        raw_name = mesh_obj.get("nod_mesh_name") or _strip_blender_suffix(mesh_obj.name)
        clean_name = (raw_name or "mesh").split("\x00", 1)[0].strip() or "mesh"
        if clean_name not in mesh_name_to_id:
            mesh_name_to_id[clean_name] = len(nod.mesh_names)
            nod.mesh_names.append(clean_name)
        return mesh_name_to_id[clean_name]

    for mesh_obj in mesh_objects:
        mesh = mesh_obj.data
        mesh.calc_loop_triangles()
        loop_triangles = mesh.loop_triangles
        if len(mesh.vertices) == 0:
            continue

        mesh_num = _get_or_add_mesh_id(mesh_obj)
        world_mat = mesh_obj.matrix_world.copy()
        normal_mat = world_mat.to_3x3().inverted_safe().transposed()
        is_identity_xform = all(
            abs(world_mat[r][c] - (1.0 if r == c else 0.0)) < 1e-6
            for r in range(4)
            for c in range(4)
        )

        # Map vertex group indices to bone indices
        vgroup_idx_to_bone_idx = {}
        for vg in mesh_obj.vertex_groups:
            if vg.name in bone_name_to_index:
                vgroup_idx_to_bone_idx[vg.index] = bone_name_to_index[vg.name]
            else:
                m = _BONE_INDEX_RE.match(vg.name)
                if m:
                    b_idx = int(m.group(1))
                    if 0 <= b_idx < len(nod_bones):
                        vgroup_idx_to_bone_idx[vg.index] = b_idx

        # Precompute per-vertex position and skinning
        vert_positions = []
        vert_skinning = []
        for v in mesh.vertices:
            pos = v.co if is_identity_xform else (world_mat @ v.co)
            vert_positions.append((float(pos.x), float(pos.y), float(pos.z)))
            vert_skinning.append(
                _resolve_vertex_skinning(v, vgroup_idx_to_bone_idx, nod_bones)
            )

        # Read loop UVs
        uv_layer = mesh.uv_layers.active or (mesh.uv_layers[0] if len(mesh.uv_layers) > 0 else None)
        num_loops = len(mesh.loops)
        if uv_layer is not None and num_loops > 0:
            flat_uvs = [0.0] * (num_loops * 2)
            uv_layer.data.foreach_get("uv", flat_uvs)
            loop_uvs = [
                (flat_uvs[i * 2], flat_uvs[i * 2 + 1])
                for i in range(num_loops)
            ]
        else:
            loop_uvs = [(0.0, 0.0)] * num_loops

        # Read loop corner normals
        if hasattr(mesh, "corner_normals") and len(mesh.corner_normals) == num_loops and num_loops > 0:
            flat_normals = [0.0] * (num_loops * 3)
            mesh.corner_normals.foreach_get("vector", flat_normals)
            loop_normals = []
            for i in range(num_loops):
                nx, ny, nz = flat_normals[i * 3], flat_normals[i * 3 + 1], flat_normals[i * 3 + 2]
                if not is_identity_xform:
                    n_vec = (normal_mat @ Vector((nx, ny, nz))).normalized()
                    nx, ny, nz = float(n_vec.x), float(n_vec.y), float(n_vec.z)
                loop_normals.append((nx, ny, nz))
        else:
            loop_normals = []
            for loop in mesh.loops:
                n_vec = mesh.vertices[loop.vertex_index].normal
                if not is_identity_xform:
                    n_vec = (normal_mat @ n_vec).normalized()
                loop_normals.append((float(n_vec.x), float(n_vec.y), float(n_vec.z)))

        # Group triangles by material_index
        tris_by_mat = defaultdict(list)
        for tri in loop_triangles:
            tris_by_mat[tri.material_index].append(tri)
        if not tris_by_mat:
            tris_by_mat[0] = []

        single_mat_group = len(tris_by_mat) == 1

        for mat_slot_idx in sorted(tris_by_mat.keys()):
            tris = tris_by_mat[mat_slot_idx]
            mat = (
                mesh.materials[mat_slot_idx]
                if 0 <= mat_slot_idx < len(mesh.materials)
                else None
            )
            material_id = _get_or_add_material_id(mat)

            group_verts = []
            group_faces = []
            candidates_by_vert = defaultdict(list)

            def _find_or_create_local_vert(v_idx, uv_val, norm_val):
                for local_idx, c_uv, c_norm in candidates_by_vert[v_idx]:
                    if (
                        abs(uv_val[0] - c_uv[0]) <= 1e-4
                        and abs(uv_val[1] - c_uv[1]) <= 1e-4
                        and abs(norm_val[0] - c_norm[0]) <= 1e-3
                        and abs(norm_val[1] - c_norm[1]) <= 1e-3
                        and abs(norm_val[2] - c_norm[2]) <= 1e-3
                    ):
                        return local_idx

                nv = NodVertex()
                px, py, pz = vert_positions[v_idx]
                nv.position = Vector3(px, py, pz)
                nv.normal = Vector3(norm_val[0], norm_val[1], norm_val[2])
                nv.uv = Vector2(uv_val[0], uv_val[1])
                b_num, w_val = vert_skinning[v_idx]
                nv.bone_number = b_num
                nv.weight = w_val

                local_idx = len(group_verts)
                group_verts.append(nv)
                candidates_by_vert[v_idx].append((local_idx, uv_val, norm_val))
                return local_idx

            if single_mat_group:
                # Seed all mesh vertices in original index order for 1:1 round-trip
                first_loop_for_vert = {}
                for tri in tris:
                    for v_idx, l_idx in zip(tri.vertices, tri.loops):
                        if v_idx not in first_loop_for_vert:
                            first_loop_for_vert[v_idx] = l_idx

                for v_idx in range(len(mesh.vertices)):
                    l_idx = first_loop_for_vert.get(v_idx)
                    if l_idx is not None:
                        uv_val = loop_uvs[l_idx]
                        norm_val = loop_normals[l_idx]
                    else:
                        uv_val = (0.0, 0.0)
                        n_v = mesh.vertices[v_idx].normal
                        norm_val = (float(n_v.x), float(n_v.y), float(n_v.z))
                    _find_or_create_local_vert(v_idx, uv_val, norm_val)

            for tri in tris:
                face_indices = [
                    _find_or_create_local_vert(v_idx, loop_uvs[l_idx], loop_normals[l_idx])
                    for v_idx, l_idx in zip(tri.vertices, tri.loops)
                ]
                group_faces.append(NodFace(x=face_indices[0], y=face_indices[1], z=face_indices[2]))

            if len(group_verts) > MAX_GROUP_VERTICES:
                raise ValueError(
                    f"Mesh group '{mesh_obj.name}' has {len(group_verts)} vertices "
                    f"(maximum per NOD group is {MAX_GROUP_VERTICES})"
                )
            if len(group_faces) > MAX_GROUP_FACES:
                raise ValueError(
                    f"Mesh group '{mesh_obj.name}' has {len(group_faces)} faces "
                    f"(maximum per NOD group is {MAX_GROUP_FACES})"
                )

            grp = NodMeshGroup()
            grp.material_id = material_id
            grp.num_faces = len(group_faces)
            grp.num_vertices = len(group_verts)
            grp.min_vertices = len(group_verts)
            grp.mesh_num = mesh_num

            stored_flags = mesh_obj.get("nod_group_flags")
            stored_bone = mesh_obj.get("nod_group_bone_num")
            if len(nod_bones) == 0:
                grp.group_flags = NOD_GROUP_NOSKINNING
                grp.bone_num = 0
            elif stored_flags is not None and (int(stored_flags) & ~NOD_GROUP_KNOWN_FLAGS) == 0:
                grp.group_flags = int(stored_flags)
                grp.bone_num = int(stored_bone) if stored_bone is not None else 0
                if grp.group_flags & NOD_GROUP_NOSKINNING:
                    for gv in group_verts:
                        gv.bone_number = grp.bone_num
                        gv.weight = 1.0
            else:
                has_soft = any(gv.weight < 1.0 - 1e-5 for gv in group_verts)
                grp.group_flags = 0 if has_soft else NOD_GROUP_NOWEIGHTS
                grp.bone_num = int(stored_bone) if stored_bone is not None else 0

            nod.vertices.extend(group_verts)
            nod.faces.extend(group_faces)
            nod.mesh_groups.append(grp)

    # Calculate header bounds and flags
    if nod.vertices:
        xs = [v.position.x for v in nod.vertices]
        ys = [v.position.y for v in nod.vertices]
        zs = [v.position.z for v in nod.vertices]
        nod.header.bounds = (
            min(xs), min(ys), min(zs),
            max(xs), max(ys), max(zs),
        )
    else:
        nod.header.bounds = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    nod.header.model_flags = 0x4 if len(nod.bones) == 0 else 0x0
    nod.header._sync_flags()

    debug_print(
        f"Built NOD model: {len(nod.bones)} bones, {len(nod.mesh_groups)} mesh groups, "
        f"{len(nod.vertices)} vertices, {len(nod.faces)} faces, "
        f"{len(nod.header.material_names)} materials"
    )
    return nod


def export_nod_file(filepath: str, context, settings: ExportSettings = None,
                    armature_obj=None, mesh_objects=None) -> NodFile:
    nod_file = build_nod_from_blender(
        context, settings=settings, armature_obj=armature_obj, mesh_objects=mesh_objects
    )
    raw_bytes = nod_file.to_bytes()
    with open(filepath, "wb") as out_file:
        out_file.write(raw_bytes)
    return nod_file
