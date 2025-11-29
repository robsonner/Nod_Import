import bpy
from mathutils import Vector, Matrix

def create_blender_skeleton_from_nod(nod_bones, armature_name="NOD_Armature"):
    """
    Convert NOD bone structure to Blender armature.
    
    Args:
        nod_bones: List of NodBone objects
        armature_name: Name for the created armature
    
    Returns:
        bpy.types.Object: The created armature object
    """
    
    # Clear existing armatures if any
    bpy.ops.object.select_all(action='DESELECT')
    
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
    bone_world_positions = {}
    
    # Calculate world positions by traversing the hierarchy
    def calculate_world_position(bone_index, visited=None):
        if visited is None:
            visited = set()
        
        if bone_index in visited:
            print(f"WARNING: Circular reference detected for bone {bone_index}")
            return Vector((0, 0, 0))
        
        if bone_index in bone_world_positions:
            return bone_world_positions[bone_index]
        
        visited.add(bone_index)
        nod_bone = nod_bones[bone_index]
        local_pos = Vector((nod_bone.rest_translate.x, 
                           nod_bone.rest_translate.y, 
                           nod_bone.rest_translate.z))
        
        if nod_bone.parent_id == -1:
            # Root bone - use local position as world position
            world_pos = local_pos
        else:
            # Child bone - add to parent's world position
            parent_world_pos = calculate_world_position(nod_bone.parent_id, visited.copy())
            world_pos = parent_world_pos + local_pos
        
        bone_world_positions[bone_index] = world_pos
        return world_pos
    
    # Calculate world positions for all bones
    print(f"=== CALCULATING WORLD POSITIONS ===")
    for i in range(len(nod_bones)):
        world_pos = calculate_world_position(i)
        print(f"Bone {i}: local=({nod_bones[i].rest_translate.x:6.2f}, {nod_bones[i].rest_translate.y:6.2f}, {nod_bones[i].rest_translate.z:6.2f}) -> world=({world_pos.x:6.2f}, {world_pos.y:6.2f}, {world_pos.z:6.2f})")
    
    # Create all bones with world positions
    print(f"\n=== CREATING BONES ===")
    for i, nod_bone in enumerate(nod_bones):
        # Create bone
        bone = armature.edit_bones.new(f"Bone_{i:03d}")
        bone_dict[i] = bone
        
        # Set bone head to calculated world position
        world_pos = bone_world_positions[i]
        bone.head = world_pos
        
        # Set initial tail (will be corrected later)
        bone.tail = world_pos + Vector((0, 0, 0.1))
        
        print(f"Created bone {i}: {bone.name} at world position {world_pos}")
    
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
        
        # Special handling for root bone
        if nod_bone.parent_id == -1:
            # Root bone - use default upward direction
            bone.tail = bone.head + Vector((0, 0, 0.1))
            print(f"Bone {i} is ROOT bone, using default upward direction")
            continue
        
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