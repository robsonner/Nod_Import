import bpy
import os
from .nod_to_blender_utils import *
from .import_settings import ImportSettings
from .nad_to_blender import import_nad_file
from .nms_file import find_nms_for_nod, resolve_nms_animations

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

def read_data(context, filepath, settings: ImportSettings):
    in_file = open(filepath, 'rb')
    data = in_file.read()
    in_file.close()

    nodFile = LoadModel(data) 
    armature_obj = CreateMeshes(nodFile,settings)

    if settings.load_animation:
        nad_path = settings.animation_path.strip()
        if not nad_path:
            nad_path = os.path.splitext(filepath)[0] + ".nad"
        nad_path = bpy.path.abspath(nad_path)
        if not settings.load_bones:
            print("WARNING: NAD import skipped because Load Bones is disabled")
        elif settings.use_nms or settings.load_all_animations:
            animation_directory = os.path.dirname(nad_path)
            requested_nms_text = settings.nms_path.strip()
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
                print(f"Using NMS motion set: '{nms_path}'")
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
                      f"'{filepath}' in '{os.path.dirname(nad_path)}'")
            else:
                imported_actions = []
                preferred_action = None
                preferred_path = os.path.normcase(os.path.abspath(nad_path))
                for matching_path in nad_paths:
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

                active_action = preferred_action or imported_actions[0]
                armature_obj.animation_data.action = active_action
                context.scene.frame_start = 1
                context.scene.frame_end = max(
                    1, int(round(active_action["nad_duration"])) + 1
                )
                context.scene.frame_set(1)
                print(f"Imported {len(imported_actions)} matching NAD "
                      f"animations; active action: '{active_action.name}'")
        elif os.path.isfile(nad_path):
            import_nad_file(nad_path, armature_obj, nodFile.bones)
        else:
            print(f"WARNING: NAD animation file not found: '{nad_path}'")
    
    return {'FINISHED'}


# ImportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator

# Only needed if you want to add into a dynamic menu.
def menu_func_import(self, context):
    self.layout.operator(NodFileImport.bl_idname, text="Nod Import (.nod)")

class NodFileImport(Operator, ImportHelper):
    """This appears in the tooltip of the operator and in the generated docs"""
    bl_idname = "nod_import.data"  # important since its how bpy.ops.nod_import.data is constructed
    bl_label = "Import NOD file"

    # ImportHelper mixin class uses this
    filename_ext = ".nod"

    filter_glob: StringProperty(
        default="*.nod",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )


    # List of operator properties, the attributes will be assigned
    # to the class instance from the operator settings before calling.
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
                     "same name and directory as the NOD file"),
        subtype="FILE_PATH",
        default=("F:\\GOG Games\\Vampire The Masquerade - Redemption\\"
                 "ExtractedModels\\Christof_kneel.nad"),
    )

    textures_path: StringProperty(
        name="Textures path",
        description="Path to the folder in which the textures are located",
        subtype="DIR_PATH",
        default="C:/GOG Games/Vampire The Masquerade - Redemption/Extracted/Resource/3d/Materials/",
    )

#    type: EnumProperty(
#        name="Example Enum",
#        description="Choose between two items",
#        items=(
#            ('OPT_A', "First Option", "Description one"),
#            ('OPT_B', "Second Option", "Description two"),
#        ),
#        default='OPT_A',
#    )

    def execute(self, context):
        settings = ImportSettings(
            self.load_bones,
            self.textures_path,
            self.load_animation,
            self.animation_path,
            self.load_all_animations,
            self.use_bind_pose_positions,
            self.use_nms,
            self.nms_path,
        )
        return read_data(context, self.filepath, settings)
