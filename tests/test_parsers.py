import io
import pathlib
import struct
import pytest

from nod_import_core.binary_reader import BinaryReader, NodFormatError
from nod_import_core.nod_file import NodFile
from nod_import_core.nad_file import NadFile


def build_synthetic_nod(
    version=1,
    has_lod=False,
    bone_number=-1,
    material_id=-1,
    extra_bytes=b"",
):
    buf = bytearray()
    model_flags = 1 if has_lod else 0

    # Header
    buf += struct.pack("<II", version, 2)  # version, num_materials
    # 2 material names (32 bytes each)
    buf += b"mat_base\x00" + b"\x00" * (32 - 9)
    buf += b"mat_detail\x00" + b"\x00" * (32 - 11)

    # num_bones, num_meshes, num_vertices, num_faces, num_groups, model_flags
    buf += struct.pack("<HHIIHI", 1, 1, 2, 1, 1, model_flags)
    # bounds: 6 floats
    buf += struct.pack("<6f", -10.0, -20.0, -30.0, 10.0, 20.0, 30.0)

    # Bone 0
    # rest_translate (3 floats)
    buf += struct.pack("<3f", 1.0, 2.0, 3.0)
    # rest_matrix_inverse (12 floats)
    buf += struct.pack("<12f", *[float(i) for i in range(12)])
    # sibling_id, child_id, parent_id
    buf += struct.pack("<hhh", -1, -1, -1)

    # Mesh names (num_meshes * 32)
    buf += b"main_mesh\x00" + b"\x00" * (32 - 10)

    # Vertices (num_vertices = 2)
    for i in range(2):
        # pos(3), norm(3), uv(2), weight(1), bone_num(1 signed int)
        buf += struct.pack(
            "<3f3f2ffi",
            float(i), 0.0, 1.0,
            0.0, 1.0, 0.0,
            0.5, 0.5,
            1.0,
            bone_number,
        )

    # HASLOD indices
    if has_lod:
        buf += struct.pack("<2H", 100, 200)

    # Faces (num_faces = 1, 3 * u16)
    buf += struct.pack("<3H", 0, 1, 0)

    # MeshGroups (num_groups = 1)
    # material_id(i32), reserved(12B), num_faces(u16), num_vertices(u16),
    # min_vertices(u16), group_flags(u16), bone_num(u8), mesh_num(u8), trash(u16)
    buf += struct.pack("<i", material_id)
    buf += b"\x00" * 12
    buf += struct.pack("<HHHHBBH", 1, 2, 0, 0, 0, 0, 99)

    buf += extra_bytes
    return bytes(buf)


def build_synthetic_nad(version=3, extra_bytes=b""):
    buf = bytearray()
    num_tracks = 1
    flags = 0
    duration = 2.5
    buf += struct.pack("<IIIf", version, num_tracks, flags, duration)

    # Track 0: num_keys(u32), bone_num(u32), track_type(u32)
    num_keys = 2
    buf += struct.pack("<III", num_keys, 5, 1)
    # Keyframes (14 floats each)
    for k in range(num_keys):
        # frame, frame_scale, val[3], c[3], b[3], a[3]
        buf += struct.pack("<14f", float(k), 1.0, 1.0, 2.0, 3.0, *([0.0] * 9))

    # Tags: num_tags(u32)
    num_tags = 1
    buf += struct.pack("<I", num_tags)
    # Tag 0: frame(f32), tag_type(u32)
    buf += struct.pack("<fI", 1.25, 10)

    buf += extra_bytes
    return bytes(buf)


def test_parse_synthetic_nod(capsys):
    data = build_synthetic_nod(version=1, has_lod=False, bone_number=-1, material_id=-1)
    reader = BinaryReader(data)
    nod = NodFile(reader)

    assert nod.header.version == 1
    assert nod.header.num_materials == 2
    assert nod.header.material_names == ["mat_base", "mat_detail"]
    assert nod.header.num_bones == 1
    assert nod.header.num_meshes == 1
    assert nod.header.num_vertices == 2
    assert nod.header.num_faces == 1
    assert nod.header.num_groups == 1
    assert not nod.header.HASLOD
    assert nod.header.bounds == (-10.0, -20.0, -30.0, 10.0, 20.0, 30.0)

    # Bone
    bone = nod.bones[0]
    assert bone.rest_translate.x == 1.0
    assert bone.rest_translate.y == 2.0
    assert bone.rest_translate.z == 3.0
    assert len(bone.rest_matrix_inverse) == 3
    assert bone.rest_matrix_inverse[0].x == 0.0
    assert bone.rest_matrix_inverse[0].w == 3.0
    assert bone.sibling_id == -1
    assert bone.child_id == -1
    assert bone.parent_id == -1

    # Mesh names
    assert nod.mesh_names == ["main_mesh"]

    # Vertices
    assert len(nod.vertices) == 2
    assert nod.vertices[0].bone_number == -1
    assert nod.vertices[1].bone_number == -1
    assert nod.vertices[0].position.x == 0.0
    assert nod.vertices[1].position.x == 1.0
    assert nod.vertices[0].weight == 1.0

    # Faces
    assert len(nod.faces) == 1
    assert (nod.faces[0].x, nod.faces[0].y, nod.faces[0].z) == (0, 1, 0)

    # Mesh groups
    assert len(nod.mesh_groups) == 1
    group = nod.mesh_groups[0]
    assert group.material_id == -1
    assert isinstance(group.reserved, bytes)
    assert len(group.reserved) == 12
    assert group.num_faces == 1
    assert group.num_vertices == 2
    assert group.trash == 99

    # No warnings on exact length
    captured = capsys.readouterr()
    assert "WARNING" not in captured.out


