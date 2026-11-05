"""Blender headless smoke test for Nod_Import."""

import os
import pathlib
import sys

# Ensure repository parent is in sys.path
REPO_DIR = pathlib.Path(__file__).resolve().parent.parent
PARENT_DIR = str(REPO_DIR.parent)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

try:
    import bpy
except ModuleNotFoundError:
    bpy = None

if bpy is not None:
    import Nod_Import
    from Nod_Import.nod_to_blender_utils import LoadModel

DEFAULT_NOD_FILE = r"F:\GOG Games\Vampire The Masquerade - Redemption\ExtractedModels\christof.nod"


def clear_scene_data():
    """Remove all objects and actions for a clean run."""
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in list(bpy.data.meshes):
        bpy.data.meshes.remove(mesh, do_unlink=True)
    for arm in list(bpy.data.armatures):
        bpy.data.armatures.remove(arm, do_unlink=True)
    for act in list(bpy.data.actions):
        bpy.data.actions.remove(act, do_unlink=True)
    for mat in list(bpy.data.materials):
        bpy.data.materials.remove(mat, do_unlink=True)


def verify_armature_and_meshes(expected_bones):
    meshes = [obj for obj in bpy.data.objects if obj.type == "MESH"]
    assert len(meshes) >= 1, f"Expected at least 1 mesh, found {len(meshes)}"

    armatures = [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]
    assert len(armatures) == 1, f"Expected 1 armature object, found {len(armatures)}"
    armature_obj = armatures[0]

    bone_count = len(armature_obj.data.bones)
    assert bone_count == expected_bones, (
        f"Armature bone count {bone_count} does not match expected {expected_bones}"
    )

    for mesh in meshes:
        arm_mods = [
            mod for mod in mesh.modifiers
            if mod.type == "ARMATURE" and mod.object == armature_obj
        ]
        assert len(arm_mods) >= 1, (
            f"Mesh '{mesh.name}' has no Armature modifier pointing to '{armature_obj.name}'"
        )

    return armature_obj, meshes


def main():
    nod_file = os.environ.get("NOD_TEST_FILE", DEFAULT_NOD_FILE)
    if not os.path.isfile(nod_file):
        print(f"SKIPPED: Test file does not exist: {nod_file}")
        sys.exit(0)

    print(f"Smoke test using NOD file: {nod_file}")

    # Parse header to retrieve expected bones count
    with open(nod_file, "rb") as f:
        parsed_nod = LoadModel(f.read())
    expected_bones = parsed_nod.header.num_bones
    print(f"Expected bones from header: {expected_bones}")

    # Register addon
    Nod_Import.register()

    try:
        # Run 1: without animations
        print("\n--- Test Run 1: load_animation=False ---")
        clear_scene_data()
        result1 = bpy.ops.nod_import.data(filepath=nod_file, load_animation=False)
        assert result1 == {"FINISHED"}, f"Run 1 operator failed with {result1}"
        verify_armature_and_meshes(expected_bones)
        print("Run 1 passed: mesh, armature, and modifiers verified.")

        # Run 2: default (with animations)
        print("\n--- Test Run 2: default (with animation) ---")
        clear_scene_data()
        result2 = bpy.ops.nod_import.data(filepath=nod_file)
        assert result2 == {"FINISHED"}, f"Run 2 operator failed with {result2}"
        armature_obj, meshes = verify_armature_and_meshes(expected_bones)

        # Animation assertions
        action_count = len(bpy.data.actions)
        assert action_count > 0, f"Expected actions loaded > 0, found {action_count}"

        anim_data = armature_obj.animation_data
        assert anim_data is not None, "Armature object has no animation_data"
        assert anim_data.action is not None, "Armature animation_data has no active action"
        if hasattr(anim_data, "action_slot"):
            assert anim_data.action_slot is not None, (
                "Armature animation_data has no action_slot assigned"
            )

        print(
            f"Run 2 passed: {action_count} actions loaded, active action "
            f"'{anim_data.action.name}' with slot verified."
        )

        print("\nSmoke test completed successfully!")

    except Exception as exc:
        import traceback
        traceback.print_exc()
        print(f"SMOKE TEST FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        try:
            Nod_Import.unregister()
        except Exception as unreg_exc:
            print(f"Warning during unregister: {unreg_exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
