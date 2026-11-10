bl_info = {
    "name": "VTM Redemption NOD Importer/Exporter",
    "description": "Imports and exports Vampire: The Masquerade - Redemption NOD models and NAD animations",
    "author": "RK",
    "version": (1, 0, 1),
    "blender": (5, 2, 0),
    "location": "File > Import / Export > Nod (.nod, .nad, .nms)",
    "category": "Import-Export",
}

import bpy

from .nod_file_export import NodFileExport, menu_func_export
from .nod_file_import import NodFileImport, menu_func_import

classes = (
    NodFileImport,
    NodFileExport,
)


def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    from bpy.utils import unregister_class
    for cls in reversed(classes):
        unregister_class(cls)


if __name__ == "__main__":
    register()
