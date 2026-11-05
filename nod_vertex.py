from .vector3 import Vector3
from .vector2 import Vector2


class NodVertex:
    position: Vector3
    normal: Vector3
    uv: Vector2
    weight: float
    lod_index: int
    bone_number: int  # 4 bytes signed int (spec incorrectly says Byte)

    def __init__(self, bs):
        self.position = Vector3(*bs.ReadFloats(3))
        self.normal = Vector3(*bs.ReadFloats(3))
        self.uv = Vector2(*bs.ReadFloats(2))
        self.weight = bs.ReadFloats(1)
        self.bone_number = bs.ReadInt32()
        self.lod_index = 0
