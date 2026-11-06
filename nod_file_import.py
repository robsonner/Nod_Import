import os
import traceback

import bpy
from bpy.props import BoolProperty, CollectionProperty, StringProperty
from bpy.types import Operator, OperatorFileListElement
from bpy_extras.io_utils import ImportHelper

from .debug_logging import debug_print, set_debug_logging
from .import_settings import ImportSettings
from .nad_to_blender import import_nad_file, reconstruct_nod_bones_from_armature
from .nms_file import find_nms_for_nod, resolve_nms_animations
from .nod_to_blender_utils import CreateMeshes, LoadModel


def _resolve_user_path(raw_path, base_dir):
    text = raw_path.strip() if raw_path else ""
    if not text:
        return ""
    if text.startswith("//"):
        return os.path.abspath(bpy.path.abspath(text))
    if os.path.isabs(text):
        return os.path.abspath(text)
    candidate_in_base = os.path.abspath(os.path.join(base_dir, text))
    if os.path.exists(candidate_in_base) or not os.path.exists(text):
        return candidate_in_base
    return os.path.abspath(text)


def find_matching_nad_files(nod_path, animation_path=""):
    """Find <NOD name>_*.nad files without relying on case-sensitive glob."""
    if animation_path:
        animation_directory = os.path.dirname(animation_path)
    else:
        animation_directory = os.path.dirname(nod_path)
    if not animation_directory:
        animation_directory = "."

    nod_name = os.path.splitext(os.path.basename(nod_path))[0]
    prefix = (nod_name + "_").lower()
    try:
        filenames = os.listdir(animation_directory)
    except OSError as error:
        print(f"WARNING: cannot scan NAD directory "
              f"'{animation_directory}': {error}")
        return []

    matching = [
        os.path.join(animation_directory, filename)
        for filename in filenames
        if filename.lower().startswith(prefix)
        and filename.lower().endswith(".nad")
    ]
    return sorted(matching, key=lambda path: os.path.basename(path).lower())


def _activate_action(context, armature_obj, action):
    if armature_obj is None or action is None:
        return
    if armature_obj.animation_data is None:
        armature_obj.animation_data_create()
    anim_data = armature_obj.animation_data
    anim_data.action = action
    if hasattr(anim_data, "action_slot") and anim_data.action_slot is None:
        if hasattr(action, "slots") and len(action.slots) > 0:
            anim_data.action_slot = action.slots[0]
    scene = context.scene
    scene.render.fps = 30
    scene.render.fps_base = 1.0
    scene.frame_start = 1
    duration = action.get("nad_duration", 0)
    try:
        dur_val = float(duration)
    except (TypeError, ValueError):
        dur_val = 0.0
    scene.frame_end = max(1, round(dur_val) + 1)
    scene.frame_set(1)


