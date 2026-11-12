# VTM Redemption NOD Importer / Exporter

Blender 5.2+ extension and add-on for importing and exporting 3D models and skeletal animations from *Vampire: The Masquerade – Redemption* (`.nod`, `.nad`, and `.nms` files).

## Features

- **Meshes & Geometry (Import & Export):** Multi-group geometry with UV texture coordinates, custom split normals, automatic triangulation, and UV/normal seam splitting on export.
- **Materials & Textures:** Automatic material generation with Principled BSDF shader nodes, `.nam` (*Nihilistic Animated Material*) parsing (`Twosided`, `Masked` 1-bit alpha, texture redirection, and `_dbl` suffix fallback), and `.tga` texture lookup (`1) .nod folder`, `2) Materials/`, `3) ../Materials/`).
- **Armature & Rigging (Import & Export):** Full skeleton generation and export (`<= 64` bones), true bind-pose transforms via `RestMatrixInverse` (with optional preservation of imported game bind poses for 100% compatibility with original `.nad` files), and soft/rigid vertex weight assignments.
- **NAD Skeletal Animations (Import & Export):** Imports and exports `.nad` animation clips using Blender 5.2 layered animation and action slots, cubic Hermite curve interpolation (`a/b/c_factor`), and animation tag event markers (`pose_markers`).
- **NMS Motion Sets:** Supports `.nms` motion set scripts to resolve and batch-import associated animation sets (searching `Anims/`, `../Anims/`, and `../Motions/`).

## Requirements

- **Blender 5.2 LTS or newer** (tested on Blender 5.2.1 LTS with Python 3.13).

## Installation

### (a) Installing from Extension ZIP
1. In Blender, navigate to **Edit > Preferences > Get Extensions**.
2. Click the menu dropdown in the top-right corner and select **Install from Disk...**.
3. Choose `nod_import-1.0.2.zip` (located in the `dist/` directory).

Alternatively, install via the Blender command-line interface:
```powershell
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --command extension install-file -r user_default -e dist\nod_import-1.0.2.zip
```

### (b) Building the Extension ZIP from Source
To build the distribution ZIP archive from the repository root:
```powershell
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --command extension build --source-dir . --output-dir dist
```

## Import Options

Access the unified importer from **File > Import > Nod Import (.nod, .nad, .nms)**. Depending on the selected file type:

- **Selecting a `.nod` file** imports the 3D model, skeleton, materials, and optionally its animations.
- **Selecting one or more `.nad` files (or an `.nms` motion set)** imports the animation(s) directly onto the selected/existing NOD armature in the scene (similar to Blender Source Tools).

The importer exposes the following settings when importing a `.nod` model:

### Skeleton
- **Load Bones** (`load_bones`): Whether to load the armature skeleton and vertex groups (default: `True`).

### Animation
- **Load NAD Animation** (`load_animation`): Import NAD animations onto the imported armature (default: `True`).
- **Use NMS Motion Set** (`use_nms`): Load animations defined in an `.nms` motion set; disable to load a single `.nad` file instead (default: `True`).
- **NMS Motion Set** (`nms_path`): Optional `.nms` file path or filename. Leave empty to auto-search `<model>.nms` by priority: `1) .nod folder`, `2) Motions/`, `3) ../Motions/` (active when `Use NMS Motion Set` is enabled).
- **Animations Folder** (`nms_anims_dir`): Optional folder with `.nad` files for NMS. Leave empty to auto-search each `.nad` by priority: `1) .nod folder`, `2) Anims/`, `3) ../Anims/` (active when `Use NMS Motion Set` is enabled or when importing a `.nms` file).
- **NAD Animation** (`animation_path`): Single `.nad` file path (or filename inside the `.nod` folder) to load. If left empty, no animation is loaded (active when `Use NMS Motion Set` is disabled).

### Materials
- **Textures Folder** (`textures_path`): Optional folder with `.tga` textures. Leave empty to auto-search each texture by priority: `1) .nod folder`, `2) Materials/`, `3) ../Materials/`.

### Diagnostics
- **Debug Logging** (`debug_log`): Print detailed mesh, skeleton, and animation diagnostic messages to the console (default: `False`).

## Export Options

Version 1.0.2 bakes constant positive uniform skeleton object scale (including
Delta Scale and parent transforms) into scale-free bind matrices and bone
positions. NAD translation and rotation are sampled in the same world space.
The source Blender scene is not modified. Re-export both the NOD and all NAD
files when replacing exports from older versions; old and new binds must not
be mixed. No NAD scale tracks are written, because Redemption does not support
them. Animated scaling, non-uniform skeleton scaling, mirrored transforms and
shear produce an export error instead of silently producing an incompatible
animation. Ordinary mesh transforms remain supported.

Access the unified exporter from **File > Export > Nod Export (.nod, .nad)**. Switch between **Model (`.nod`)** and **Animation (`.nad`)** using the format toggle at the top of the export panel (or by typing `.nod` / `.nad` in the file name):

### Model (`.nod`)
- **Selected Objects Only** (`selected_only`): Export only selected mesh objects and their associated armature (default: `False`).
- **Export Bones & Skinning** (`export_bones`): Export the armature skeleton and vertex skin weights; disable to export as a static prop (default: `True`).
- **Preserve Imported NOD Bind Pose** (`preserve_imported_bind_pose`): Use original `RestMatrixInverse` matrices stored on imported NOD bones for 100% compatibility with existing game `.nad` animations (default: `True`).

### Animation (`.nad`)
- **Export All Actions to Folder** (`export_all_actions`): Export every Action in the `.blend` file to the target directory as `<action_name>.nad` (default: `False`).
- **Smooth Hermite Tangents** (`use_smooth_tangents`): Compute smooth Catmull-Rom Hermite curve fitting factors (`a`, `b`, `c`) between keyframes (default: `True`).
- **Frame Step** (`frame_step`): Keyframing step in frames when sampling the Blender Action (default: `1`).

## Development & Testing

### Running Unit Tests
Unit tests run independently of Blender using standard pytest:
```powershell
python -m pytest tests -q
```

### Running Blender Headless Smoke Test

Scale regression tests (optionally append `-- path\to\source.blend` to check
every source Action against rotation/translation-only engine skinning):

```powershell
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b --factory-startup --python-exit-code 1 --python tests\blender_scale_regression.py
```
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

- Progressive-mesh LOD collapse table (`HASLOD`) generation is not computed on export (models are exported at full resolution).
- Unhandled format variations or edge cases from unofficial game modifications may require further adjustments.

## License

This project is licensed under the GNU General Public License v3.0 or later ([GPL-3.0-or-later](LICENSE)).
