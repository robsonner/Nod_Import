from . vector3 import Vector3

class NodBone:
    """The centerpoint of the bone in the at-rest pose of the model"""
    rest_translate: Vector3 #Vector3 (three floats, 9 bytes, [XYZ])
    """The inverse orientation of the bone in the at-rest pose"""
    rest_matrix_inverse: list[Vector3] #Matrix34, list of vector3
    """The index of the next "sibling" bone, or –1 if this is the last"""
    sibling_id: int #Signed short (2 bytes)
    """The index of the first child of this bone or –1 if there is no child."""
    child_id: int #Signed short
    """The index of the parent of this bone. The root bone is always defined first,
       so –1 is only valid for that bone."""
    parent_id: int #Signed short

    def __init__(self, bs):
        self.rest_translate = Vector3(bs.ReadFloats(1),bs.ReadFloats(1),bs.ReadFloats(1))
        self.rest_matrix_inverse = []
        for x in range(4):
            self.rest_matrix_inverse.append(Vector3(bs.ReadFloats(1),bs.ReadFloats(1),bs.ReadFloats(1)))     

        #RestMatrixInverse = NoeMat43.fromBytes(bs.read(48)).transpose().inverse()
        self.sibling_id = bs.ReadInt16()
        self.child_id = bs.ReadInt16()
        self.parent_id = bs.ReadInt16()