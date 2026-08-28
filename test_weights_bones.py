import bpy
from mathutils import Vector, Matrix
import mathutils

def convert_to_mathutils_vector(v):
    return mathutils.Vector((v.x, v.y, v.z))

def create_blender_skeleton_from_nod_with_mesh(nod_vertices, nod_bones, armature_name="NOD_Armature"):
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
    
    # FIRST: Calculate bone positions from vertices
    print(f"=== CALCULATING BONE POSITIONS FROM VERTICES ===")
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
        if data["weight"] > 0:
            bone_avg_positions[bone_index] = data["position"] / data["weight"]
            print(f"Bone {bone_index}: avg position from vertices = {bone_avg_positions[bone_index]}")
        else:
            # Fallback to rest_translate if no vertices assigned
            nod_bone = nod_bones[bone_index]
            bone_avg_positions[bone_index] = Vector((nod_bone.rest_translate.x, 
                                                      nod_bone.rest_translate.y, 
                                                      nod_bone.rest_translate.z))
            print(f"Bone {bone_index}: no vertices, using rest_translate = {bone_avg_positions[bone_index]}")
    
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
    print(f"\n=== CREATING BONES ===")
    for i, nod_bone in enumerate(nod_bones):
        # Create bone
        bone = armature.edit_bones.new(f"Bone_{i:03d}")
        bone_dict[i] = bone
        
        # Use vertex-calculated position
        bone.head = bone_avg_positions[i]
        
        # Set initial tail (will be corrected later)
        bone.tail = bone.head + Vector((0, 0, 0.1))
        
        print(f"Created bone {i}: {bone.name} at position {bone.head}")
    
    # Set up parent relationships
    print(f"\n=== SETTING UP PARENTS ===")
    for i, nod_bone in enumerate(nod_bones):
        bone = bone_dict[i]
        
        if nod_bone.parent_id != -1:
            if nod_bone.parent_id < len(nod_bones):
                parent_bone = bone_dict[nod_bone.parent_id]
                bone.parent = parent_bone
                print(f"Bone {i} -> Parent {nod_bone.parent_id}")
            else:
                print(f"ERROR: Bone {i} has invalid parent_id {nod_bone.parent_id}")
        else:
            print(f"Bone {i} is ROOT bone")
    
    # Fix bone tails based on children
    print(f"\n=== FIXING BONE TAILS ===")
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
                print(f"Bone {i} tail -> first child {all_children[0]} (all children: {all_children})")
            else:
                bone.tail = bone.head + Vector((0, 0, 0.1))
                print(f"Bone {i} and child at same position, using default tail")
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
            print(f"Bone {i} is leaf bone")

    # Return to object mode
    bpy.ops.object.mode_set(mode='OBJECT')
    
    print(f"\n=== ARMATURE CREATED ===")
    print(f"Armature '{armature_name}' created with {len(nod_bones)} bones")
    
    return armature_obj