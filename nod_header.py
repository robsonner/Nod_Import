class NodHeader:
    version: int  # UINT
    num_materials: int  # UINT
    material_names: list[str]  # 32 characters * NumMaterials
    num_bones: int  # Word (2 bytes)
    num_meshes: int  # WORD
    num_vertices: int  # UINT
    num_faces: int  # UINT
    num_groups: int  # WORD
    model_flags: int  # UINT
    bounds: tuple  # 6 floats, min(XYZ), max(XYZ)

    def __init__(self, bs=None):
        if bs is None:
            self.version = 7
            self.num_materials = 0
            self.material_names = []
            self.num_bones = 0
            self.num_meshes = 0
            self.num_vertices = 0
            self.num_faces = 0
            self.num_groups = 0
            self.model_flags = 0
            self.bounds = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
            self._sync_flags()
            return

        self.version = bs.ReadUInt32()
        self.num_materials = bs.ReadUInt32()
        self.material_names = []
        for x in range(self.num_materials):
            self.material_names.append(str(bs.ReadString(32)))

        self.num_bones = bs.ReadUInt16()
        self.num_meshes = bs.ReadUInt16()
        self.num_vertices = bs.ReadUInt32()
        self.num_faces = bs.ReadUInt32()
        self.num_groups = bs.ReadUInt16()
        self.model_flags = bs.ReadUInt32()
        self.bounds = bs.ReadFloats(6)
        self._sync_flags()

    def _sync_flags(self):
        self.HASLOD = self.model_flags & 0x1
        self.INLINE = self.model_flags & 0x2
        self.STATIC = self.model_flags & 0x4
        self.RESERVED1 = self.model_flags & 0x8
        self.RESERVED2 = self.model_flags & 0x10

    def write(self, bw) -> None:
        self.num_materials = len(self.material_names)
        bw.WriteUInt32(self.version)
        bw.WriteUInt32(self.num_materials)
        for name in self.material_names:
            bw.WriteString(name, 32)
        bw.WriteUInt16(self.num_bones)
        bw.WriteUInt16(self.num_meshes)
        bw.WriteUInt32(self.num_vertices)
        bw.WriteUInt32(self.num_faces)
        bw.WriteUInt16(self.num_groups)
        bw.WriteUInt32(self.model_flags)
        bw.WriteFloats(self.bounds)
