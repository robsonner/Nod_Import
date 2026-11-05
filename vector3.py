class Vector3:
    x: float
    y: float
    z: float

    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z

    def __str__(self):
        return str(self.x) + "," + str(self.y) + "," + str(self.z)

    def __repr__(self):
        return "x:" + str(self.x) + ",y:" + str(self.y) + ",z:" + str(self.z)

    def ReadBinaryReader(self, binaryReader):
        self.x = binaryReader.ReadFloats(1)
        self.y = binaryReader.ReadFloats(1)
        self.z = binaryReader.ReadFloats(1)
