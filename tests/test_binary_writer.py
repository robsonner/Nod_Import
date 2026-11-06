import pathlib
import pytest

from nod_import_core.binary_reader import BinaryReader
from nod_import_core.binary_writer import BinaryWriter
from nod_import_core.nod_file import NodFile
from nod_import_core.nad_file import NadFile
from test_parsers import build_synthetic_nod, build_synthetic_nad, MODELS_DIR


def test_writer_primitives_roundtrip():
    bw = BinaryWriter("little")
    bw.WriteByte(0xAB)
    bw.WriteBytes(b"xyz")
    bw.WriteUInt16(65535)
    bw.WriteInt16(-12345)
    bw.WriteUInt32(4000000000)
    bw.WriteInt32(-1)
    bw.WriteFloats(1.5)
    bw.WriteFloats(-2.5, 3.25, 4.0)
    bw.WriteFloats((5.0, 6.0))
    bw.WriteString("test_mat", 16)

    raw = bw.to_bytes()
    assert bw.position == len(raw)
    assert bw.length == len(raw)

    br = BinaryReader(raw, "little")
    assert br.ReadByte() == 0xAB
    assert br.ReadBytes(3) == b"xyz"
    assert br.ReadUInt16() == 65535
    assert br.ReadInt16() == -12345
    assert br.ReadUInt32() == 4000000000
    assert br.ReadInt32() == -1
    assert pytest.approx(br.ReadFloats(1)) == 1.5
    assert pytest.approx(br.ReadFloats(3)) == (-2.5, 3.25, 4.0)
    assert pytest.approx(br.ReadFloats(2)) == (5.0, 6.0)
    assert br.ReadString(16) == "test_mat"
    assert br.remaining == 0


def test_writer_big_endian():
    bw = BinaryWriter("big")
    assert bw.endianess == "big"
    bw.WriteUInt16(1000)
    bw.WriteInt16(-500)
    bw.WriteUInt32(70000)
    bw.WriteInt32(-70000)
    bw.WriteFloats(2.5, -3.5)

    br = BinaryReader(bw.to_bytes(), "big")
    assert br.ReadUInt16() == 1000
    assert br.ReadInt16() == -500
    assert br.ReadUInt32() == 70000
    assert br.ReadInt32() == -70000
    assert pytest.approx(br.ReadFloats(2)) == (2.5, -3.5)


def test_writer_string_padding_and_truncation():
    bw = BinaryWriter()
    bw.WriteString("abc\x00ignored", 8)
    assert bw.to_bytes() == b"abc\x00\x00\x00\x00\x00"

    bw2 = BinaryWriter()
    bw2.WriteString("0123456789", 5)
    assert len(bw2.to_bytes()) == 5
    assert bw2.to_bytes() == b"0123\x00"


def test_writer_invalid_inputs():
    with pytest.raises(ValueError):
        BinaryWriter("middle")

    bw = BinaryWriter()
    with pytest.raises(ValueError):
        bw.WriteByte(256)
    with pytest.raises(ValueError):
        bw.WriteString("a", -1)


@pytest.mark.parametrize("has_lod", [False, True])
def test_synthetic_nod_exact_roundtrip(has_lod):
    original_bytes = build_synthetic_nod(
        version=7,
        has_lod=has_lod,
        bone_number=-1,
        material_id=-1,
    )
    nod = NodFile(BinaryReader(original_bytes))
    rewritten_bytes = nod.to_bytes()
    assert rewritten_bytes == original_bytes


def test_synthetic_nad_exact_roundtrip():
    original_bytes = build_synthetic_nad(version=3)
    nad = NadFile(original_bytes)
    rewritten_bytes = nad.to_bytes()
    assert rewritten_bytes == original_bytes


def test_programmatic_nod_and_nad_creation():
    nod = NodFile()
    nod.header.material_names = ["skin_mat"]
    raw_nod = nod.to_bytes()
    parsed_nod = NodFile(BinaryReader(raw_nod))
    assert parsed_nod.header.version == 7
    assert parsed_nod.header.material_names == ["skin_mat"]
    assert parsed_nod.header.num_bones == 0

    nad = NadFile()
    nad.duration = 10.0
    raw_nad = nad.to_bytes()
    parsed_nad = NadFile(raw_nad)
    assert parsed_nad.version == 3
    assert pytest.approx(parsed_nad.duration) == 10.0


@pytest.mark.skipif(not MODELS_DIR.exists(), reason="Game models directory not found")
def test_game_nod_files_roundtrip():
    nod_files = list(MODELS_DIR.glob("*.nod"))
    assert len(nod_files) > 0

    for path in nod_files:
        orig_data = path.read_bytes()
        nod1 = NodFile(BinaryReader(orig_data))
        exported_bytes = nod1.to_bytes()
        nod2 = NodFile(BinaryReader(exported_bytes))

        # Second export must be 100% byte-identical to first export
        assert nod2.to_bytes() == exported_bytes, f"{path.name}: non-deterministic serialization"

        # Verify structural equality
        assert nod1.header.version == nod2.header.version
        assert nod1.header.material_names == nod2.header.material_names
        assert nod1.header.bounds == nod2.header.bounds
        assert nod1.header.model_flags == nod2.header.model_flags
        assert nod1.mesh_names == nod2.mesh_names
        assert len(nod1.bones) == len(nod2.bones)
        assert len(nod1.vertices) == len(nod2.vertices)
        assert len(nod1.faces) == len(nod2.faces)
        assert len(nod1.mesh_groups) == len(nod2.mesh_groups)

        for b1, b2 in zip(nod1.bones, nod2.bones):
            assert (b1.parent_id, b1.child_id, b1.sibling_id) == (b2.parent_id, b2.child_id, b2.sibling_id)
        for g1, g2 in zip(nod1.mesh_groups, nod2.mesh_groups):
            assert g1.material_id == g2.material_id
            assert g1.num_faces == g2.num_faces
            assert g1.num_vertices == g2.num_vertices
            assert g1.group_flags == g2.group_flags


@pytest.mark.skipif(not MODELS_DIR.exists(), reason="Game models directory not found")
def test_game_nad_files_exact_byte_roundtrip():
    nad_files = list(MODELS_DIR.glob("christof_*.nad"))
    assert len(nad_files) > 0

    for path in nad_files:
        orig_data = path.read_bytes()
        nad = NadFile(orig_data)
        exported_bytes = nad.to_bytes()
        assert exported_bytes == orig_data, f"{path.name}: byte roundtrip mismatch"
