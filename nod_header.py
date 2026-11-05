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

    def __init__(self, bs):
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

        self.HASLOD = self.model_flags & 0x1
        self.INLINE = self.model_flags & 0x2
        self.STATIC = self.model_flags & 0x4
        self.RESERVED1 = self.model_flags & 0x8
        self.RESERVED2 = self.model_flags & 0x10
