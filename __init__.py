bl_info = {
    "name": "VTM Redemption NOD Importer",
    "description": "Imports models from Vampire:The Masquerade-Redemption NOD format",
    "author": "RK",
    "version": (0, 1, 0),
    "blender": (5, 2, 0),
    "location": "File > Import > Nod Import (.nod)",
    "category": "Import-Export",
}

import bpy

from .nod_file_import import NodFileImport, menu_func_import

classes = (
    NodFileImport,
)


def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    from bpy.utils import unregister_class
    for cls in reversed(classes):
        unregister_class(cls)


if __name__ == "__main__":
    register()