def read_data(context, filepath, settings: ImportSettings, report=None):
    def _report(level_set, message):
        if report is not None:
            report(level_set, message)
        else:
            lvl = list(level_set)[0] if level_set else "INFO"
            print(f"{lvl}: {message}")

    set_debug_logging(settings.debug_log)

    nod_dir = os.path.dirname(os.path.abspath(filepath))

    # Resolve texture directory path
    raw_textures_path = getattr(settings, "textures_path", None)
    if raw_textures_path is None:
        raw_textures_path = getattr(settings, "textures_dir_path", "")
    raw_textures_path = raw_textures_path.strip() if raw_textures_path else ""

    if raw_textures_path:
        tex_dir = _resolve_user_path(raw_textures_path, nod_dir)
        resolved_tex_dir = os.path.join(tex_dir, "") if tex_dir else ""
    else:
        candidates = [
            os.path.join(nod_dir, "Materials"),
            os.path.normpath(os.path.join(nod_dir, "..", "Materials")),
            nod_dir,
        ]
        resolved_tex_dir = ""
        for cand in candidates:
            if os.path.isdir(cand):
                try:
                    entries = os.listdir(cand)
                except OSError:
                    entries = []
                if any(e.lower().endswith(".tga") for e in entries):
                    resolved_tex_dir = os.path.join(cand, "")
                    break
        if not resolved_tex_dir:
            debug_print(f"No texture directory with .tga files found for '{filepath}'")

    settings.textures_dir_path = resolved_tex_dir
    if hasattr(settings, "textures_path"):
        settings.textures_path = resolved_tex_dir

    with open(filepath, 'rb') as in_file:
        data = in_file.read()

    nodFile = LoadModel(data)

    existing_objs = set(bpy.data.objects)
    armature_obj = CreateMeshes(nodFile, settings)
    if armature_obj is not None:
        armature_obj["nod_source_path"] = os.path.abspath(filepath)
        armature_obj["nod_model_name"] = os.path.splitext(os.path.basename(filepath))[0]
    imported_meshes = [
        obj for obj in bpy.data.objects
        if obj not in existing_objs and obj.type == 'MESH'
    ]

    if settings.load_animation:
        anim_path_raw = settings.animation_path.strip() if settings.animation_path else ""
        if anim_path_raw:
            nad_path = _resolve_user_path(anim_path_raw, nod_dir)
        else:
            nad_path = os.path.splitext(os.path.abspath(filepath))[0] + ".nad"
        animation_directory = os.path.dirname(nad_path)

        if not settings.load_bones:
            print("WARNING: NAD import skipped because Load Bones is disabled")
        elif settings.use_nms or settings.load_all_animations:
            requested_nms_text = settings.nms_path.strip() if settings.nms_path else ""
            requested_nms_path = (
                _resolve_user_path(requested_nms_text, nod_dir)
                if requested_nms_text else ""
            )
            nms_path = None
            nms_metadata = {}
            if settings.use_nms:
                nms_path = find_nms_for_nod(filepath, requested_nms_path)

            if settings.use_nms and nms_path:
                nad_paths, nms_metadata = resolve_nms_animations(
                    nms_path, animation_directory
                )
                debug_print(f"Using NMS motion set: '{nms_path}'")
            else:
                nad_paths = find_matching_nad_files(filepath, nad_path)
                if settings.use_nms:
                    expected_path = (requested_nms_path or
                                     os.path.splitext(filepath)[0] + ".nms")
                    print(f"WARNING: NMS motion set not found: "
                          f"'{expected_path}'; using NAD filename-prefix "
                          "fallback")
            if not nad_paths:
                print(f"WARNING: no matching NAD animations found for "
                      f"'{filepath}' in '{animation_directory}'")
            else:
                imported_actions = []
                preferred_action = None
                preferred_path = os.path.normcase(os.path.abspath(nad_path))
                skipped_count = 0
                total_count = len(nad_paths)
                for matching_path in nad_paths:
                    try:
                        action = import_nad_file(
                            matching_path, armature_obj, nodFile.bones
                        )
                        metadata_key = os.path.normcase(
                            os.path.abspath(matching_path)
                        )
                        motion_entries = nms_metadata.get(metadata_key, [])
                        if motion_entries:
                            action["nms_source"] = nms_path
                            action["nms_motion_modes"] = ",".join(
                                entry.mode for entry in motion_entries
                            )
                            action["nms_flags"] = ",".join(sorted({
                                flag.lower()
                                for entry in motion_entries
                                for flag in entry.flags
                            }))
                        imported_actions.append(action)
                        if os.path.normcase(os.path.abspath(matching_path)) == preferred_path:
                            preferred_action = action
                    except Exception as nad_err:
                        traceback.print_exc()
                        skipped_count += 1
                        print(f"ERROR: Failed to import NAD '{matching_path}': {nad_err}")

                if skipped_count > 0:
                    _report({'WARNING'}, f"Skipped {skipped_count} of {total_count} NAD animations (see console)")

                if imported_actions:
                    active_action = preferred_action or imported_actions[0]
                    _activate_action(context, armature_obj, active_action)
                    debug_print(f"Imported {len(imported_actions)} matching NAD "
                                f"animations; active action: "
                                f"'{active_action.name}'")
        elif os.path.isfile(nad_path):
            try:
                action = import_nad_file(nad_path, armature_obj, nodFile.bones)
                if action:
                    _activate_action(context, armature_obj, action)
                    debug_print(f"Imported single NAD animation: '{action.name}'")
                else:
                    _report({'WARNING'}, "Skipped 1 of 1 NAD animations (see console)")
            except Exception as nad_err:
                traceback.print_exc()
                print(f"ERROR: Failed to import NAD '{nad_path}': {nad_err}")
                _report({'WARNING'}, "Skipped 1 of 1 NAD animations (see console)")
        else:
            print(f"WARNING: NAD animation file not found: '{nad_path}'")

    # Selection after import: armature (or first mesh) active and selected, meshes selected
    if hasattr(context, "selected_objects"):
        for obj in list(context.selected_objects):
            obj.select_set(False)

    for mesh_obj in imported_meshes:
        mesh_obj.select_set(True)

    view_layer_objects = getattr(getattr(context, "view_layer", None), "objects", None)
    if armature_obj is not None:
        armature_obj.select_set(True)
        if view_layer_objects is not None:
            view_layer_objects.active = armature_obj
    elif imported_meshes:
        first_mesh = imported_meshes[0]
        first_mesh.select_set(True)
        if view_layer_objects is not None:
            view_layer_objects.active = first_mesh

    return {'FINISHED'}


