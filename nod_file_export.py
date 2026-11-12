import os
import traceback

import bpy
from bpy.props import BoolProperty, EnumProperty, IntProperty, StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ExportHelper

from .blender_to_nad import export_nad_file
from .blender_to_nod import collect_export_targets, export_nod_file, reconstruct_export_bones
from .export_settings import ExportSettings
from .nod_file_import import find_target_nod_armature


def _sanitize_filename(name: str) -> str:
    invalid = '<>:"/\\|?*\x00'
    cleaned = "".join("_" if c in invalid else c for c in (name or "animation"))
    return cleaned.strip() or "animation"


def _get_compatible_actions():
    return [
        act
        for act in bpy.data.actions
        if not getattr(act, "slots", None)
        or any(
            getattr(s, "target_id_type", "OBJECT") in ("OBJECT", "UNSPECIFIED")
            for s in act.slots
        )
    ]


class NodFileExport(Operator, ExportHelper):
    """Export a Vampire: The Masquerade - Redemption model (.nod) or skeletal animation (.nad)"""
    bl_idname = "nod_export.data"
    bl_label = "Export NOD / NAD"
    bl_options = {'REGISTER'}

    filename_ext = ".nod"
    check_extension = None

    filter_glob: StringProperty(
        default="*.nod;*.nad",
        options={'HIDDEN'},
        maxlen=255,
    )

    export_format: EnumProperty(
        name="Format",
        description="Choose whether to export a 3D model (.nod) or skeletal animation (.nad)",
        items=(
            ('NOD', "Model (.nod)", "Export 3D meshes, materials, skeleton and vertex weights to a .nod file"),
            ('NAD', "Animation (.nad)", "Export skeletal animation Action(s) from the armature to .nad file(s)"),
        ),
        default='NOD',
    )

    _last_format: str = 'NOD'

    # NOD model options
    selected_only: BoolProperty(
        name="Selected Objects Only",
        description="Export only selected mesh objects (and their armature)",
        default=False,
    )

    export_bones: BoolProperty(
        name="Export Bones & Skinning",
        description="Export the armature skeleton and vertex skin weights; disable to export as a static prop",
        default=True,
    )

    preserve_imported_bind_pose: BoolProperty(
        name="Preserve Imported NOD Bind Pose",
        description=(
            "Use original RestMatrixInverse matrices stored on imported NOD bones "
            "for 100% compatibility with existing game .nad animations"
        ),
        default=True,
    )

    # NAD animation options
    export_animations: BoolProperty(
        name="Export Animations (.nad)",
        description="Also export skeletal animation Action(s) to .nad file(s) alongside the .nod model",
        default=False,
    )

    animations_dir: StringProperty(
        name="Animations Folder",
        description=(
            "Optional folder for exported .nad files (absolute or relative to the .nod folder, "
            "e.g. ../Anims). Leave empty to save in the same folder as the .nod file"
        ),
        default="",
    )

    export_all_actions: BoolProperty(
        name="Export All Actions to Folder",
        description="Export every Action in the blend file onto the target directory as <action_name>.nad",
        default=False,
    )

    use_smooth_tangents: BoolProperty(
        name="Smooth Hermite Tangents",
        description="Compute smooth Catmull-Rom Hermite curve fitting factors (a, b, c) between keyframes",
        default=True,
    )

    frame_step: IntProperty(
        name="Frame Step",
        description="Keyframing step in frames when sampling the Blender Action",
        default=1,
        min=1,
        max=30,
    )

    debug_log: BoolProperty(
        name="Debug Logging",
        description="Print detailed NOD/NAD export diagnostics to the console",
        default=False,
    )

    def invoke(self, context, event):
        armature_obj = find_target_nod_armature(context)
        if not self.filepath:
            blend_filepath = context.blend_data.filepath
            if blend_filepath:
                base = os.path.splitext(blend_filepath)[0]
            elif armature_obj is not None and armature_obj.get("nod_model_name"):
                base = armature_obj.get("nod_model_name")
            else:
                base = "untitled"
            ext = ".nad" if self.export_format == 'NAD' else ".nod"
            self.filepath = base + ext
        self._last_format = self.export_format
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def check(self, context):
        changed = False
        filepath = self.filepath
        if not filepath:
            return False

        head, tail = os.path.split(filepath)
        if not tail:
            return False

        stem, ext = os.path.splitext(tail)
        ext_lower = ext.lower()

        # Detect if user switched the format toggle in the UI
        if self.export_format != getattr(self, "_last_format", self.export_format):
            self._last_format = self.export_format
            target_ext = ".nad" if self.export_format == 'NAD' else ".nod"
            if ext_lower != target_ext:
                self.filepath = os.path.join(head, (stem or "untitled") + target_ext)
                changed = True
            return changed

        # Detect if user typed .nad or .nod directly in the filename box
        if ext_lower == ".nad" and self.export_format != 'NAD':
            self.export_format = 'NAD'
            self._last_format = 'NAD'
            changed = True
        elif ext_lower == ".nod" and self.export_format != 'NOD':
            self.export_format = 'NOD'
            self._last_format = 'NOD'
            changed = True
        elif ext_lower not in (".nod", ".nad"):
            target_ext = ".nad" if self.export_format == 'NAD' else ".nod"
            self.filepath = os.path.join(head, tail + target_ext)
            changed = True

        return changed

    def _effective_mode(self) -> str:
        ext = os.path.splitext(self.filepath or "")[1].lower()
        if ext == ".nad":
            return 'NAD'
        if ext == ".nod":
            return 'NOD'
        return self.export_format

    def draw(self, context):
        layout = self.layout
        layout.row().prop(self, "export_format", expand=True)

        mode = self._effective_mode()
        if mode == 'NAD':
            armature_obj = find_target_nod_armature(context)
            box = layout.box()
            box.label(text="Target Armature")
            if armature_obj is not None:
                box.label(
                    text=f"{armature_obj.name} ({len(armature_obj.data.bones)} bones)",
                    icon='ARMATURE_DATA',
                )
                act = armature_obj.animation_data.action if armature_obj.animation_data else None
                if act is not None:
                    box.label(text=f"Active Action: {act.name}", icon='ACTION')
                elif not self.export_all_actions:
                    box.label(text="No active Action assigned!", icon='ERROR')
            else:
                box.label(text="No armature in scene / selected!", icon='ERROR')

            box_anim = layout.box()
            box_anim.label(text="Animation Export")
            box_anim.prop(self, "export_all_actions")
            box_anim.prop(self, "use_smooth_tangents")
            box_anim.prop(self, "frame_step")
        else:
            box_scope = layout.box()
            box_scope.label(text="Geometry")
            box_scope.prop(self, "selected_only")

            box_skel = layout.box()
            box_skel.label(text="Skeleton")
            box_skel.prop(self, "export_bones")
            sub = box_skel.column()
            sub.enabled = self.export_bones
            sub.prop(self, "preserve_imported_bind_pose")

            box_anim = layout.box()
            box_anim.enabled = self.export_bones
            box_anim.label(text="Animation Export")
            box_anim.prop(self, "export_animations")
            if self.export_animations:
                sub_anim = box_anim.column()
                sub_anim.prop(self, "export_all_actions")
                sub_anim.prop(self, "animations_dir")
                sub_anim.prop(self, "use_smooth_tangents")
                sub_anim.prop(self, "frame_step")

        layout.prop(self, "debug_log")

    def _resolve_animations_out_dir(self, nod_filepath: str) -> str:
        nod_dir = os.path.dirname(nod_filepath) or "."
        raw_dir = (self.animations_dir or "").strip()
        if not raw_dir:
            return nod_dir
        if os.path.isabs(raw_dir):
            return os.path.normpath(raw_dir)
        return os.path.normpath(os.path.join(nod_dir, raw_dir))

    def execute(self, context):
        active_obj = getattr(getattr(context, "view_layer", None), "objects", None)
        active_obj = getattr(active_obj, "active", None)
        if active_obj is not None and active_obj.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        mode = self._effective_mode()
        filepath = os.path.abspath(self.filepath)
        ext = os.path.splitext(filepath)[1].lower()
        if mode == 'NAD' and ext != ".nad":
            filepath = os.path.splitext(filepath)[0] + ".nad"
        elif mode == 'NOD' and ext != ".nod":
            filepath = os.path.splitext(filepath)[0] + ".nod"

        try:
            if mode == 'NAD':
                armature_obj = find_target_nod_armature(context)
                if armature_obj is None:
                    self.report(
                        {'ERROR'},
                        "No target NOD armature found. Select an armature (or its mesh) first",
                    )
                    return {'CANCELLED'}

                nod_bones = reconstruct_export_bones(armature_obj)
                if self.export_all_actions:
                    out_dir = os.path.dirname(filepath) or "."
                    actions = _get_compatible_actions()
                    if not actions:
                        self.report({'ERROR'}, "No compatible object Actions found in blend file to export")
                        return {'CANCELLED'}
                    exported_count = 0
                    for act in actions:
                        out_name = _sanitize_filename(act.name) + ".nad"
                        out_path = os.path.join(out_dir, out_name)
                        export_nad_file(
                            out_path,
                            context,
                            armature_obj,
                            action=act,
                            nod_bones=nod_bones,
                            frame_step=self.frame_step,
                            use_smooth_tangents=self.use_smooth_tangents,
                            debug_log=self.debug_log,
                        )
                        exported_count += 1
                    self.report({'INFO'}, f"Exported {exported_count} NAD animation(s) to '{out_dir}'")
                else:
                    export_nad_file(
                        filepath,
                        context,
                        armature_obj,
                        action=None,
                        nod_bones=nod_bones,
                        frame_step=self.frame_step,
                        use_smooth_tangents=self.use_smooth_tangents,
                        debug_log=self.debug_log,
                    )
                    self.report({'INFO'}, f"Exported NAD animation to '{filepath}'")
                return {'FINISHED'}

            # NOD model export
            settings = ExportSettings(
                export_bones=self.export_bones,
                preserve_imported_bind_pose=self.preserve_imported_bind_pose,
                selected_only=self.selected_only,
                model_version=7,
                debug_log=self.debug_log,
            )
            nod_file = export_nod_file(filepath, context, settings=settings)

            if self.export_bones and self.export_animations:
                armature_obj, _ = collect_export_targets(context, settings)
                if armature_obj is None:
                    armature_obj = find_target_nod_armature(context)
                if armature_obj is None or not nod_file.bones:
                    self.report(
                        {'WARNING'},
                        f"Exported NOD model to '{filepath}', but skipped NAD export (no armature/bones found)",
                    )
                    return {'FINISHED'}

                anim_out_dir = self._resolve_animations_out_dir(filepath)
                os.makedirs(anim_out_dir, exist_ok=True)

                if self.export_all_actions:
                    actions = _get_compatible_actions()
                    if not actions:
                        self.report(
                            {'WARNING'},
                            f"Exported NOD model to '{filepath}', but found no Actions to export",
                        )
                        return {'FINISHED'}
                    exported_count = 0
                    for act in actions:
                        out_name = _sanitize_filename(act.name) + ".nad"
                        out_path = os.path.join(anim_out_dir, out_name)
                        export_nad_file(
                            out_path,
                            context,
                            armature_obj,
                            action=act,
                            nod_bones=nod_file.bones,
                            frame_step=self.frame_step,
                            use_smooth_tangents=self.use_smooth_tangents,
                            debug_log=self.debug_log,
                        )
                        exported_count += 1
                    self.report(
                        {'INFO'},
                        f"Exported NOD model to '{filepath}' and {exported_count} NAD animation(s) to '{anim_out_dir}'",
                    )
                else:
                    act = armature_obj.animation_data.action if armature_obj.animation_data else None
                    if act is None:
                        self.report(
                            {'WARNING'},
                            f"Exported NOD model to '{filepath}', but armature has no active Action to export",
                        )
                        return {'FINISHED'}
                    out_name = _sanitize_filename(act.name) + ".nad"
                    out_path = os.path.join(anim_out_dir, out_name)
                    export_nad_file(
                        out_path,
                        context,
                        armature_obj,
                        action=act,
                        nod_bones=nod_file.bones,
                        frame_step=self.frame_step,
                        use_smooth_tangents=self.use_smooth_tangents,
                        debug_log=self.debug_log,
                    )
                    self.report(
                        {'INFO'},
                        f"Exported NOD model to '{filepath}' and NAD animation to '{out_path}'",
                    )
                return {'FINISHED'}

            self.report(
                {'INFO'},
                f"Exported NOD model to '{filepath}' "
                f"({len(nod_file.mesh_groups)} groups, {len(nod_file.bones)} bones)",
            )
            return {'FINISHED'}
        except Exception as exc:
            traceback.print_exc()
            self.report({'ERROR'}, f"NOD/NAD export failed: {exc}")
            return {'CANCELLED'}


def menu_func_export(self, context):
    self.layout.operator(NodFileExport.bl_idname, text="Nod Export (.nod, .nad)")
