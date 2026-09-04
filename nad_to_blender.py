import os
import math

import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

from .nad_file import NadFile


NAD_TRACK_ROTATION = 0
NAD_TRACK_TRANSLATION = 1
NAD_TRACK_SCALE = 2

NAD_TAG_NAMES = {
    0: "Lwalk", 1: "Rwalk", 2: "Lrun", 3: "Rrun", 4: "Fire",
    5: "Strike", 6: "Cast", 7: "Fall", 8: "Project", 9: "Flap",
    10: "Suck", 11: "Splat", 12: "Land", 13: "Grab",
    14: "Release", 15: "Weapon", 16: "Repeat", 17: "RepeatTo",
    18: "Throwdeath",
}


def load_nad(filepath):
    with open(filepath, "rb") as nad_stream:
        return NadFile(nad_stream.read())


def _track_target(track_type):
    if track_type == NAD_TRACK_ROTATION:
        return "rotation_quaternion"
    if track_type == NAD_TRACK_TRANSLATION:
        return "location"
    if track_type == NAD_TRACK_SCALE:
        return "scale"
    return None


def _nad_euler_to_quaternion(value):
    # NAD stores pitch/roll/yaw in degrees. This is confirmed by comparing the
    # first animation keys with the 4x3 inverse rest matrices in christof.nod.
    return Euler(tuple(math.radians(component) for component in value),
                 'XYZ').to_quaternion()


def _nod_inverse_world_rotation(nod_bone):
    """Return the rotation part of NOD's serialized inverse Matrix43."""
    values = []
    for row in nod_bone.rest_matrix_inverse:
        values.extend((row.x, row.y, row.z, row.w))
    return Matrix((values[0:3], values[3:6], values[6:9]))


def _nod_local_bind_rotation(nod_bones, bone_index):
    """Return inverse local bind rotation in the convention used by NAD."""
    bone = nod_bones[bone_index]
    child_inverse_world = _nod_inverse_world_rotation(bone)
    if bone.parent_id < 0:
        inverse_local = child_inverse_world
    else:
        parent_inverse_world = _nod_inverse_world_rotation(
            nod_bones[bone.parent_id]
        )
        # With NOD's row-vector Matrix43 convention:
        # inverse_local = inverse_child_world * parent_world.
        inverse_local = child_inverse_world @ parent_inverse_world.transposed()
    inverse_local.normalize()
    return inverse_local.to_quaternion()


def _relative_values(track, pose_bone, nod_bones):
    """Map absolute NAD channels onto the existing Blender rest pose."""
    if track.track_type == NAD_TRACK_ROTATION:
        base_rotation = _nod_local_bind_rotation(
            nod_bones, track.bone_num
        )
        values = []
        previous = None
        for key in track.keys:
            source_rotation = _nad_euler_to_quaternion(key.value)
            delta = base_rotation.inverted() @ source_rotation
            delta.normalize()
            # q and -q describe the same rotation. Keep one hemisphere so
            # interpolation never takes the long path between two keys.
            if previous is not None and previous.dot(delta) < 0.0:
                delta = Quaternion((-delta.w, -delta.x, -delta.y, -delta.z))
            values.append((delta.w, delta.x, delta.y, delta.z))
            previous = delta
        return values
    if track.track_type == NAD_TRACK_SCALE:
        return [tuple(
            value
            for axis, value in enumerate(key.value)
        ) for key in track.keys]
    if track.track_type == NAD_TRACK_TRANSLATION:
        rest_axes = pose_bone.bone.matrix_local.to_3x3()
        inverse_rest_axes = rest_axes.inverted_safe()
        return [tuple(inverse_rest_axes @ Vector(key.value))
                for key in track.keys]
    return [tuple(key.value) for key in track.keys]


def _set_linear_interpolation(key_points):
    for key_point in key_points:
        key_point.interpolation = 'LINEAR'


def import_nad_animation(nad_file, armature_obj, nod_bones,
                         action_name="NAD_Animation"):
    if armature_obj is None or armature_obj.type != 'ARMATURE':
        raise ValueError("A Blender armature object is required for NAD import")

    action = bpy.data.actions.new(name=action_name)
    # Only one Action can be active on the armature at a time. Preserve the
    # remaining imported NAD Actions when the .blend file is saved/reopened.
    action.use_fake_user = True
    armature_obj.animation_data_create()
    armature_obj.animation_data.action = action
    armature_obj.data.pose_position = 'POSE'

    imported_tracks = 0
    for track in nad_file.bone_tracks:
        if not track.keys:
            continue
        bone_name = f"Bone_{track.bone_num:03d}"
        pose_bone = armature_obj.pose.bones.get(bone_name)
        target = _track_target(track.track_type)
        if pose_bone is None or target is None:
            print(f"WARNING: skipping NAD track: bone={track.bone_num}, "
                  f"type={track.track_type}")
            continue

        if track.track_type == NAD_TRACK_ROTATION:
            pose_bone.rotation_mode = 'QUATERNION'

        values = _relative_values(track, pose_bone, nod_bones)
        data_path = f'pose.bones["{bone_name}"].{target}'
        channel_count = 4 if track.track_type == NAD_TRACK_ROTATION else 3
        for axis in range(channel_count):
            curve = action.fcurves.new(
                data_path=data_path,
                index=axis,
                action_group=bone_name,
            )
            curve.keyframe_points.add(len(track.keys))
            for index, key in enumerate(track.keys):
                # Blender's timeline is conventionally one-based.
                curve.keyframe_points[index].co = (
                    key.frame + 1.0,
                    values[index][axis],
                )
            _set_linear_interpolation(curve.keyframe_points)
            curve.update()
        imported_tracks += 1

    action["nad_version"] = nad_file.version
    action["nad_flags"] = nad_file.flags
    action["nad_duration"] = nad_file.duration

    scene = bpy.context.scene
    scene.render.fps = 30
    scene.render.fps_base = 1.0
    scene.frame_start = 1
    scene.frame_end = max(1, int(round(nad_file.duration)) + 1)

    for tag_index, tag in enumerate(nad_file.tags):
        tag_name = NAD_TAG_NAMES.get(tag.tag_type, f"Tag_{tag.tag_type}")
        marker_name = f"NAD_{tag_name}_{tag_index:02d}"
        marker = action.pose_markers.new(marker_name)
        marker.frame = int(round(tag.frame)) + 1

    scene.frame_set(1)
    print(f"Imported NAD action '{action.name}': {imported_tracks}/"
          f"{nad_file.num_bone_tracks} tracks, {nad_file.num_tags} tags, "
          f"duration={nad_file.duration}")
    return action


def import_nad_file(filepath, armature_obj, nod_bones):
    nad_file = load_nad(filepath)
    action_name = os.path.splitext(os.path.basename(filepath))[0]
    return import_nad_animation(
        nad_file, armature_obj, nod_bones, action_name
    )