def _armature_from_object(obj):
    if obj is None:
        return None
    if obj.type == 'ARMATURE':
        return obj
    if obj.type == 'MESH':
        if obj.parent is not None and obj.parent.type == 'ARMATURE':
            return obj.parent
        for mod in obj.modifiers:
            if mod.type == 'ARMATURE' and mod.object is not None:
                return mod.object
    return None


def find_target_nod_armature(context):
    """Find the target NOD armature from active object, selection, or scene."""
    view_layer_objs = getattr(getattr(context, "view_layer", None), "objects", None)
    active = getattr(view_layer_objs, "active", None) or getattr(context, "active_object", None)
    arm = _armature_from_object(active)
    if arm is not None:
        return arm

    for obj in getattr(context, "selected_objects", []) or []:
        arm = _armature_from_object(obj)
        if arm is not None:
            return arm

    scene = getattr(context, "scene", None)
    if scene is not None:
        scene_armatures = [obj for obj in scene.objects if obj.type == 'ARMATURE']
        if len(scene_armatures) == 1:
            return scene_armatures[0]
    return None


def import_animations_to_armature(
    context,
    armature_obj,
    filepath,
    files=None,
    directory="",
    load_all_matching=False,
    debug_log=False,
    report=None,
):
    """Import one or more NAD or NMS animations onto an existing NOD armature."""
    def _report(level_set, message):
        if report is not None:
            report(level_set, message)
        else:
            lvl = list(level_set)[0] if level_set else "INFO"
            print(f"{lvl}: {message}")

    set_debug_logging(debug_log)

    if armature_obj is None or armature_obj.type != 'ARMATURE':
        raise ValueError("Select an imported NOD armature (or one of its meshes) first")

    nod_bones = reconstruct_nod_bones_from_armature(armature_obj)

    base_dir = directory or os.path.dirname(os.path.abspath(filepath))
    selected_paths = []
    if files:
        for file_elem in files:
            name = getattr(file_elem, "name", "")
            if name:
                candidate = os.path.join(base_dir, name)
                if os.path.isfile(candidate):
                    selected_paths.append(os.path.abspath(candidate))
    if not selected_paths and filepath:
        abs_fp = os.path.abspath(filepath)
        if os.path.isfile(abs_fp):
            selected_paths.append(abs_fp)

    if not selected_paths:
        raise FileNotFoundError(f"Animation file not found: '{filepath}'")

    nad_queue = []
    nms_metadata_by_path = {}
    nms_source_by_path = {}
    seen_paths = set()

    def _enqueue_nad(path, nms_src=None, motion_entries=None):
        norm = os.path.normcase(os.path.abspath(path))
        if norm not in seen_paths:
            seen_paths.add(norm)
            nad_queue.append(path)
        if nms_src:
            nms_source_by_path[norm] = nms_src
        if motion_entries:
            nms_metadata_by_path[norm] = motion_entries

    nod_source_path = armature_obj.get("nod_source_path", "")
    nod_source_dir = os.path.dirname(nod_source_path) if nod_source_path else ""

    for sel_path in selected_paths:
        ext = os.path.splitext(sel_path)[1].lower()
        sel_dir = os.path.dirname(sel_path)
        if ext == ".nms":
            nad_paths, nms_meta = resolve_nms_animations(
                sel_path, nod_source_dir or sel_dir
            )
            for p in nad_paths:
                norm_p = os.path.normcase(os.path.abspath(p))
                _enqueue_nad(p, nms_src=sel_path, motion_entries=nms_meta.get(norm_p, []))
        elif load_all_matching and len(selected_paths) == 1:
            model_name = armature_obj.get("nod_model_name", "")
            if not model_name:
                stem = os.path.splitext(os.path.basename(sel_path))[0]
                model_name = stem.split("_", 1)[0]
            pseudo_nod = os.path.join(sel_dir, model_name + ".nod")
            for p in find_matching_nad_files(pseudo_nod, sel_path):
                _enqueue_nad(p)
            if not nad_queue:
                _enqueue_nad(sel_path)
        else:
            _enqueue_nad(sel_path)

    if not nad_queue:
        _report({'WARNING'}, f"No NAD animations found for '{filepath}'")
        return {'CANCELLED'}

    imported_actions = []
    preferred_action = None
    preferred_norm = os.path.normcase(os.path.abspath(selected_paths[0]))
    skipped_count = 0
    total_count = len(nad_queue)

    for nad_path in nad_queue:
        try:
            action = import_nad_file(nad_path, armature_obj, nod_bones)
            norm_key = os.path.normcase(os.path.abspath(nad_path))
            motion_entries = nms_metadata_by_path.get(norm_key, [])
            if motion_entries:
                action["nms_source"] = nms_source_by_path.get(norm_key, "")
                action["nms_motion_modes"] = ",".join(
                    entry.mode for entry in motion_entries
                )
                action["nms_flags"] = ",".join(sorted({
                    flag.lower()
                    for entry in motion_entries
                    for flag in entry.flags
                }))
            imported_actions.append(action)
            if norm_key == preferred_norm:
                preferred_action = action
        except Exception as nad_err:
            traceback.print_exc()
            skipped_count += 1
            print(f"ERROR: Failed to import NAD '{nad_path}': {nad_err}")

    if skipped_count > 0:
        _report({'WARNING'}, f"Skipped {skipped_count} of {total_count} NAD animations (see console)")

    if not imported_actions:
        return {'CANCELLED'}

    active_action = preferred_action or imported_actions[0]
    _activate_action(context, armature_obj, active_action)
    debug_print(
        f"Imported {len(imported_actions)} NAD animation(s) onto "
        f"'{armature_obj.name}'; active action: '{active_action.name}'"
    )
    return {'FINISHED'}


