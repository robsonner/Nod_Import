import functools
import struct
from typing import Literal


class NodFormatError(ValueError):
    """Raised when binary data cannot be parsed or buffer ends unexpectedly."""
    pass


_STRUCTS = {
    "<": {
        "H": struct.Struct("<H"),
        "h": struct.Struct("<h"),
        "I": struct.Struct("<I"),
        "i": struct.Struct("<i"),
        "f": struct.Struct("<f"),
    },
    ">": {
        "H": struct.Struct(">H"),
        "h": struct.Struct(">h"),
        "I": struct.Struct(">I"),
        "i": struct.Struct(">i"),
        "f": struct.Struct(">f"),
    },
}


@functools.lru_cache(maxsize=128)
def _get_float_struct(prefix: str, count: int) -> struct.Struct:
    return struct.Struct(f"{prefix}{count}f")


class BinaryReader:
    endianess: Literal["little", "big"]
    length: int
    position: int
    buffer: bytes

    def __init__(self, wdata: bytes, endianess: Literal["little", "big"] = "little"):
        self.buffer = wdata
        self.position = 0
        self.length = len(wdata)
        self.endianess = endianess

    @property
    def remaining(self) -> int:
        return self.length - self.position

    @property
    def endianess(self) -> Literal["little", "big"]:
        return self._endianess

    @endianess.setter
    def endianess(self, value: Literal["little", "big"]) -> None:
        if value not in ("little", "big"):
            raise ValueError(f"Invalid endianess: {value!r}")
        self._endianess = value
        self._prefix = "<" if value == "little" else ">"
        self._structs = _STRUCTS[self._prefix]

    def _check_bounds(self, n: int) -> None:
        if n < 0 or self.position + n > self.length:
            raise NodFormatError(
                f"Unexpected end of buffer at position {self.position}: "
                f"requested {n} bytes, but buffer length is {self.length} "
                f"(remaining: {self.length - self.position})"
            )

    def PeekByte(self) -> int:
        self._check_bounds(1)
        return self.buffer[self.position]

    def ReadByte(self) -> int:
        self._check_bounds(1)
        byte = self.buffer[self.position]
        self.position += 1
        return byte

    def ReadBytes(self, byteCount: int) -> bytes:
        self._check_bounds(byteCount)
        start = self.position
        self.position += byteCount
        return self.buffer[start:self.position]

    def ReadUInt16(self) -> int:
        self._check_bounds(2)
        val = self._structs["H"].unpack_from(self.buffer, self.position)[0]
        self.position += 2
        return val

    def ReadInt16(self) -> int:
        self._check_bounds(2)
        val = self._structs["h"].unpack_from(self.buffer, self.position)[0]
        self.position += 2
        return val

    def ReadUInt32(self) -> int:
        self._check_bounds(4)
        val = self._structs["I"].unpack_from(self.buffer, self.position)[0]
        self.position += 4
        return val

    def ReadInt32(self) -> int:
        self._check_bounds(4)
        val = self._structs["i"].unpack_from(self.buffer, self.position)[0]
        self.position += 4
        return val

    def ReadString(self, count: int) -> str:
        self._check_bounds(count)
        raw = self.buffer[self.position : self.position + count]
        self.position += count
        null_idx = raw.find(b"\x00")
        if null_idx != -1:
            raw = raw[:null_idx]
        return raw.decode("cp1252", errors="replace")

    def ReadFloats(self, floatsCount: int):
        byte_count = floatsCount * 4
        self._check_bounds(byte_count)
        if floatsCount == 1:
            val = self._structs["f"].unpack_from(self.buffer, self.position)[0]
            self.position += 4
            return val
        elif floatsCount > 1:
            s = _get_float_struct(self._prefix, floatsCount)
            res = s.unpack_from(self.buffer, self.position)
            self.position += byte_count
            return res
        elif floatsCount == 0:
            return ()
        else:
            raise ValueError(f"floatsCount must be non-negative, got {floatsCount}")
