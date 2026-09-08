import bpy
from mathutils import Vector, Matrix
import mathutils
from .debug_logging import debug_print

NOD_GROUP_NOWEIGHTS = 0x2
NOD_GROUP_NOSKINNING = 0x4
NOD_GROUP_KNOWN_FLAGS = 0xF

def convert_to_mathutils_vector(v):
    return mathutils.Vector((v.x, v.y, v.z))

def get_nod_bone_world_rest_position(nod_bone):
    """Recover only the world-space position from NOD's inverse bind matrix.

    The 12 serialized floats form a row-vector Matrix43: three inverse
    rotation rows followed by the inverse translation. For a rigid transform,
    the forward translation is ``-R_inv * T_inv``. Deliberately do not return
    or apply its rotation: the existing Blender bone orientation logic must
    remain unchanged.
    """
    matrix_rows = nod_bone.rest_matrix_inverse
    values = []
    for row in matrix_rows:
        values.extend((row.x, row.y, row.z, row.w))

    inverse_rotation = (
        values[0:3],
        values[3:6],
        values[6:9],
    )
    inverse_translation = values[9:12]
    return Vector(tuple(
        -sum(inverse_translation[column] * inverse_rotation[row][column]
             for column in range(3))
        for row in range(3)
    ))

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

    vertex_groups = {}
    assigned_vertices = set()

    # Some shipped NOD files contain the MSVC debug-fill pattern (0xCDCD,
    # 0xCDCE, 0xCDCF) in GroupFlags. Those values are uninitialised data, not
    # real flags. In particular, blindly testing bit 0x4 incorrectly makes the
    # whole mesh rigidly bound to group bone 0.
    flags_are_valid = (group_flags & ~NOD_GROUP_KNOWN_FLAGS) == 0
    effective_flags = group_flags if flags_are_valid else 0
    if not flags_are_valid:
        print(f"WARNING: mesh '{mesh_obj.name}' has invalid/uninitialised NOD "
              f"group flags 0x{group_flags:04X}; using per-vertex skinning")

    def add_weight(vertex_index, bone_index, weight):
        if not (0 <= bone_index < bone_count) or weight <= 0.0:
            return
        group = vertex_groups.get(bone_index)
        if group is None:
            group = mesh_obj.vertex_groups.get(f"Bone_{bone_index:03d}")
            if group is None:
                group = mesh_obj.vertex_groups.new(name=f"Bone_{bone_index:03d}")
            vertex_groups[bone_index] = group
        group.add([vertex_index], min(1.0, float(weight)), 'REPLACE')
        assigned_vertices.add(vertex_index)

    if effective_flags & NOD_GROUP_NOSKINNING:
        if 0 <= group_bone_num < bone_count:
            for vertex_index in range(vertex_count):
                add_weight(vertex_index, group_bone_num, 1.0)
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
                add_weight(vertex_index, bone_index, 1.0)
                continue

            add_weight(vertex_index, bone_index, weight)
            parent_index = nod_bones[bone_index].parent_id
            if 0 <= parent_index < bone_count:
                add_weight(vertex_index, parent_index, 1.0 - weight)
            else:
                # A root bone has no parent, so keep the vertex fully bound.
                add_weight(vertex_index, bone_index, 1.0)

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

    for bone in armature_obj.data.bones:
        bone.use_deform = True
    armature_obj.data.pose_position = 'POSE'

    mesh_obj.data.update()
    bpy.context.view_layer.update()

    group_names = ", ".join(
        f"Bone_{bone_index:03d}" for bone_index in sorted(vertex_groups)
    ) or "none"
    debug_print(f"Attached mesh '{mesh_obj.name}' to '{armature_obj.name}': "
          f"flags=0x{group_flags:04X}, group_bone={group_bone_num}, "
          f"groups=[{group_names}], weighted "
          f"{len(assigned_vertices)}/{vertex_count} vertices")
    return modifier

