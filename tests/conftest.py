import pathlib
import sys
import types
try:
    from _pytest.python import Package
    if hasattr(Package, "setup"):
        # Prevent pytest from importing the parent addon directory as a package (which imports bpy)
        Package.setup = lambda self: None
except ImportError:
    pass

ROOT = pathlib.Path(__file__).resolve().parents[1]
pkg = types.ModuleType("nod_import_core")
pkg.__path__ = [str(ROOT)]
sys.modules.setdefault("nod_import_core", pkg)
