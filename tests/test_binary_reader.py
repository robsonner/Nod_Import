import struct
import pytest
from nod_import_core.binary_reader import BinaryReader, NodFormatError


def test_peek_and_read_byte():
    data = b"\x12\x34\x56"
    reader = BinaryReader(data)
    assert reader.position == 0
    assert reader.length == 3
    assert reader.remaining == 3

    assert reader.PeekByte() == 0x12
    assert reader.position == 0
    assert reader.remaining == 3

    assert reader.ReadByte() == 0x12
    assert reader.position == 1
    assert reader.remaining == 2

    assert reader.ReadByte() == 0x34
    assert reader.ReadByte() == 0x56
    assert reader.position == 3
    assert reader.remaining == 0

    with pytest.raises(NodFormatError) as exc_info:
        reader.ReadByte()
    assert "Unexpected end of buffer" in str(exc_info.value)
    assert "position 3" in str(exc_info.value)

    with pytest.raises(NodFormatError):
        reader.PeekByte()


def test_read_bytes():
    data = b"abcdef"
    reader = BinaryReader(data)
    res = reader.ReadBytes(3)
    assert isinstance(res, bytes)
    assert res == b"abc"
    assert reader.position == 3

    with pytest.raises(NodFormatError):
        reader.ReadBytes(4)


def test_read_uint16_and_int16():
    # Test positive, 0, and -1
    packed = struct.pack("<Hh", 65535, -1)
    reader = BinaryReader(packed)
    assert reader.ReadUInt16() == 65535
    assert reader.ReadInt16() == -1


def test_read_int16_negative_range():
    packed = struct.pack("<h", -32768)
    reader = BinaryReader(packed)
    assert reader.ReadInt16() == -32768


def test_read_uint32_and_int32():
    packed = struct.pack("<Ii", 4294967295, -1)
    reader = BinaryReader(packed)
    assert reader.ReadUInt32() == 4294967295
    assert reader.ReadInt32() == -1


def test_read_int32_negative_range():
    packed = struct.pack("<i", -2147483648)
    reader = BinaryReader(packed)
    assert reader.ReadInt32() == -2147483648


def test_read_floats():
    packed = struct.pack("<4f", 1.5, -2.5, 3.25, 4.0)
    reader = BinaryReader(packed)

    f1 = reader.ReadFloats(1)
    assert isinstance(f1, float)
    assert pytest.approx(f1) == 1.5
    assert reader.position == 4

    f3 = reader.ReadFloats(3)
    assert isinstance(f3, tuple)
    assert len(f3) == 3
    assert pytest.approx(f3[0]) == -2.5
    assert pytest.approx(f3[1]) == 3.25
    assert pytest.approx(f3[2]) == 4.0
    assert reader.position == 16


def test_read_floats_zero():
    reader = BinaryReader(b"")
    assert reader.ReadFloats(0) == ()


def test_read_string_with_null_terminator():
    data = b"abc\x00xyz\x00"
    reader = BinaryReader(data)
    s = reader.ReadString(8)
    assert s == "abc"
    assert reader.position == 8
    assert reader.remaining == 0


def test_read_string_without_null():
    data = b"hello"
    reader = BinaryReader(data)
    assert reader.ReadString(5) == "hello"
    assert reader.position == 5


def test_read_string_cp1252():
    # 0xE9 in cp1252 is é
    data = b"\xe9cole\x00\x00\x00"
    reader = BinaryReader(data)
    assert reader.ReadString(8) == "école"


def test_big_endian():
    packed = struct.pack(">HhIi", 1000, -500, 70000, -70000)
    reader = BinaryReader(packed, endianess="big")
    assert reader.endianess == "big"
    assert reader.ReadUInt16() == 1000
    assert reader.ReadInt16() == -500
    assert reader.ReadUInt32() == 70000
    assert reader.ReadInt32() == -70000


def test_invalid_endianess():
    with pytest.raises(ValueError):
        BinaryReader(b"", endianess="middle")


def test_nod_format_error_contains_details():
    reader = BinaryReader(b"\x01\x02")
    with pytest.raises(NodFormatError) as exc_info:
        reader.ReadUInt32()
    msg = str(exc_info.value)
    assert "position 0" in msg
    assert "4" in msg  # requested bytes
    assert "2" in msg  # buffer length
