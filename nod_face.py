class NodFace:
    x: int
    y: int
    z: int

    def __init__(self, bs=None, x: int = 0, y: int = 0, z: int = 0):
        if bs is None:
            self.x = x
            self.y = y
            self.z = z
            return
        self.x = bs.ReadUInt16()
        self.y = bs.ReadUInt16()
        self.z = bs.ReadUInt16()

    def write(self, bw) -> None:
        bw.WriteUInt16(self.x)
        bw.WriteUInt16(self.y)
        bw.WriteUInt16(self.z)
