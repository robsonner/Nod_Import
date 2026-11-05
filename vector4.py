class Vector4:
    x: float
    y: float
    z: float
    w: float

    def __init__(self, x, y, z, w):
        self.x = x
        self.y = y
        self.z = z
        self.w = w

    def __str__(self):
        return str(self.x) + "," + str(self.y) + "," + str(self.z) + "," + str(self.w)

    def __repr__(self):
        return "x:" + str(self.x) + ",y:" + str(self.y) + ",z:" + str(self.z) + ",w:" + str(self.w)

    def ReadBinaryReader(self, binaryReader):
        self.x = binaryReader.ReadFloats(1)
        self.y = binaryReader.ReadFloats(1)
        self.z = binaryReader.ReadFloats(1)
        self.w = binaryReader.ReadFloats(1)
