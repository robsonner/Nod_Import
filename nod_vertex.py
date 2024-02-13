from . vector3 import Vector3
from . vector2 import Vector2

class NodVertex:
    position: Vector3
    normal: Vector3
    uv: Vector2
    weight: float
    lod_index: int
    bone_number: int #in documentation there is a mistake it says, Byte but it's actually 4 bytes (int)

    def __init__(self, bs):
         self.position = Vector3(bs.ReadFloats(1),bs.ReadFloats(1),bs.ReadFloats(1))
         self.normal= Vector3(bs.ReadFloats(1),bs.ReadFloats(1),bs.ReadFloats(1))
         self.uv = Vector2(bs.ReadFloats(1),bs.ReadFloats(1))
         self.weight = bs.ReadFloats(1)
         self.bone_number =bs.ReadInt32()