from .vector3 import Vector3
from .vector4 import Vector4


class NodBone:
    # The centerpoint of the bone in the at-rest pose of the model
    rest_translate: Vector3  # Vector3 (three floats, 12 bytes, [XYZ])
    # The inverse orientation of the bone in the at-rest pose
    rest_matrix_inverse: list[Vector4]  # Matrix34, list of 3 Vector4 (48 bytes)
    # The index of the next "sibling" bone, or -1 if this is the last
    sibling_id: int  # Signed short (2 bytes)
    # The index of the first child of this bone or -1 if there is no child
    child_id: int  # Signed short (2 bytes)
    # The index of the parent of this bone. The root bone is always defined first,
    # so -1 is only valid for that bone.
    parent_id: int  # Signed short (2 bytes)

    def __init__(self, bs=None):
        if bs is None:
            self.rest_translate = Vector3(0.0, 0.0, 0.0)
            self.rest_matrix_inverse = [
                Vector4(1.0, 0.0, 0.0, 0.0),
                Vector4(0.0, 1.0, 0.0, 0.0),
                Vector4(0.0, 0.0, 1.0, 0.0),
            ]
            self.sibling_id = -1
            self.child_id = -1
            self.parent_id = -1
            return

        self.rest_translate = Vector3(*bs.ReadFloats(3))
        self.rest_matrix_inverse = []
        for x in range(3):
            self.rest_matrix_inverse.append(Vector4(*bs.ReadFloats(4)))
        self.sibling_id = bs.ReadInt16()
        self.child_id = bs.ReadInt16()
        self.parent_id = bs.ReadInt16()

    def write(self, bw) -> None:
        bw.WriteFloats(
            self.rest_translate.x,
            self.rest_translate.y,
            self.rest_translate.z,
        )
        for row in self.rest_matrix_inverse:
            bw.WriteFloats(row.x, row.y, row.z, row.w)
        bw.WriteInt16(self.sibling_id)
        bw.WriteInt16(self.child_id)
        bw.WriteInt16(self.parent_id)
