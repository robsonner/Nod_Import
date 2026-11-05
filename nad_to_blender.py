import bisect
import math
import os

import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

from .nad_file import NadFile
from .debug_logging import debug_print


NAD_TRACK_ROTATION = 0
NAD_TRACK_TRANSLATION = 1
NAD_TRACK_SCALE = 2

NAD_BAKE_STEP = 1.0

# Keyframe tag names from Vampire: The Masquerade – Redemption NAD specification (Docs/nad.htm)
NAD_TAG_NAMES = {
    0: "Lwalk", 1: "Rwalk", 2: "Lrun", 3: "Rrun", 4: "Fire",
    5: "Strike", 6: "Cast", 7: "Fall", 8: "Project", 9: "Flap",
    10: "Suck", 11: "Idle", 12: "Idle2", 13: "Codex1",
    14: "Codex2", 15: "Codex3", 16: "Repeat", 17: "RepeatTo",
    18: "Throwdeath",
}


def load_nad(filepath):
    with open(filepath, "rb") as nad_stream:
        return NadFile(nad_stream.read())


def _nad_euler_to_quaternion(value):
    return Euler(tuple(math.radians(component) for component in value),
                 'XYZ').to_quaternion()


def _nod_inverse_bind_matrix(nod_bone):
    """Convert NOD's serialized row-vector Matrix43 to a Blender matrix."""
    values = []
    for row in nod_bone.rest_matrix_inverse:
        values.extend((row.x, row.y, row.z, row.w))
    return Matrix((
        (values[0], values[3], values[6], values[9]),
        (values[1], values[4], values[7], values[10]),
        (values[2], values[5], values[8], values[11]),
        (0.0, 0.0, 0.0, 1.0),
    ))


def _nod_bind_world_matrices(nod_bones):
    return [_nod_inverse_bind_matrix(bone).inverted_safe()
            for bone in nod_bones]


def _local_bind_matrices(nod_bones, bind_world):
    result = []
    for index, bone in enumerate(nod_bones):
        if 0 <= bone.parent_id < len(nod_bones):
            result.append(bind_world[bone.parent_id].inverted_safe()
                          @ bind_world[index])
        else:
            result.append(bind_world[index].copy())
    return result


def _evaluate_track(track, frame):
    """Evaluate one NAD vector track at a source frame using Hermite curve interpolation."""
    keys = track.keys
    if not keys:
        return Vector((0.0, 0.0, 0.0))
    if frame <= keys[0].frame:
        return Vector(keys[0].value)
    if frame >= keys[-1].frame:
        return Vector(keys[-1].value)

    frames = getattr(track, "_frames", None)
    if frames is None:
        frames = [key.frame for key in keys]
        track._frames = frames

    index = bisect.bisect_right(frames, frame) - 1
    left = keys[index]
    right = keys[index + 1]

    distance = right.frame - left.frame
    if left.frame_scale <= 0.0 or distance <= 0.0:
        return Vector(left.value)

    s = (frame - left.frame) * left.frame_scale
    val = left.value
    c = left.c_factor
    b = left.b_factor
    a = left.a_factor

    return Vector((
        val[0] + s * (c[0] + s * (b[0] + s * a[0])),
        val[1] + s * (c[1] + s * (b[1] + s * a[1])),
        val[2] + s * (c[2] + s * (b[2] + s * a[2])),
    ))


def _animation_frames(nad_file):
    duration = float(nad_file.duration)
    frames = {0.0, duration}
    for track in nad_file.bone_tracks:
        frames.update(float(key.frame) for key in track.keys)
    if NAD_BAKE_STEP > 0.0:
        count = int(math.floor(duration / NAD_BAKE_STEP))
        for i in range(count + 1):
            frames.add(float(i * NAD_BAKE_STEP))
    return sorted(frames)


def _make_source_pose_world(nod_bones, local_bind, tracks, frame):
    """Reconstruct an absolute NAD pose through the NOD hierarchy."""
    pose_world = [None] * len(nod_bones)

    def calculate(index):
        if pose_world[index] is not None:
            return pose_world[index]
        bone = nod_bones[index]
        translation = local_bind[index].to_translation()
        rotation = local_bind[index].to_quaternion()
        scale = Vector((1.0, 1.0, 1.0))

        track = tracks.get((index, NAD_TRACK_ROTATION))
        if track is not None:
            rotation = _nad_euler_to_quaternion(_evaluate_track(track, frame))

        track = tracks.get((index, NAD_TRACK_TRANSLATION))
        if track is not None:
            # NAD translation is an animation offset from RestTranslate.
            translation += _evaluate_track(track, frame)

        track = tracks.get((index, NAD_TRACK_SCALE))
        if track is not None:
            scale = _evaluate_track(track, frame)

        local_pose = (Matrix.Translation(translation)
                      @ rotation.to_matrix().to_4x4()
                      @ Matrix.Diagonal((*scale, 1.0)))
        if 0 <= bone.parent_id < len(nod_bones):
            pose_world[index] = calculate(bone.parent_id) @ local_pose
        else:
            pose_world[index] = local_pose
        return pose_world[index]

    for bone_index in range(len(nod_bones)):
        calculate(bone_index)
    return pose_world


