from collections import defaultdict
import bpy
from mathutils import Vector
from .nod_math import nod_bind_world_position
from .debug_logging import debug_print

NOD_GROUP_NOWEIGHTS = 0x2
NOD_GROUP_NOSKINNING = 0x4
NOD_GROUP_KNOWN_FLAGS = 0xF

def convert_to_mathutils_vector(v):
    return Vector((v.x, v.y, v.z))

def get_nod_bone_world_rest_position(nod_bone):
    """Recover the world-space rest position from NOD's inverse bind matrix."""
    return nod_bind_world_position(nod_bone)


def attach_nod_mesh_to_armature(mesh_obj, nod_vertices, nod_bones, armature_obj,
                                group_flags=0, group_bone_num=0):
    """Create NOD skin weights and an Armature modifier on one mesh group.

    NOD stores at most two influences per vertex. ``bone_number`` is the first
    bone and, for soft-skinned vertices, the second bone is its parent.
    ``NOSKINNING`` overrides per-vertex bindings with the mesh-group bone.
    """
    if mesh_obj is None or mesh_obj.type != 'MESH':
        raise ValueError("A Blender mesh object is required")

    bone_count = len(nod_bones)
    vertex_count = len(mesh_obj.data.vertices)
    if len(nod_vertices) != vertex_count:
        raise ValueError(
            f"NOD vertex count ({len(nod_vertices)}) does not match Blender "
            f"mesh vertex count ({vertex_count})"
        )

    # Some shipped NOD files contain the MSVC debug-fill pattern (0xCDCD,
    # 0xCDCE, 0xCDCF) in GroupFlags. Those values are uninitialised data, not
    # real flags. In particular, blindly testing bit 0x4 incorrectly makes the
    # whole mesh rigidly bound to group bone 0.
    flags_are_valid = (group_flags & ~NOD_GROUP_KNOWN_FLAGS) == 0
    effective_flags = group_flags if flags_are_valid else 0
    if not flags_are_valid:
        debug_print(f"WARNING: mesh '{mesh_obj.name}' has invalid/uninitialised NOD "
                    f"group flags 0x{group_flags:04X}; using per-vertex skinning")

    batch_weights = defaultdict(list)
    assigned_vertices = set()

    if effective_flags & NOD_GROUP_NOSKINNING:
        if 0 <= group_bone_num < bone_count:
            all_verts = list(range(vertex_count))
            batch_weights[(group_bone_num, 1.0)].extend(all_verts)
            assigned_vertices.update(all_verts)
        else:
            print(f"WARNING: mesh '{mesh_obj.name}' has invalid group bone "
                  f"index {group_bone_num}")
    else:
        has_soft_weights = not (effective_flags & NOD_GROUP_NOWEIGHTS)
        for vertex_index, nod_vertex in enumerate(nod_vertices):
            bone_index = nod_vertex.bone_number
            if not (0 <= bone_index < bone_count):
                print(f"WARNING: mesh '{mesh_obj.name}', vertex {vertex_index} "
                      f"has invalid bone index {bone_index}")
                continue

            weight = max(0.0, min(1.0, float(nod_vertex.weight)))
            if not has_soft_weights or weight >= 1.0:
                batch_weights[(bone_index, 1.0)].append(vertex_index)
                assigned_vertices.add(vertex_index)
                continue

            parent_index = nod_bones[bone_index].parent_id
            if 0 <= parent_index < bone_count and parent_index != bone_index:
                if weight > 0.0:
                    batch_weights[(bone_index, weight)].append(vertex_index)
                    assigned_vertices.add(vertex_index)
                parent_weight = 1.0 - weight
                if parent_weight > 0.0:
                    batch_weights[(parent_index, parent_weight)].append(vertex_index)
                    assigned_vertices.add(vertex_index)
            else:
                # A root bone has no parent, so keep the vertex fully bound.
                batch_weights[(bone_index, 1.0)].append(vertex_index)
                assigned_vertices.add(vertex_index)

    vertex_groups = {}
    for (bone_index, weight), indices in batch_weights.items():
        if not indices or weight <= 0.0:
            continue
        group = vertex_groups.get(bone_index)
        if group is None:
            group_name = f"Bone_{bone_index:03d}"
            group = mesh_obj.vertex_groups.get(group_name)
            if group is None:
                group = mesh_obj.vertex_groups.new(name=group_name)
            vertex_groups[bone_index] = group
        group.add(indices, min(1.0, float(weight)), 'REPLACE')

    # A valid deform setup needs both matching vertex groups and an Armature
    # modifier. Parenting also makes the meshes follow object-level movement of
    # the armature, just like Blender's "Armature Deform" operation.
    modifier = mesh_obj.modifiers.get("NOD Armature")
    if modifier is None or modifier.type != 'ARMATURE':
        modifier = mesh_obj.modifiers.new(name="NOD Armature", type='ARMATURE')
    modifier.object = armature_obj
    modifier.use_vertex_groups = True
    modifier.show_viewport = True
    modifier.show_render = True

    world_matrix = mesh_obj.matrix_world.copy()
    mesh_obj.parent = armature_obj
    mesh_obj.matrix_world = world_matrix

    group_names = ", ".join(
        f"Bone_{bone_index:03d}" for bone_index in sorted(vertex_groups)
    ) or "none"
    debug_print(f"Attached mesh '{mesh_obj.name}' to '{armature_obj.name}': "
          f"flags=0x{group_flags:04X}, group_bone={group_bone_num}, "
          f"groups=[{group_names}], weighted "
          f"{len(assigned_vertices)}/{vertex_count} vertices")
    return modifier