def menu_func_import(self, context):
    self.layout.operator(NodFileImport.bl_idname, text="Nod Import (.nod, .nad, .nms)")


class NodFileImport(Operator, ImportHelper):
    """Import a Vampire: The Masquerade - Redemption model (.nod) or animation (.nad, .nms)"""
    bl_idname = "nod_import.data"
    bl_label = "Import NOD / NAD / NMS"
    bl_options = {'REGISTER', 'UNDO'}

    # ImportHelper mixin class uses this
    filename_ext = ".nod"

    filter_glob: StringProperty(
        default="*.nod;*.nad;*.nms",
        options={'HIDDEN'},
        maxlen=255,
    )

    files: CollectionProperty(
        name="File Path",
        type=OperatorFileListElement,
        options={'SKIP_SAVE'},
    )

    directory: StringProperty(
        subtype='DIR_PATH',
        options={'HIDDEN', 'SKIP_SAVE'},
    )

    load_bones: BoolProperty(
        name="Load Bones",
        description="Should bones be loaded",
        default=True,
    )

    use_bind_pose_positions: BoolProperty(
        name="Use NOD Bind Positions",
        description=("Place bone heads at joint pivots from RestMatrixInverse; "
                     "disable to use legacy weighted vertex centroids"),
        default=True,
    )

    load_animation: BoolProperty(
        name="Load NAD Animation",
        description="Import a NAD animation onto the imported armature",
        default=True,
    )

    load_all_animations: BoolProperty(
        name="Load All Matching NAD Animations",
        description=("When NMS is disabled or unavailable, load every "
                     "<NOD name>_*.nad file from the NAD animation "
                     "directory as a separate Action"),
        default=True,
    )

    use_nms: BoolProperty(
        name="Use NMS Motion Set",
        description=("Use an NMS motion set to select animations; when no "
                     "path is provided, use <model name>.nms beside the NOD"),
        default=True,
    )

    nms_path: StringProperty(
        name="NMS Motion Set",
        description=("Optional NMS file path or filename override; leave empty "
                     "to look beside the imported NOD using the same base filename"),
        default="",
    )

    animation_path: StringProperty(
        name="NAD Animation",
        description=("NAD animation file path or filename; leave empty to use "
                     "a file with the same base name or matching animations in the NOD directory"),
        default="",
    )

    debug_log: BoolProperty(
        name="Debug Logging",
        description=("Print detailed NOD mesh, skeleton and animation "
                     "diagnostics to the console"),
        default=False,
    )

    textures_path: StringProperty(
        name="Textures path",
        description=("Path to textures folder; leave empty to search "
                     "Materials/, ../Materials/ or the NOD directory"),
        default="",
    )

    def _selected_extensions(self):
        exts = set()
        if self.files:
            for f in self.files:
                name = getattr(f, "name", "")
                if name:
                    ext = os.path.splitext(name)[1].lower()
                    if ext:
                        exts.add(ext)
        if not exts and self.filepath:
            ext = os.path.splitext(self.filepath)[1].lower()
            if ext:
                exts.add(ext)
        return exts

    def _is_animation_only_selection(self):
        exts = self._selected_extensions()
        return bool(exts) and exts.issubset({".nad", ".nms"})

    def draw(self, context):
        layout = self.layout

        if self._is_animation_only_selection():
            armature_obj = find_target_nod_armature(context)
            box = layout.box()
            box.label(text="Target Armature (Animation Import)")
            if armature_obj is not None:
                box.label(
                    text=f"{armature_obj.name} ({len(armature_obj.data.bones)} bones)",
                    icon='ARMATURE_DATA',
                )
            else:
                box.label(text="No armature in scene / selected!", icon='ERROR')
            layout.prop(self, "debug_log")
            return

        # Skeleton section
        box = layout.box()
        box.label(text="Skeleton")
        box.prop(self, "load_bones")
        sub_bones = box.column()
        sub_bones.enabled = self.load_bones
        sub_bones.prop(self, "use_bind_pose_positions")

        # Animation section
        box = layout.box()
        box.label(text="Animation")
        row_anim = box.row()
        row_anim.enabled = self.load_bones
        row_anim.prop(self, "load_animation")
        col_anim = box.column()
        col_anim.enabled = self.load_bones and self.load_animation
        col_anim.prop(self, "use_nms")
        sub_nms = col_anim.column()
        sub_nms.enabled = self.use_nms
        sub_nms.prop(self, "nms_path")
        col_anim.prop(self, "load_all_animations")
        col_anim.prop(self, "animation_path")

        # Materials section
        box = layout.box()
        box.label(text="Materials")
        box.prop(self, "textures_path")

        # Debug logging
        layout.prop(self, "debug_log")

    def execute(self, context):
        active_obj = getattr(getattr(context, "view_layer", None), "objects", None)
        active_obj = getattr(active_obj, "active", None)
        if active_obj is not None and active_obj.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        if self._is_animation_only_selection():
            armature_obj = find_target_nod_armature(context)
            if armature_obj is None:
                self.report(
                    {'ERROR'},
                    "No target NOD armature found. Select an armature (or its mesh) first",
                )
                return {'CANCELLED'}
            try:
                return import_animations_to_armature(
                    context,
                    armature_obj,
                    self.filepath,
                    files=self.files,
                    directory=self.directory,
                    load_all_matching=False,
                    debug_log=self.debug_log,
                    report=self.report,
                )
            except Exception as exc:
                traceback.print_exc()
                self.report({'ERROR'}, f"NAD animation import failed: {exc}")
                return {'CANCELLED'}

        settings = ImportSettings(
            self.load_bones,
            self.textures_path,
            self.load_animation,
            self.animation_path,
            self.load_all_animations,
            self.use_bind_pose_positions,
            self.use_nms,
            self.nms_path,
            self.debug_log,
            nod_path=self.filepath,
        )
        try:
            return read_data(context, self.filepath, settings, report=self.report)
        except Exception as exc:
            traceback.print_exc()
            self.report({'ERROR'}, f"NOD import failed: {exc}")
            return {'CANCELLED'}
