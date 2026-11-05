import os
import traceback

import bpy
from bpy.props import BoolProperty, StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper

from .debug_logging import debug_print, set_debug_logging
from .import_settings import ImportSettings
from .nad_to_blender import import_nad_file
from .nms_file import find_nms_for_nod, resolve_nms_animations
from .nod_to_blender_utils import CreateMeshes, LoadModel


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
        tex_dir = bpy.path.abspath(raw_textures_path)
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
    imported_meshes = [
        obj for obj in bpy.data.objects
        if obj not in existing_objs and obj.type == 'MESH'
    ]

    if settings.load_animation:
        anim_path_raw = settings.animation_path.strip() if settings.animation_path else ""
        if anim_path_raw:
            nad_path = bpy.path.abspath(anim_path_raw)
        else:
            nad_path = os.path.splitext(os.path.abspath(filepath))[0] + ".nad"
        animation_directory = os.path.dirname(nad_path)

        if not settings.load_bones:
            print("WARNING: NAD import skipped because Load Bones is disabled")
        elif settings.use_nms or settings.load_all_animations:
            requested_nms_text = settings.nms_path.strip() if settings.nms_path else ""
            requested_nms_path = (
                bpy.path.abspath(requested_nms_text)
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


def menu_func_import(self, context):
    self.layout.operator(NodFileImport.bl_idname, text="Nod Import (.nod)")


class NodFileImport(Operator, ImportHelper):
    """This appears in the tooltip of the operator and in the generated docs"""
    bl_idname = "nod_import.data"
    bl_label = "Import NOD file"
    bl_options = {'REGISTER', 'UNDO'}

    # ImportHelper mixin class uses this
    filename_ext = ".nod"

    filter_glob: StringProperty(
        default="*.nod",
        options={'HIDDEN'},
        maxlen=255,
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
        description=("Optional NMS file override; leave empty to look beside "
                     "the imported NOD using the same base filename"),
        subtype="FILE_PATH",
        default="",
    )

    animation_path: StringProperty(
        name="NAD Animation",
        description=("NAD animation file; leave empty to use a file with the "
                     "same base name or matching animations in the NOD directory"),
        subtype="FILE_PATH",
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
        subtype="DIR_PATH",
        default="",
    )

    def draw(self, context):
        layout = self.layout

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
