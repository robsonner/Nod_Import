from .vector3 import Vector3
from .vector2 import Vector2


class NodVertex:
    position: Vector3
    normal: Vector3
    uv: Vector2
    weight: float
    lod_index: int
    bone_number: int  # 4 bytes signed int (spec incorrectly says Byte)

    def __init__(self, bs=None):
        if bs is None:
            self.position = Vector3(0.0, 0.0, 0.0)
            self.normal = Vector3(0.0, 0.0, 1.0)
            self.uv = Vector2(0.0, 0.0)
            self.weight = 1.0
            self.bone_number = 0
            self.lod_index = 0
            return

        self.position = Vector3(*bs.ReadFloats(3))
        self.normal = Vector3(*bs.ReadFloats(3))
        self.uv = Vector2(*bs.ReadFloats(2))
        self.weight = bs.ReadFloats(1)
        self.bone_number = bs.ReadInt32()
        self.lod_index = 0

    def write(self, bw) -> None:
        bw.WriteFloats(self.position.x, self.position.y, self.position.z)
        bw.WriteFloats(self.normal.x, self.normal.y, self.normal.z)
        bw.WriteFloats(self.uv.x, self.uv.y)
        bw.WriteFloats(self.weight)
        bw.WriteInt32(self.bone_number)
