import struct
from typing import Literal

from .binary_reader import _STRUCTS, _get_float_struct


class BinaryWriter:
    endianess: Literal["little", "big"]

    def __init__(self, endianess: Literal["little", "big"] = "little"):
        self._buffer = bytearray()
        self.endianess = endianess

    @property
    def position(self) -> int:
        return len(self._buffer)

    @property
    def length(self) -> int:
        return len(self._buffer)

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

    def to_bytes(self) -> bytes:
        return bytes(self._buffer)

    def WriteByte(self, value: int) -> None:
        if not (0 <= value <= 255):
            raise ValueError(f"Byte value out of range [0, 255]: {value}")
        self._buffer.append(value)

    def WriteBytes(self, data: bytes | bytearray) -> None:
        self._buffer.extend(data)

    def WriteUInt16(self, value: int) -> None:
        self._buffer.extend(self._structs["H"].pack(int(value)))

    def WriteInt16(self, value: int) -> None:
        self._buffer.extend(self._structs["h"].pack(int(value)))

    def WriteUInt32(self, value: int) -> None:
        self._buffer.extend(self._structs["I"].pack(int(value)))

    def WriteInt32(self, value: int) -> None:
        self._buffer.extend(self._structs["i"].pack(int(value)))

    def WriteString(self, text: str, count: int) -> None:
        if count < 0:
            raise ValueError(f"count must be non-negative, got {count}")
        if count == 0:
            return
        clean = (text or "").split("\x00", 1)[0]
        encoded = clean.encode("cp1252", errors="replace")
        if len(encoded) >= count:
            # Leave room for null terminator if count > 0, or truncate to count
            self._buffer.extend(encoded[: count - 1] + b"\x00")
        else:
            self._buffer.extend(encoded + b"\x00" * (count - len(encoded)))

    def WriteFloats(self, *values) -> None:
        if len(values) == 1 and isinstance(values[0], (tuple, list)):
            flat = tuple(values[0])
        else:
            flat = values
        n = len(flat)
        if n == 0:
            return
        if n == 1:
            self._buffer.extend(self._structs["f"].pack(float(flat[0])))
        else:
            s = _get_float_struct(self._prefix, n)
            self._buffer.extend(s.pack(*(float(v) for v in flat)))
