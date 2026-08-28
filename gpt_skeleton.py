import bpy
import mathutils
from typing import List

# Blender script to create an armature from NodBones
def create_armature_from_nodbones(nod_bones):
    # Create a new armature object
    bpy.ops.object.armature_add()
    armature = bpy.context.object
    armature.name = "Nod Armature"
    bpy.ops.object.mode_set(mode="EDIT")  # Switch to edit mode to add bones

    # Dictionary to store created bones by id (for easy parent linking)
    bones_dict = {}

    for nod_bone in nod_bones:
        # Convert rest_matrix_inverse (list of Vector4) to a 3x4 matrix
        matrix = mathutils.Matrix((
            (nod_bone.rest_matrix_inverse[0].x, nod_bone.rest_matrix_inverse[0].y, nod_bone.rest_matrix_inverse[0].z, 0),
            (nod_bone.rest_matrix_inverse[1].x, nod_bone.rest_matrix_inverse[1].y, nod_bone.rest_matrix_inverse[1].z, 0),
            (nod_bone.rest_matrix_inverse[2].x, nod_bone.rest_matrix_inverse[2].y, nod_bone.rest_matrix_inverse[2].z, 0),
            (nod_bone.rest_translate.x, nod_bone.rest_translate.y, nod_bone.rest_translate.z, 1)  # Translation as the last row
        ))

        # Perform matrix inversion and transposition
        bone_matrix = matrix.transposed().inverted()

        # Extract the head of the bone (the translation part)
        translation = bone_matrix.to_translation()

        # Create the bone in Blender
        bone = armature.data.edit_bones.new(f"Bone_{nod_bone.parent_id}_{nod_bone.child_id}")
        bone.head = translation  # Head of the bone is the translation from the matrix
        bone.tail = translation + mathutils.Vector((0, 0, 1))  # Point the bone's tail along Z-axis (default)

        # Store the bone in the dictionary (so we can later link parents)
        bones_dict[nod_bone.parent_id] = bone

        # Set parent if applicable
        if nod_bone.parent_id != -1:  # -1 means no parent (root bone)
            parent_bone = bones_dict.get(nod_bone.parent_id)
            if parent_bone:
                bone.parent = parent_bone
            else:
                print(f"Warning: Parent bone {nod_bone.parent_id} not found for bone {nod_bone.parent_id}_{nod_bone.child_id}")

    bpy.ops.object.mode_set(mode="OBJECT")  # Switch to object mode after editing bones