from mathutils import Matrix
from mathutils import Vector
from .vector4 import Vector4
from .nod_bone import NodBone
import bpy

ARMATURE_NAME = "NOD_Armature"

"""
def create_blender_skeleton_from_nod(nod_bones : list[NodBone], armature_name=ARMATURE_NAME):
    for i in range(len(nod_bones)):
        matrix = matrix34_to_blender_matrix(nod_bones[i].rest_matrix_inverse)
        parent_name = None
        if nod_bones[i].parent_id != -1:
            parent_name = f"Bone_{nod_bones[i].parent_id:03d}"

        create_bone_from_matrix(armature_name, f"Bone_{i:03d}", matrix,1, parent_name)

def create_bone_from_matrix(armature_name: str, bone_name: str, matrix: Matrix, 
                           bone_length: float = 1.0, parent_bone_name: str = None) -> str:
    # Get or create armature
    if armature_name in bpy.data.objects:
        armature_obj = bpy.data.objects[armature_name]
    else:
        # Create new armature
        armature_data = bpy.data.armatures.new(armature_name)
        armature_obj = bpy.data.objects.new(armature_name, armature_data)
        bpy.context.collection.objects.link(armature_obj)
    
    # Make sure we're in the right context
    bpy.context.view_layer.objects.active = armature_obj
    
    # Enter edit mode to create/edit bones
    bpy.ops.object.mode_set(mode='EDIT')
    
    # Get the armature data in edit mode
    edit_bones = armature_obj.data.edit_bones
    
    # Create the bone
    bone = edit_bones.new(bone_name)
    
    # Extract position and rotation from matrix
    bone_head = matrix.to_translation()
    bone_tail = bone_head + (matrix.to_3x3() @ Vector((0, bone_length, 0)))
    
    # Set bone head and tail positions
    bone.head = bone_head
    bone.tail = bone_tail
    
    # Set parent if specified
    if parent_bone_name and parent_bone_name in edit_bones:
        bone.parent = edit_bones[parent_bone_name]
    
    # Exit edit mode
    bpy.ops.object.mode_set(mode='OBJECT')
    
    return bone_name
"""

#void GUtil_GetEulerAngles2(const float m[3][4], float angles[3])
#{
#	float cy;
#
#	// order of angles x,y,z
#
#	cy = (float) sqrt(m[0][0] * m[0][0] + m[0][1] * m[0][1]); // AX^2 + BX^2
#
#	if (cy > 16 * 0.001)
#		{
#			angles[0] = (float) atan2(m[1][2], m[2][2]); // CY, CZ
#			angles[1] = (float) atan2(-m[0][2], cy); // -CX, cy
#			angles[2] = (float) atan2(m[0][1], m[0][0]); // BX, AX
#		}
#	else
#		{
#			angles[0] = (float) atan2(-m[2][1], m[1][1]); //-BZ, BY
#			angles[1] = (float) atan2(-m[0][2], cy);	// -CX, cy
#			angles[2] = 0;
#		}
#}

def matrix34_to_blender_matrix(rest_matrix_inverse: list[Vector4]) -> Matrix:
    """
    Convert a Matrix34 (list of 3 Vector4) to a Blender 4x4 matrix.
    
    Args:
        rest_matrix_inverse: List of 3 Vector4 objects representing a 3x4 matrix
                           (the inverse of the bone's rest pose matrix)
    
    Returns:
        mathutils.Matrix: 4x4 matrix suitable for Blender bone operations
    """
    # Convert Matrix34 to 4x4 matrix
    # The input is the inverse matrix, so we need to create the 4x4 version first
    matrix_inverse_4x4 = Matrix((
        (rest_matrix_inverse[0].x, rest_matrix_inverse[0].y, rest_matrix_inverse[0].z, rest_matrix_inverse[0].w),
        (rest_matrix_inverse[1].x, rest_matrix_inverse[1].y, rest_matrix_inverse[1].z, rest_matrix_inverse[1].w),
        (rest_matrix_inverse[2].x, rest_matrix_inverse[2].y, rest_matrix_inverse[2].z, rest_matrix_inverse[2].w),
        (0.0, 0.0, 0.0, 1.0)
    ))
    
    # Invert to get the actual rest pose matrix
    rest_matrix = matrix_inverse_4x4.inverted()
    
    # Coordinate system conversion matrix
    # From Z-up, Y-forward to Blender's coordinate system
    # This converts from your model's coordinate system to Blender's
    conversion_matrix = Matrix((
        (1.0,  0.0,  0.0, 0.0),
        (0.0,  0.0, -1.0, 0.0),
        (0.0,  1.0,  0.0, 0.0),
        (0.0,  0.0,  0.0, 1.0)
    ))
    
    # Apply coordinate system conversion
    blender_matrix = conversion_matrix @ rest_matrix @ conversion_matrix.inverted()
    
    return blender_matrix

def matrix34_to_blender_matrix_simple(rest_matrix_inverse: list[Vector4]) -> Matrix:
    """
    Simplified version that just converts Matrix34 to 4x4 and inverts it,
    without coordinate system conversion. Use this if you want to handle
    coordinate conversion separately.
    
    Args:
        rest_matrix_inverse: List of 3 Vector4 objects representing a 3x4 matrix
    
    Returns:
        mathutils.Matrix: 4x4 matrix (inverted from the input)
    """
    # Convert Matrix34 to 4x4 matrix
    matrix_inverse_4x4 = Matrix((
        (rest_matrix_inverse[0].x, rest_matrix_inverse[0].y, rest_matrix_inverse[0].z, rest_matrix_inverse[0].w),
        (rest_matrix_inverse[1].x, rest_matrix_inverse[1].y, rest_matrix_inverse[1].z, rest_matrix_inverse[1].w),
        (rest_matrix_inverse[2].x, rest_matrix_inverse[2].y, rest_matrix_inverse[2].z, rest_matrix_inverse[2].w),
        (0.0, 0.0, 0.0, 1.0)
    ))
    
    # Invert to get the actual rest pose matrix
    return matrix_inverse_4x4.inverted()

# Example usage:
if __name__ == "__main__":
    # Example data
    example_matrix = [
        Vector4(1.0, 0.0, 0.0, 0.0),
        Vector4(0.0, 1.0, 0.0, 0.0),
        Vector4(0.0, 0.0, 1.0, 0.0)
    ]
    
    # Convert to Blender matrix
    blender_matrix = matrix34_to_blender_matrix(example_matrix)
    print("Blender Matrix:")
    for row in blender_matrix:
        print(f"  {row}")
    
    # Or use the simple version
    simple_matrix = matrix34_to_blender_matrix_simple(example_matrix)
    print("\nSimple Matrix (no coordinate conversion):")
    for row in simple_matrix:
        print(f"  {row}")
