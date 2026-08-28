import bpy
import mathutils
from typing import List

def create_blender_skeleton_from_nod(nod_bones, armature_name="NOD_Armature"):
    """
    Convert NOD bone data to Blender armature
    
    Args:
        nod_bones: List of NodBone objects
        armature_name: Name for the created armature
    
    Returns:
        Created armature object
    """
    # Create new armature
    armature = bpy.data.armatures.new(armature_name)
    armature_obj = bpy.data.objects.new(armature_name, armature)
    bpy.context.collection.objects.link(armature_obj)
    
    # Set as active and enter edit mode
    bpy.context.view_layer.objects.active = armature_obj
    bpy.ops.object.mode_set(mode='EDIT')
    
    # Create bones
    edit_bones = armature.edit_bones
    bone_map = {}  # Map indices to bone objects
    
    # First pass: Create all bones with basic positioning
    for i, nod_bone in enumerate(nod_bones):
        # Create bone
        bone = edit_bones.new(f"Bone_{i:03d}")
        bone_map[i] = bone
        
        # Convert rest_matrix_inverse back to rest matrix
        rest_matrix = _convert_nod_matrix_to_blender(nod_bone.rest_matrix_inverse)
        rest_matrix = rest_matrix.inverted()  # Convert inverse back to forward matrix
        
        # Extract position from the rest matrix translation component
        rest_position = rest_matrix.translation
        
        # Set bone head position
        bone.head = rest_position
        
        # Calculate bone direction from matrix
        # Use the matrix's Y-axis (second column) as bone direction
        bone_direction = rest_matrix.col[1].xyz.normalized()
        bone_length = 0.1  # Default length, can be adjusted
        
        # If we can determine length from children, we'll do that in second pass
        bone.tail = rest_position + bone_direction * bone_length
        
        # Store the rest matrix for potential use
        bone["rest_matrix"] = rest_matrix
    
    # Second pass: Set up hierarchy and adjust bone lengths
    for i, nod_bone in enumerate(nod_bones):
        bone = bone_map[i]
        
        # Set parent relationship
        if nod_bone.parent_id >= 0 and nod_bone.parent_id in bone_map:
            parent_bone = bone_map[nod_bone.parent_id]
            bone.parent = parent_bone
            
            # Adjust parent bone length to reach this child
            direction = (bone.head - parent_bone.head).normalized()
            length = (bone.head - parent_bone.head).length
            if length > 0.001:  # Avoid zero-length bones
                parent_bone.tail = bone.head
            else:
                # If child is at same position, use small default length
                parent_bone.tail = parent_bone.head + direction * 0.05
    
    # Third pass: Handle bones without children (leaf bones)
    for i, nod_bone in enumerate(nod_bones):
        bone = bone_map[i]
        
        # If bone has no children and tail hasn't been adjusted by children
        if nod_bone.child_id == -1:
            # Use the bone's orientation from the rest matrix to set tail
            rest_matrix = bone["rest_matrix"]
            bone_direction = rest_matrix.col[1].xyz.normalized()
            bone.tail = bone.head + bone_direction * 0.05  # Small length for leaf bones
    
    # Exit edit mode
    bpy.ops.object.mode_set(mode='OBJECT')
    
    return armature_obj

def _convert_nod_matrix_to_blender(rest_matrix_inverse_list):
    """
    Convert NOD matrix (list of Vector4) to Blender Matrix
    
    Args:
        rest_matrix_inverse_list: List of 3 Vector4 objects representing a 3x4 matrix
    
    Returns:
        mathutils.Matrix (4x4)
    """
    # Convert list of Vector4 to 4x4 matrix
    # NOD uses 3x4 matrix (3 rows, 4 columns), we need to make it 4x4
    matrix_data = []
    
    for vec4 in rest_matrix_inverse_list:
        row = [vec4.x, vec4.y, vec4.z, vec4.w]
        matrix_data.append(row)
    
    # Add the fourth row for homogeneous coordinates
    matrix_data.append([0.0, 0.0, 0.0, 1.0])
    
    # Create Blender matrix
    return mathutils.Matrix(matrix_data)

# Example usage:
# create_blender_skeleton_from_nod(nod_bones_list, "MyCharacter_Armature")