def test_parse_nod_haslod():
    data = build_synthetic_nod(has_lod=True)
    reader = BinaryReader(data)
    nod = NodFile(reader)
    assert nod.header.HASLOD
    assert nod.vertices[0].lod_index == 100
    assert nod.vertices[1].lod_index == 200


def test_parse_nod_truncated():
    data = build_synthetic_nod()
    truncated = data[: len(data) - 5]
    with pytest.raises(NodFormatError):
        NodFile(BinaryReader(truncated))


def test_parse_nod_trailing_bytes(capsys):
    data = build_synthetic_nod(extra_bytes=b"extra_padding_bytes")
    nod = NodFile(BinaryReader(data))
    captured = capsys.readouterr()
    assert "WARNING: NOD reader ended at" in captured.out


def test_parse_synthetic_nad(capsys):
    data = build_synthetic_nad(version=3)
    nad = NadFile(data)

    assert nad.version == 3
    assert nad.num_bone_tracks == 1
    assert nad.flags == 0
    assert pytest.approx(nad.duration) == 2.5
    assert len(nad.bone_tracks) == 1

    track = nad.bone_tracks[0]
    assert track.num_keys == 2
    assert track.bone_num == 5
    assert track.track_type == 1
    assert len(track.keys) == 2

    assert pytest.approx(track.keys[0].frame) == 0.0
    assert pytest.approx(track.keys[0].value[0]) == 1.0
    assert pytest.approx(track.keys[1].frame) == 1.0

    assert nad.num_tags == 1
    assert len(nad.tags) == 1
    assert pytest.approx(nad.tags[0].frame) == 1.25
    assert nad.tags[0].tag_type == 10

    captured = capsys.readouterr()
    assert "WARNING" not in captured.out


def test_parse_nad_version_warning(capsys):
    data = build_synthetic_nad(version=2)
    nad = NadFile(data)
    assert nad.version == 2
    captured = capsys.readouterr()
    assert "WARNING: NAD version is 2, expected 3" in captured.out


def test_parse_nad_truncated():
    data = build_synthetic_nad()
    truncated = data[: len(data) - 4]
    with pytest.raises(NodFormatError):
        NadFile(truncated)


def test_parse_nad_trailing_bytes(capsys):
    data = build_synthetic_nad(extra_bytes=b"pad")
    nad = NadFile(data)
    captured = capsys.readouterr()
    assert "WARNING: NAD reader ended at" in captured.out


MODELS_DIR = pathlib.Path(r"F:\GOG Games\Vampire The Masquerade - Redemption\ExtractedModels")


@pytest.mark.skipif(not MODELS_DIR.exists(), reason="Game models directory not found")
def test_parse_all_game_nod_files():
    nod_files = list(MODELS_DIR.glob("*.nod"))
    assert len(nod_files) > 0, "No .nod files found in test data"

    for path in nod_files:
        data = path.read_bytes()
        reader = BinaryReader(data)
        nod = NodFile(reader)

        assert nod.header.num_bones == len(nod.bones), f"{path.name}: bone count mismatch"
        assert nod.header.num_meshes == len(nod.mesh_names), f"{path.name}: mesh count mismatch"
        assert nod.header.num_vertices == len(nod.vertices), f"{path.name}: vertex count mismatch"
        assert nod.header.num_faces == len(nod.faces), f"{path.name}: face count mismatch"
        assert nod.header.num_groups == len(nod.mesh_groups), f"{path.name}: group count mismatch"


@pytest.mark.skipif(not MODELS_DIR.exists(), reason="Game models directory not found")
def test_parse_christof_nad_files():
    nad_files = list(MODELS_DIR.glob("christof_*.nad"))
    assert len(nad_files) > 0, "No christof_*.nad files found in test data"

    for path in nad_files:
        data = path.read_bytes()
        nad = NadFile(data)
        assert nad.num_bone_tracks == len(nad.bone_tracks), f"{path.name}: track count mismatch"
        assert nad.num_tags == len(nad.tags), f"{path.name}: tag count mismatch"
