import math
import re

import bpy
from mathutils import Euler, Matrix, Vector

from .debug_logging import debug_print, set_debug_logging
from .nad_file import NadBoneTrack, NadFile, NadKeyframe, NadTag
from .blender_to_nod import reconstruct_export_bones
from .nad_to_blender import (
    NAD_TAG_NAMES,
    NAD_TRACK_ROTATION,
    NAD_TRACK_TRANSLATION,
    _local_bind_matrices,
    _nod_bind_world_matrices,
)
from .nod_math import order_blender_bones, rigid_export_matrix

_TAG_NAME_TO_ID = {name.lower(): tag_id for tag_id, name in NAD_TAG_NAMES.items()}
_MARKER_RE = re.compile(r"^(?:NAD_)?([A-Za-z0-9_]+?)(?:_\d+)?$")
_RAW_TAG_RE = re.compile(r"^tag_(\d+)$", re.IGNORECASE)


def _parse_marker_tag_type(marker_name: str):
    if not marker_name:
        return None
    clean = marker_name.strip()
    if clean.lower() in _TAG_NAME_TO_ID:
        return _TAG_NAME_TO_ID[clean.lower()]

    m = _MARKER_RE.match(clean)
    if m:
        core = m.group(1)
        if core.lower() in _TAG_NAME_TO_ID:
            return _TAG_NAME_TO_ID[core.lower()]
        raw_m = _RAW_TAG_RE.match(core)
        if raw_m:
            return int(raw_m.group(1))
    return None


def _compute_hermite_keys(frames: list[float], values: list[tuple[float, float, float]], use_smooth_tangents: bool = True) -> list[NadKeyframe]:
    n = len(frames)
    if n == 0:
        return []
    if n == 1:
        kf = NadKeyframe()
        kf.frame = float(frames[0])
        kf.frame_scale = 0.0
        kf.value = tuple(float(x) for x in values[0])
        kf.c_factor = (0.0, 0.0, 0.0)
        kf.b_factor = (0.0, 0.0, 0.0)
        kf.a_factor = (0.0, 0.0, 0.0)
        return [kf]

    # Compute per-keyframe tangents (derivative with respect to frame t)
    tangents = []
    for i in range(n):
        if not use_smooth_tangents:
            tangents.append((0.0, 0.0, 0.0))
            continue
        if i == 0:
            dt = frames[1] - frames[0]
            if dt > 1e-6:
                tangents.append(tuple((values[1][c] - values[0][c]) / dt for c in range(3)))
            else:
                tangents.append((0.0, 0.0, 0.0))
        elif i == n - 1:
            dt = frames[n - 1] - frames[n - 2]
            if dt > 1e-6:
                tangents.append(tuple((values[n - 1][c] - values[n - 2][c]) / dt for c in range(3)))
            else:
                tangents.append((0.0, 0.0, 0.0))
        else:
            dt = frames[i + 1] - frames[i - 1]
            if dt > 1e-6:
                tangents.append(tuple((values[i + 1][c] - values[i - 1][c]) / dt for c in range(3)))
            else:
                tangents.append((0.0, 0.0, 0.0))

    keyframes = []
    for i in range(n):
        kf = NadKeyframe()
        kf.frame = float(frames[i])
        kf.value = tuple(float(x) for x in values[i])

        if i == n - 1:
            kf.frame_scale = 0.0
            kf.c_factor = (0.0, 0.0, 0.0)
            kf.b_factor = (0.0, 0.0, 0.0)
            kf.a_factor = (0.0, 0.0, 0.0)
        else:
            dt = frames[i + 1] - frames[i]
            if dt <= 1e-6:
                kf.frame_scale = 0.0
                kf.c_factor = (0.0, 0.0, 0.0)
                kf.b_factor = (0.0, 0.0, 0.0)
                kf.a_factor = (0.0, 0.0, 0.0)
            else:
                kf.frame_scale = float(1.0 / dt)
                c_list = []
                b_list = []
                a_list = []
                for comp in range(3):
                    delta = values[i + 1][comp] - values[i][comp]
                    if use_smooth_tangents:
                        m0 = tangents[i][comp] * dt
                        m1 = tangents[i + 1][comp] * dt
                        c_val = m0
                        b_val = 3.0 * delta - 2.0 * m0 - m1
                        a_val = m1 + m0 - 2.0 * delta
                    else:
                        c_val = delta
                        b_val = 0.0
                        a_val = 0.0
                    c_list.append(float(c_val))
                    b_list.append(float(b_val))
                    a_list.append(float(a_val))
                kf.c_factor = tuple(c_list)
                kf.b_factor = tuple(b_list)
                kf.a_factor = tuple(a_list)

        keyframes.append(kf)

    return keyframes


