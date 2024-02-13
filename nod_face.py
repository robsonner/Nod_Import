class NodFace:
    x: int
    y: int
    z: int

    def __init__(self,bs):
        self.x = bs.ReadUInt16()
        self.y = bs.ReadUInt16()
        self.z = bs.ReadUInt16()