def create_blender_skeleton_from_nod_with_mesh(
        nod_vertices, nod_bones, armature_name="NOD_Armature",
        use_bind_pose_positions=False):
    """
    Convert NOD bone structure to Blender armature.
    
    Args:
        nod_vertices: List of NodVertex objects
        nod_bones: List of NodBone objects
        armature_name: Name for the created armature
    
    Returns:
        bpy.types.Object: The created armature object
    """
    
    # Clear existing armatures if any
    bpy.ops.object.select_all(action='DESELECT')
    
    # FIRST: Calculate bone positions. Bind positions provide the actual joint
    # pivots; the legacy mode retains weighted vertex centroids for comparison.
    position_mode = ("NOD BIND POSE" if use_bind_pose_positions
                     else "VERTEX WEIGHT CENTROIDS")
    debug_print(f"=== CALCULATING BONE POSITIONS: {position_mode} ===")
    bone_positions = {}
    for i in range(len(nod_bones)):
        bone_positions[i] = {"position": mathutils.Vector((0, 0, 0)), "weight": 0}
    
    for vertex in nod_vertices:
        bone_index = vertex.bone_number
        weight = vertex.weight
        vertex_position = convert_to_mathutils_vector(vertex.position)
        
        # Accumulate weighted position for the bone
        bone_positions[bone_index]["position"] += vertex_position * weight
        bone_positions[bone_index]["weight"] += weight
        
        # If weight < 1.0, distribute to parent bone
        if weight < 1.0 and bone_index < len(nod_bones):
            nod_bone = nod_bones[bone_index]
            parent_bone_index = nod_bone.parent_id
            
            if parent_bone_index >= 0 and parent_bone_index < len(nod_bones):
                bone_positions[parent_bone_index]["position"] += vertex_position * (1 - weight)
                bone_positions[parent_bone_index]["weight"] += (1 - weight)
    
    # Calculate average positions for each bone
    bone_avg_positions = {}
    for bone_index, data in bone_positions.items():
        if use_bind_pose_positions:
            bone_avg_positions[bone_index] = get_nod_bone_world_rest_position(
                nod_bones[bone_index]
            )
            debug_print(f"Bone {bone_index}: absolute bind position = "
                  f"{bone_avg_positions[bone_index]}")
        elif data["weight"] > 0:
            bone_avg_positions[bone_index] = data["position"] / data["weight"]
            debug_print(f"Bone {bone_index}: avg position from vertices = {bone_avg_positions[bone_index]}")
        else:
            # RestTranslate is local to the parent and cannot be used directly
            # as a Blender edit-bone head. For bones without any influences,
            # recover only their absolute bind position from RestMatrixInverse.
            nod_bone = nod_bones[bone_index]
            bone_avg_positions[bone_index] = get_nod_bone_world_rest_position(
                nod_bone
            )
            debug_print(f"Bone {bone_index}: no vertices, using absolute bind "
                  f"position = {bone_avg_positions[bone_index]}")
    
    # Create new armature
    armature = bpy.data.armatures.new(armature_name)
    armature_obj = bpy.data.objects.new(armature_name, armature)
    
    # Link to scene
    bpy.context.collection.objects.link(armature_obj)
    
    # Set as active object and enter edit mode
    bpy.context.view_layer.objects.active = armature_obj
    bpy.ops.object.mode_set(mode='EDIT')
    
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
        bone.tail = bone.head + Vector((0, 0, 0.1))
        
        debug_print(f"Created bone {i}: {bone.name} at position {bone.head}")
    
    # Set up parent relationships
    debug_print("\n=== SETTING UP PARENTS ===")
    for i, nod_bone in enumerate(nod_bones):
        bone = bone_dict[i]
        
        if nod_bone.parent_id != -1:
            if nod_bone.parent_id < len(nod_bones):
                parent_bone = bone_dict[nod_bone.parent_id]
                bone.parent = parent_bone
                debug_print(f"Bone {i} -> Parent {nod_bone.parent_id}")
            else:
                print(f"ERROR: Bone {i} has invalid parent_id {nod_bone.parent_id}")
        else:
            debug_print(f"Bone {i} is ROOT bone")
    
    # Fix bone tails based on children
    debug_print("\n=== FIXING BONE TAILS ===")
    for i, nod_bone in enumerate(nod_bones):
        bone = bone_dict[i]
        
        # Collect ALL children by following the sibling chain
        all_children = []
        if nod_bone.child_id != -1 and nod_bone.child_id < len(nod_bones):
            child_idx = nod_bone.child_id
            while child_idx != -1 and child_idx < len(nod_bones):
                all_children.append(child_idx)
                child_nod = nod_bones[child_idx]
                child_idx = child_nod.sibling_id
        
        if all_children:
            # Point to first child
            first_child = bone_dict[all_children[0]]
            direction = first_child.head - bone.head
            if direction.length > 0.001:
                bone.tail = first_child.head
                debug_print(f"Bone {i} tail -> first child {all_children[0]} (all children: {all_children})")
            else:
                bone.tail = bone.head + Vector((0, 0, 0.1))
                debug_print(f"Bone {i} and child at same position, using default tail")
        else:
            # No children - use reasonable tail
            if bone.parent:
                # Use parent direction but shorter
                parent_dir = bone.head - bone.parent.head
                if parent_dir.length > 0.001:
                    bone.tail = bone.head + parent_dir.normalized() * (parent_dir.length * 0.3)
                else:
                    bone.tail = bone.head + Vector((0, 0, 0.1))
            else:
                bone.tail = bone.head + Vector((0, 0, 0.1))
            debug_print(f"Bone {i} is leaf bone")

    # Return to object mode
    bpy.ops.object.mode_set(mode='OBJECT')
    
    debug_print("\n=== ARMATURE CREATED ===")
    debug_print(f"Armature '{armature_name}' created with {len(nod_bones)} bones")
    
    return armature_obj
