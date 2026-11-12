"""Run in background Blender; optionally pass a source .blend after --.

Compare exported, engine-style (rotation/translation only) skinning with Blender
world-space deformation. Includes object scale, delta scale, transformed parents,
standalone NAD parity, state restoration, and unsupported animated-scale errors.
"""
import math
import pathlib
import sys
import tempfile

import bpy
from mathutils import Euler, Matrix, Vector

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
from Nod_Import.blender_to_nod import build_nod_from_blender
from Nod_Import.blender_to_nad import build_nad_from_action
from Nod_Import.nod_math import nod_inverse_bind_matrix, order_blender_bones
from Nod_Import.nod_file import NodFile
from Nod_Import.nad_file import NadFile
from Nod_Import.binary_reader import BinaryReader


def check_action(arm, model, action):
    old_frame = bpy.context.scene.frame_current
    old_action = arm.animation_data.action
    old_world = arm.matrix_world.copy()
    nad = build_nad_from_action(bpy.context, arm, action, model.bones)
    assert bpy.context.scene.frame_current == old_frame
    assert arm.animation_data.action == old_action
    assert all(t.track_type in (0, 1) for t in nad.bone_tracks)
    nad = NadFile(nad.to_bytes())
    standalone = build_nad_from_action(bpy.context, arm, action)
    assert standalone.to_bytes() == nad.to_bytes(), 'Standalone NAD bind differs from paired export'
    bones = order_blender_bones(arm)
    original_bind_inv = [(old_world @ b.matrix_local).inverted() for b in bones]
    inverse_bind = [nod_inverse_bind_matrix(b) for b in model.bones]
    start = int(round(action.frame_start if action.use_frame_range else action.frame_range[0]))
    sample_indices = sorted({0, len(nad.bone_tracks[0].keys) // 2, len(nad.bone_tracks[0].keys) - 1})
    max_error = 0.0
    try:
        arm.animation_data.action = action
        for sample in sample_indices:
            frame = nad.bone_tracks[0].keys[sample].frame
            bpy.context.scene.frame_set(start + round(frame))
            tracks = {(t.bone_num, t.track_type): t.keys[sample].value for t in nad.bone_tracks}
            world = []
            for i, b in enumerate(model.bones):
                t = Vector((b.rest_translate.x, b.rest_translate.y, b.rest_translate.z))
                t += Vector(tracks.get((i, 1), (0, 0, 0)))
                angles = tracks[(i, 0)]
                m = Matrix.Translation(t) @ Euler(tuple(math.radians(v) for v in angles), 'XYZ').to_matrix().to_4x4()
                world.append(world[b.parent_id] @ m if b.parent_id >= 0 else m)
            exported = [world[i] @ inverse_bind[i] for i in range(len(bones))]
            expected = [arm.matrix_world @ arm.pose.bones[b.name].matrix @ original_bind_inv[i]
                        for i, b in enumerate(bones)]
            # Every exported vertex, including UV/normal splits and soft weights.
            for v in model.vertices:
                p = Vector((v.position.x, v.position.y, v.position.z))
                i = v.bone_number
                parent = model.bones[i].parent_id
                if parent < 0:
                    parent = i
                actual = v.weight * (exported[i] @ p) + (1 - v.weight) * (exported[parent] @ p)
                wanted = v.weight * (expected[i] @ p) + (1 - v.weight) * (expected[parent] @ p)
                max_error = max(max_error, (actual - wanted).length)
    finally:
        arm.animation_data.action = old_action
        bpy.context.scene.frame_set(old_frame)
    assert max_error < 0.01, (action.name, max_error)
    print(f'PASS {action.name}: engine skinning max error {max_error:.6f}, no scale tracks')


def synthetic_case(delta=False, parented=False):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.object.armature_add()
    arm = bpy.context.object
    arm.name = 'ScaleRegressionRig'
    bpy.ops.object.mode_set(mode='EDIT')
    root = arm.data.edit_bones[0]
    root.head, root.tail = (0, 0, 0), (0, 0, 1)
    child = arm.data.edit_bones.new('Child')
    child.head, child.tail, child.parent = (0, 0, 1), (0, 0, 2), root
    root_name = root.name
    bpy.ops.object.mode_set(mode='OBJECT')
    if delta:
        arm.delta_scale = (73.309,)*3
    else:
        arm.scale = (73.309,)*3
    arm.rotation_euler = (0.1, -0.2, 0.4)
    arm.location = (4, -8, 3)
    if parented:
        parent = bpy.data.objects.new('ScaledParent', None)
        bpy.context.collection.objects.link(parent)
        parent.scale = (2,)*3
        parent.rotation_euler = (0.2, 0, -0.3)
        arm.parent = parent
    mesh = bpy.data.meshes.new('TestMesh')
    mesh.from_pydata([(0.1,0,0), (0.3,0.1,1), (-0.1,0,2)], [], [(0,1,2)])
    obj = bpy.data.objects.new('TestMesh', mesh)
    bpy.context.collection.objects.link(obj)
    obj.parent = arm
    mod = obj.modifiers.new('Armature', 'ARMATURE')
    mod.object = arm
    obj.vertex_groups.new(name=root_name).add([0], 1, 'REPLACE')
    obj.vertex_groups.new(name='Child').add([1,2], 0.7, 'REPLACE')
    obj.vertex_groups[root_name].add([1,2], 0.3, 'REPLACE')
    for f in (1, 5, 9):
        pb = arm.pose.bones['Child']
        pb.rotation_mode = 'XYZ'
        pb.rotation_euler = (0.05*f, 0.02*f, -0.1*f)
        pb.location = (0.01*f, 0, 0.02*f)
        pb.keyframe_insert('rotation_euler', frame=f)
        pb.keyframe_insert('location', frame=f)
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    model = build_nod_from_blender(bpy.context)
    model = NodFile(BinaryReader(model.to_bytes(), 'little'))
    check_action(arm, model, arm.animation_data.action)
    # Exercise the actual UI operator routes as well as the core functions.
    import Nod_Import
    Nod_Import.register()
    try:
        with tempfile.TemporaryDirectory(dir=ROOT / 'tests') as directory:
            nod_path = str(pathlib.Path(directory) / 'scaled.nod')
            nad_path = str(pathlib.Path(directory) / 'standalone.nad')
            assert bpy.ops.nod_export.data(filepath=nod_path, export_format='NOD', export_animations=True) == {'FINISHED'}
            assert bpy.ops.nod_export.data(filepath=nad_path, export_format='NAD') == {'FINISHED'}
            written = NadFile(pathlib.Path(nad_path).read_bytes())
            assert all(t.track_type in (0, 1) for t in written.bone_tracks)
    finally:
        Nod_Import.unregister()
    # Real animated scaling must fail, with context, and restore the scene.
    action = arm.animation_data.action
    pb.scale = (1,1,1)
    pb.keyframe_insert('scale', frame=1)
    pb.scale = (2,2,2)
    pb.keyframe_insert('scale', frame=9)
    bpy.context.scene.frame_set(1)
    try:
        build_nad_from_action(bpy.context, arm, action, model.bones)
    except ValueError as exc:
        assert 'scale' in str(exc) and action.name in str(exc) and 'Child' in str(exc)
    else:
        raise AssertionError('Animated scale was silently exported')
    assert bpy.context.scene.frame_current == 1
    assert arm.animation_data.action == action
    print('PASS animated-scale rejection and scene restoration')


for delta, parented in ((False, False), (True, False), (True, True)):
    synthetic_case(delta, parented)

if '--' in sys.argv:
    source = sys.argv[sys.argv.index('--') + 1]
    bpy.ops.wm.open_mainfile(filepath=source)
    arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
    model = build_nod_from_blender(bpy.context)
    model = NodFile(BinaryReader(model.to_bytes(), 'little'))
    for action in list(bpy.data.actions):
        check_action(arm, model, action)
    print(f'PASS source model: {len(bpy.data.actions)} actions, {len(model.bones)} bones')

    extra = sys.argv[sys.argv.index('--') + 2:]
    if len(extra) == 2:
        import Nod_Import
        from Nod_Import.nad_to_blender import import_nad_file
        bpy.ops.wm.read_factory_settings(use_empty=True)
        Nod_Import.register()
        try:
            assert bpy.ops.nod_import.data(filepath=extra[0], load_animation=False) == {'FINISHED'}
            arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
            import_nad_file(extra[1], arm)
            bpy.context.scene.frame_set(1)
            model = build_nod_from_blender(bpy.context)
            original = NodFile(BinaryReader(pathlib.Path(extra[0]).read_bytes(), 'little'))
            for before, after in zip(original.bones, model.bones):
                assert before.rest_matrix_inverse == after.rest_matrix_inverse or all(
                    vars(a) == vars(b) for a, b in zip(before.rest_matrix_inverse, after.rest_matrix_inverse))
                assert vars(before.rest_translate) == vars(after.rest_translate)
            check_action(arm, model, arm.animation_data.action)
            print('PASS original game bind preservation and NAD roundtrip')
        finally:
            Nod_Import.unregister()

print('ALL SCALE EXPORT TESTS PASSED')