def _target_pose_basis(target_pose_world, target_bind_world, nod_bones):
    """Convert absolute target poses into Blender pose-bone basis matrices."""
    result = []
    for index, bone in enumerate(nod_bones):
        if 0 <= bone.parent_id < len(nod_bones):
            parent = bone.parent_id
            rest_local = (target_bind_world[parent].inverted_safe()
                          @ target_bind_world[index])
            pose_local = (target_pose_world[parent].inverted_safe()
                          @ target_pose_world[index])
            result.append(rest_local.inverted_safe() @ pose_local)
        else:
            result.append(target_bind_world[index].inverted_safe()
                          @ target_pose_world[index])
    return result


def _add_fcurve(action, armature_obj, data_path, array_index, frames, values, group):
    curve = action.fcurve_ensure_for_datablock(
        armature_obj, data_path, index=array_index, group_name=group
    )
    n = len(frames)
    curve.keyframe_points.add(n)
    flat = [coord for pair in zip(frames, values) for coord in (pair[0] + 1.0, pair[1])]
    curve.keyframe_points.foreach_set("co", flat)
    try:
        curve.keyframe_points.foreach_set("interpolation", [1] * n)  # 1 == LINEAR
    except Exception:
        for point in curve.keyframe_points:
            point.interpolation = 'LINEAR'
    curve.update()


def import_nad_animation(nad_file, armature_obj, nod_bones,
                         action_name="NAD_Animation"):
    if armature_obj is None or armature_obj.type != 'ARMATURE':
        raise ValueError("A Blender armature object is required for NAD import")
    if len(nod_bones) != len(armature_obj.data.bones):
        raise ValueError("NAD/NOD bone count does not match Blender armature")

    action = bpy.data.actions.new(name=action_name)
    action.use_fake_user = True
    armature_obj.animation_data_create()
    armature_obj.animation_data.action = action
    armature_obj.data.pose_position = 'POSE'

    tracks = {(track.bone_num, track.track_type): track
              for track in nad_file.bone_tracks
              if 0 <= track.bone_num < len(nod_bones) and track.keys}
    frames = _animation_frames(nad_file)
    source_bind_world = _nod_bind_world_matrices(nod_bones)
    source_local_bind = _local_bind_matrices(nod_bones, source_bind_world)
    target_bind_world = [
        armature_obj.data.bones[f"Bone_{index:03d}"].matrix_local.copy()
        for index in range(len(nod_bones))
    ]

    samples = [{"location": [], "rotation_quaternion": [], "scale": []}
               for _ in nod_bones]
    previous_rotations = [None] * len(nod_bones)

    for frame in frames:
        source_pose_world = _make_source_pose_world(
            nod_bones, source_local_bind, tracks, frame
        )
        target_pose_world = []
        for index in range(len(nod_bones)):
            deformation = (source_pose_world[index]
                           @ source_bind_world[index].inverted_safe())
            target_pose_world.append(deformation @ target_bind_world[index])

        basis_matrices = _target_pose_basis(
            target_pose_world, target_bind_world, nod_bones
        )
        for index, basis in enumerate(basis_matrices):
            location, rotation, scale = basis.decompose()
            previous = previous_rotations[index]
            if previous is not None and previous.dot(rotation) < 0.0:
                rotation = Quaternion(
                    (-rotation.w, -rotation.x, -rotation.y, -rotation.z)
                )
            previous_rotations[index] = rotation.copy()
            samples[index]["location"].append(tuple(location))
            samples[index]["rotation_quaternion"].append(
                (rotation.w, rotation.x, rotation.y, rotation.z)
            )
            samples[index]["scale"].append(tuple(scale))

    for index, bone_samples in enumerate(samples):
        bone_name = f"Bone_{index:03d}"
        armature_obj.pose.bones[bone_name].rotation_mode = 'QUATERNION'
        for property_name, channel_count in (
                ("location", 3), ("rotation_quaternion", 4), ("scale", 3)):
            data_path = f'pose.bones["{bone_name}"].{property_name}'
            values = bone_samples[property_name]
            for channel in range(channel_count):
                _add_fcurve(action, armature_obj, data_path, channel, frames,
                            [value[channel] for value in values], bone_name)

    if armature_obj.animation_data.action_slot is None:
        if action.slots:
            armature_obj.animation_data.action_slot = action.slots[0]
    assert armature_obj.animation_data.action_slot is not None

    action["nad_version"] = nad_file.version
    action["nad_flags"] = nad_file.flags
    action["nad_duration"] = nad_file.duration

    action.use_frame_range = True
    action.frame_start = 1.0
    action.frame_end = float(max(1, round(nad_file.duration) + 1))

    for tag_index, tag in enumerate(nad_file.tags):
        tag_name = NAD_TAG_NAMES.get(tag.tag_type, f"Tag_{tag.tag_type}")
        marker = action.pose_markers.new(f"NAD_{tag_name}_{tag_index:02d}")
        marker.frame = int(round(tag.frame)) + 1

    debug_print(f"Imported matrix-retargeted NAD action '{action.name}': "
                f"{len(tracks)}/{nad_file.num_bone_tracks} tracks, "
                f"{len(frames)} sampled frames, {nad_file.num_tags} tags, "
                f"duration={nad_file.duration}")
    return action


def import_nad_file(filepath, armature_obj, nod_bones):
    nad_file = load_nad(filepath)
    action_name = os.path.splitext(os.path.basename(filepath))[0]
    action = import_nad_animation(nad_file, armature_obj, nod_bones, action_name)
    action["nad_source"] = filepath
    return action
