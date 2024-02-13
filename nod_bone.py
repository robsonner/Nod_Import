from . vector3 import Vector3

class NodBone:
    rest_translate: Vector3 #Vector3 (three floats, 9 bytes, [XYZ])
    rest_matrix_inverse: list[Vector3] #Matrix34, list of vector3
    sibling_id: int #Signed short (2 bytes)
    child_id: int #Signed short
    parent_id: int #Signed short

    def __init__(self, bs):
        self.rest_translate = bs.ReadFloats(3)
        self.rest_matrix_inverse = []
        for x in range(4):
            self.rest_matrix_inverse.append(Vector3(bs.ReadFloats(1),bs.ReadFloats(1),bs.ReadFloats(1)))     

        #RestMatrixInverse = NoeMat43.fromBytes(bs.read(48)).transpose().inverse()
        self.sibling_id = bs.ReadInt16()
        self.child_id = bs.ReadInt16()
        self.parent_id = bs.ReadInt16()