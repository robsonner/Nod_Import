bl_info = {
    "name": "Nod Import/Export plugin",
    "description": "Imports/Exports models from/to Vampire:The Masquerade-Redemption NOD format",
    "author": "RK",
    "category": "Import-Export",
    "version": (0, 0, 3),
    "blender": (3, 6, 0)
}

import bpy

from .nod_file_import import *
#from .nod_import import TestPanel
#from .nod_import import LoadNodFileOperator

classes = {
#    TestPanel,
#    LoadNodFileOperator,
    NodFileImport
}

def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
    #add to nod import to menu
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
    from bpy.utils import unregister_class
    for cls in classes:
        unregister_class(cls)
     #remove to nod import to menu
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

if __name__ == "__main__":
    register()
    #in_file = open("F:\GOG Games\Vampire The Masquerade - Redemption\ExtractedModels\christof.nod", "rb") # opening for [r]eading as [b]inary
    #data = in_file.read()
    #in_file.close()
    #LoadModel(data)

#def LoadModel(data):
#    bs = BinaryReader(data, "little") #the files are in little-endian
#    nod_file = NodFile(bs) 
#    print("We read everything, now position of buffer: ",bs.position," and length: ", bs.length)
""""


#from . binary_reader import BinaryReader
#from . vector3 import Vector3
#from . vector2 import Vector2
#from . nod_vertex import NodVertex
#from . nod_face import NodFace
#from . nod_file import NodFile


#classes = {
 #   BinaryReader
#}

def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)

def unregister():
    from bpy.utils import unregister_class
    for cls in classes:
        unregister_class(cls)
"""