def build_nad_from_action(
    context,
    armature_obj,
    action=None,
    nod_bones=None,
    frame_step: int = 1,
    use_smooth_tangents: bool = True,
    debug_log: bool = False,
) -> NadFile:
    """Sample a Blender Action on a NOD armature and convert it into a NadFile."""
    set_debug_logging(debug_log)

    if armature_obj is None or armature_obj.type != 'ARMATURE':
        raise ValueError("A Blender armature object is required for NAD export")

    if action is None:
        if armature_obj.animation_data is not None:
            action = armature_obj.animation_data.action
    if action is None:
        raise ValueError(f"Armature '{armature_obj.name}' has no active Action to export")

    if nod_bones is None:
        nod_bones = reconstruct_export_bones(armature_obj)

    ordered_bones = order_blender_bones(armature_obj)
    bone_count = len(nod_bones)
    if bone_count != len(ordered_bones):
        raise ValueError(
            f"NOD bone count ({bone_count}) does not match Blender armature "
            f"bone count ({len(ordered_bones)})"
        )

    # Determine frame range
    if getattr(action, "use_frame_range", False):
        f_start = int(round(action.frame_start))
        f_end = int(round(action.frame_end))
    else:
        fr = action.frame_range
        f_start = int(round(fr[0]))
        f_end = int(round(fr[1]))

    if f_end < f_start:
        f_end = f_start

    frame_span = max(0, f_end - f_start)
    stored_duration = action.get("nad_duration")
    if stored_duration is not None:
        try:
            stored_val = float(stored_duration)
            if int(round(stored_val)) == frame_span:
                duration = stored_val
            else:
                duration = float(frame_span)
        except (TypeError, ValueError):
            duration = float(frame_span)
    else:
        duration = float(frame_span)

    step = max(1, int(frame_step))
    sample_blender_frames = list(range(f_start, f_end + 1, step))
    if not sample_blender_frames or sample_blender_frames[-1] != f_end:
        sample_blender_frames.append(f_end)

    nad_frames = [float(bf - f_start) for bf in sample_blender_frames]

    source_bind_world = _nod_bind_world_matrices(nod_bones)
    source_local_bind = _local_bind_matrices(nod_bones, source_bind_world)
    rest_translations = [mat.to_translation() for mat in source_local_bind]

    # Pose bones use armature space; exported binds/vertices use world space.
    # Include object and delta transforms on both sides of the deformation.
    reference_arm_world = armature_obj.matrix_world.copy()
    target_bind_world_inv = [
        (reference_arm_world @ b.matrix_local).inverted_safe()
        for b in ordered_bones
    ]

    rot_samples = [[] for _ in range(bone_count)]
    trans_samples = [[] for _ in range(bone_count)]
    prev_eulers = [None] * bone_count

    scene = context.scene
    orig_frame = scene.frame_current
    orig_pose_position = armature_obj.data.pose_position
    armature_obj.animation_data_create()
    anim_data = armature_obj.animation_data
    orig_action = anim_data.action
    orig_slot = getattr(anim_data, "action_slot", None)
    orig_use_nla = getattr(anim_data, "use_nla", False)

    try:
        armature_obj.data.pose_position = 'POSE'
        if hasattr(anim_data, "use_nla") and orig_use_nla:
            anim_data.use_nla = False
        anim_data.action = action
        if hasattr(anim_data, "action_slot") and getattr(action, "slots", None):
            suitable = list(
                getattr(anim_data, "action_suitable_slots", None)
                or [
                    s
                    for s in action.slots
                    if getattr(s, "target_id_type", "OBJECT") in ("OBJECT", "UNSPECIFIED")
                ]
            )
            if anim_data.action_slot is None or anim_data.action_slot not in suitable:
                if suitable:
                    anim_data.action_slot = suitable[0]

        for bf in sample_blender_frames:
            scene.frame_set(bf)
            pose_bones = armature_obj.pose.bones

            source_pose_world = []
            for i, b in enumerate(ordered_bones):
                pb = pose_bones[b.name]
                target_pose = armature_obj.matrix_world @ pb.matrix
                deformation = target_pose @ target_bind_world_inv[i]
                source_pose_world.append(deformation @ source_bind_world[i])

            for i, bone in enumerate(nod_bones):
                p_id = bone.parent_id
                if 0 <= p_id < bone_count:
                    local_pose = source_pose_world[p_id].inverted_safe() @ source_pose_world[i]
                else:
                    local_pose = source_pose_world[i]

                local_pose = rigid_export_matrix(
                    local_pose, f"Action '{action.name}', bone '{ordered_bones[i].name}', frame {bf}",
                )
                loc, quat, _ = local_pose.decompose()
                prev_eul = prev_eulers[i]
                if prev_eul is not None:
                    eul = quat.to_euler('XYZ', prev_eul)
                else:
                    eul = quat.to_euler('XYZ')
                prev_eulers[i] = eul

                rot_deg = (
                    math.degrees(eul.x),
                    math.degrees(eul.y),
                    math.degrees(eul.z),
                )
                rot_samples[i].append(rot_deg)

                offset_t = loc - rest_translations[i]
                trans_samples[i].append((float(offset_t.x), float(offset_t.y), float(offset_t.z)))
    finally:
        armature_obj.data.pose_position = orig_pose_position
        if hasattr(anim_data, "use_nla"):
            anim_data.use_nla = orig_use_nla
        anim_data.action = orig_action
        if hasattr(anim_data, "action_slot"):
            try:
                anim_data.action_slot = orig_slot
            except Exception:
                pass
        scene.frame_set(orig_frame)

    nad = NadFile()
    nad.version = int(action.get("nad_version", 3))
    nad.flags = int(action.get("nad_flags", 0))
    nad.duration = duration

    for i in range(bone_count):
        # Track 0: Rotation
        rot_track = NadBoneTrack()
        rot_track.bone_num = i
        rot_track.track_type = NAD_TRACK_ROTATION
        rot_track.keys = _compute_hermite_keys(nad_frames, rot_samples[i], use_smooth_tangents=use_smooth_tangents)
        rot_track.num_keys = len(rot_track.keys)
        nad.bone_tracks.append(rot_track)

        # Track 1: Translation (include if root bone or non-zero offset)
        has_translation = (
            nod_bones[i].parent_id < 0
            or any(
                abs(tx) > 1e-4 or abs(ty) > 1e-4 or abs(tz) > 1e-4
                for tx, ty, tz in trans_samples[i]
            )
        )
        if has_translation:
            trans_track = NadBoneTrack()
            trans_track.bone_num = i
            trans_track.track_type = NAD_TRACK_TRANSLATION
            trans_track.keys = _compute_hermite_keys(nad_frames, trans_samples[i], use_smooth_tangents=use_smooth_tangents)
            trans_track.num_keys = len(trans_track.keys)
            nad.bone_tracks.append(trans_track)

    nad.num_bone_tracks = len(nad.bone_tracks)

    # Export pose markers as NAD tags
    for marker in sorted(action.pose_markers, key=lambda m: m.frame):
        tag_type = _parse_marker_tag_type(marker.name)
        if tag_type is not None:
            tag_frame = max(0.0, float(marker.frame - f_start))
            nad.tags.append(NadTag(frame=tag_frame, tag_type=tag_type))
    nad.num_tags = len(nad.tags)

    debug_print(
        f"Exported Action '{action.name}' to NAD: {nad.num_bone_tracks} tracks, "
        f"{len(nad_frames)} frames, {nad.num_tags} tags, duration={nad.duration}"
    )
    return nad


def export_nad_file(
    filepath: str,
    context,
    armature_obj,
    action=None,
    nod_bones=None,
    frame_step: int = 1,
    use_smooth_tangents: bool = True,
    debug_log: bool = False,
) -> NadFile:
    nad_file = build_nad_from_action(
        context,
        armature_obj,
        action=action,
        nod_bones=nod_bones,
        frame_step=frame_step,
        use_smooth_tangents=use_smooth_tangents,
        debug_log=debug_log,
    )
    raw_bytes = nad_file.to_bytes()
    with open(filepath, "wb") as out_file:
        out_file.write(raw_bytes)
    return nad_file
