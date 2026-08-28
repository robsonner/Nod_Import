import bpy
from .nod_to_blender_utils import *
from .import_settings import ImportSettings

def read_data(context, filepath, settings: ImportSettings):
    in_file = open(filepath, 'rb')
    data = in_file.read()
    in_file.close()

    nodFile = LoadModel(data) 
    CreateMeshes(nodFile,settings)
    
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
        return read_data(context, self.filepath, ImportSettings(self.load_bones, self.textures_path))
    