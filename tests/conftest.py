import pathlib
import sys
import types
from _pytest.python import Package

# Prevent pytest from importing the parent addon directory as a package (which imports bpy)
Package.setup = lambda self: None

ROOT = pathlib.Path(__file__).resolve().parents[1]
pkg = types.ModuleType("nod_import_core")
pkg.__path__ = [str(ROOT)]
sys.modules.setdefault("nod_import_core", pkg)
