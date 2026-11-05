# VTM Redemption NOD Importer

Blender 5.2+ extension and add-on for importing 3D models and skeletal animations from *Vampire: The Masquerade – Redemption* (`.nod`, `.nad`, and `.nms` files).

## Features

- **Meshes & Geometry:** Imports multi-group geometry with UV texture coordinates, custom split normals, and LOD handling.
- **Materials & Textures:** Automatic material generation with Principled BSDF shader nodes and `.tga` texture lookup (supporting `Materials/`, `../Materials/`, or the NOD file directory).
- **Armature & Rigging:** Full skeleton generation from NOD bone hierarchies, true bind-pose transforms via `RestMatrixInverse`, and vertex weight group assignments.
- **NAD Skeletal Animations:** Imports `.nad` animation clips into Blender Actions (compatible with Blender 5.2 layered animation and action slots), sets scene timeline frame ranges (30 FPS), and imports animation tag event markers.
- **NMS Motion Sets:** Supports `.nms` motion set scripts to resolve and batch-import associated animation sets.

## Requirements

- **Blender 5.2 LTS or newer** (tested on Blender 5.2.1 LTS with Python 3.13).

## Installation

### (a) Installing from Extension ZIP
1. In Blender, navigate to **Edit > Preferences > Get Extensions**.
2. Click the menu dropdown in the top-right corner and select **Install from Disk...**.
3. Choose `nod_import-0.1.0.zip` (located in the `dist/` directory).

Alternatively, install via the Blender command-line interface:
```powershell
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --command extension install-file -r user_default -e dist\nod_import-0.1.0.zip
```

### (b) Building the Extension ZIP from Source
To build the distribution ZIP archive from the repository root:
```powershell
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --command extension build --source-dir . --output-dir dist
```

## Import Options

Access the importer from **File > Import > Nod Import (.nod)**. The operator exposes the following settings:

### Skeleton
- **Load Bones** (`load_bones`): Whether to load the armature skeleton and vertex groups (default: `True`).
- **Use NOD Bind Positions** (`use_bind_pose_positions`): Place bone heads at joint pivots calculated from `RestMatrixInverse`. Disable to fallback to legacy weighted vertex centroids (default: `True`).

### Animation
- **Load NAD Animation** (`load_animation`): Import NAD animations onto the imported armature (default: `True`).
- **Use NMS Motion Set** (`use_nms`): Use an NMS motion set to select animations; when no path is provided, searches for `<model name>.nms` beside the NOD file (default: `True`).
- **NMS Motion Set** (`nms_path`): Optional file path override for the `.nms` motion set file.
- **Load All Matching NAD Animations** (`load_all_animations`): When NMS is disabled or unavailable, loads every `<NOD name>_*.nad` file from the animation directory as a separate Action (default: `True`).
- **NAD Animation** (`animation_path`): File path override for a specific `.nad` animation file; leave empty to auto-detect matching files.

### Materials
- **Textures path** (`textures_path`): Directory path for textures; leave empty to search `Materials/`, `../Materials/`, or the NOD file directory.

### Diagnostics
- **Debug Logging** (`debug_log`): Print detailed mesh, skeleton, and animation diagnostic messages to the console (default: `False`).

## Development & Testing

### Running Unit Tests
Unit tests run independently of Blender using standard pytest:
```powershell
python -m pytest tests -q
```

### Running Blender Headless Smoke Test
Run the end-to-end headless integration smoke test with Blender 5.2:
```powershell
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b --factory-startup --python-exit-code 1 --python tests\blender_smoke_test.py
```
You can optionally set the `NOD_TEST_FILE` environment variable to test against a different model:
```powershell
$env:NOD_TEST_FILE = "path\to\model.nod"
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b --factory-startup --python-exit-code 1 --python tests\blender_smoke_test.py
```

### Format Documentation
Reverse-engineering specifications and HTML documentation can be found in the `Docs/` directory.

## Limitations

- **Import only:** Exporting Blender models back to NOD/NAD format is not supported.
- Unhandled format variations or edge cases from unofficial game modifications may require further adjustments.

## TODO

- Exporting models and animations back to `.nod` / `.nad` format.

## License

This project is licensed under the GNU General Public License v3.0 or later ([GPL-3.0-or-later](LICENSE)).