def get_nod_bone_children(nod_bones, bone_index):
    """Collect all direct children indices of nod_bones[bone_index] using child_id and sibling_id.

    Guards against invalid indices and circular sibling chains.
    """
    children = []
    n = len(nod_bones)
    if not (0 <= bone_index < n):
        return children

    child_idx = nod_bones[bone_index].child_id
    visited = set()
    while 0 <= child_idx < n and child_idx not in visited:
        visited.add(child_idx)
        children.append(child_idx)
        child_idx = nod_bones[child_idx].sibling_id
    return children

def create_blender_skeleton_from_nod_with_mesh(
        nod_vertices, nod_bones, armature_name="NOD_Armature",
        collection=None):
    """
    Convert NOD bone structure to Blender armature.
    
    Args:
        nod_vertices: List of NodVertex objects
        nod_bones: List of NodBone objects
        armature_name: Name for the created armature
        collection: Target collection (defaults to bpy.context.collection)
    
    Returns:
        bpy.types.Object: The created armature object
    """
    
    # Ensure active object is in OBJECT mode
    active_obj = bpy.context.view_layer.objects.active
    if active_obj is not None and active_obj.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    # Deselect all objects safely without bpy.ops.object.select_all
    for obj in bpy.context.view_layer.objects.selected:
        obj.select_set(False)
    
    # FIRST: Calculate bone positions from NOD bind pose (RestMatrixInverse).
    debug_print("=== CALCULATING BONE POSITIONS: NOD BIND POSE ===")
    bone_avg_positions = {}
    for bone_index, nod_bone in enumerate(nod_bones):
        bone_avg_positions[bone_index] = get_nod_bone_world_rest_position(
            nod_bone
        )
        debug_print(f"Bone {bone_index}: absolute bind position = "
              f"{bone_avg_positions[bone_index]}")
    
    # Calculate scale-dependent tail parameters from bounding box
    def compute_diagonal(points):
        pts = list(points)
        if not pts:
            return 0.0
        min_x = min(p.x for p in pts)
        max_x = max(p.x for p in pts)
        min_y = min(p.y for p in pts)
        max_y = max(p.y for p in pts)
        min_z = min(p.z for p in pts)
        max_z = max(p.z for p in pts)
        dx = max_x - min_x
        dy = max_y - min_y
        dz = max_z - min_z
        return (dx * dx + dy * dy + dz * dz) ** 0.5

    extent = compute_diagonal(bone_avg_positions.values())
    if extent < 1e-4:
        vert_points = [convert_to_mathutils_vector(v.position) for v in nod_vertices]
        extent = compute_diagonal(vert_points)
    extent = max(extent, 1e-3)
    default_tail = Vector((0.0, 0.0, extent * 0.02))
    threshold = extent * 1e-4

    # Create new armature
    armature = bpy.data.armatures.new(armature_name)
    armature_obj = bpy.data.objects.new(armature_name, armature)
    
    # Link to scene collection
    target_collection = collection if collection is not None else bpy.context.collection
    if target_collection is None and bpy.context.scene is not None:
        target_collection = bpy.context.scene.collection
    if target_collection is not None:
        target_collection.objects.link(armature_obj)
    
    # Set as active object and enter edit mode
    armature_obj.select_set(True)
    bpy.context.view_layer.objects.active = armature_obj
    bpy.ops.object.mode_set(mode='EDIT')
    
    try:
        # Create bones dictionary for easy lookup
        bone_dict = {}
        
        # Create all bones using vertex-calculated positions
        debug_print("\n=== CREATING BONES ===")
        for i, nod_bone in enumerate(nod_bones):
            # Create bone
            bone = armature.edit_bones.new(f"Bone_{i:03d}")
            bone_dict[i] = bone
            
            # Use vertex-calculated position
            bone.head = bone_avg_positions[i]
            
            # Set initial tail (will be corrected later)
            bone.tail = bone.head + default_tail
            
            debug_print(f"Created bone {i}: {bone.name} at position {bone.head}")
        
        # Set up parent relationships
        debug_print("\n=== SETTING UP PARENTS ===")
        for i, nod_bone in enumerate(nod_bones):
            bone = bone_dict[i]
            parent_id = nod_bone.parent_id
            
            if parent_id == -1:
                debug_print(f"Bone {i} is ROOT bone")
                continue

            if not (0 <= parent_id < len(nod_bones) and parent_id != i):
                print(f"WARNING: Bone {i} has invalid parent_id {parent_id}; keeping as root")
                continue

            parent_bone = bone_dict[parent_id]
            curr = parent_bone
            has_cycle = False
            visited_parents = set()
            while curr is not None:
                if curr == bone or curr in visited_parents:
                    has_cycle = True
                    break
                visited_parents.add(curr)
                curr = curr.parent

            if has_cycle:
                print(f"WARNING: Bone {i} parenting to {parent_id} would create a cycle; keeping as root")
                continue

            bone.parent = parent_bone
            debug_print(f"Bone {i} -> Parent {parent_id}")
        
        # Fix bone tails based on children
        debug_print("\n=== FIXING BONE TAILS ===")
        for i, nod_bone in enumerate(nod_bones):
            bone = bone_dict[i]
            all_children = get_nod_bone_children(nod_bones, i)
            
            if all_children:
                # Point to first child
                first_child = bone_dict[all_children[0]]
                direction = first_child.head - bone.head
                if direction.length > threshold:
                    bone.tail = first_child.head
                    debug_print(f"Bone {i} tail -> first child {all_children[0]} (all children: {all_children})")
                else:
                    bone.tail = bone.head + default_tail
                    debug_print(f"Bone {i} and child at same position, using default tail")
            else:
                # No children - use reasonable tail
                if bone.parent:
                    # Use parent direction but shorter
                    parent_dir = bone.head - bone.parent.head
                    if parent_dir.length > threshold:
                        bone.tail = bone.head + parent_dir.normalized() * (parent_dir.length * 0.3)
                    else:
                        bone.tail = bone.head + default_tail
                else:
                    bone.tail = bone.head + default_tail
                debug_print(f"Bone {i} is leaf bone")
    finally:
        if bpy.context.view_layer.objects.active != armature_obj:
            bpy.context.view_layer.objects.active = armature_obj
        if armature_obj.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

    for i, nod_bone in enumerate(nod_bones):
        bone = armature.bones.get(f"Bone_{i:03d}")
        if bone is not None:
            bone.use_deform = True
            bone["nod_parent_id"] = int(nod_bone.parent_id)
            bone["nod_rest_translate"] = [
                float(nod_bone.rest_translate.x),
                float(nod_bone.rest_translate.y),
                float(nod_bone.rest_translate.z),
            ]
            bone["nod_rest_matrix_inverse"] = [
                float(val)
                for row in nod_bone.rest_matrix_inverse
                for val in (row.x, row.y, row.z, row.w)
            ]
    armature.pose_position = 'POSE'

    debug_print("\n=== ARMATURE CREATED ===")
    debug_print(f"Armature '{armature_name}' created with {len(nod_bones)} bones")
    
    return armature_obj
