from .binary_reader import BinaryReader


class NodMeshGroup:
    material_id: int  # Signed Integer (SINT)
    reserved: bytes  # 12 bytes
    num_faces: int  # WORD
    num_vertices: int  # WORD
    min_vertices: int  # WORD
    group_flags: int  # WORD
    bone_num: int  # BYTE
    mesh_num: int  # Byte
    trash: int  # 2 bytes trailing data

    def __init__(self, bs: BinaryReader):
        self.material_id = bs.ReadInt32()
        self.reserved = bs.ReadBytes(12)
        self.num_faces = bs.ReadUInt16()
        self.num_vertices = bs.ReadUInt16()
        self.min_vertices = bs.ReadUInt16()
        self.group_flags = bs.ReadUInt16()
        self.bone_num = bs.ReadByte()
        self.mesh_num = bs.ReadByte()
        self.trash = bs.ReadUInt16()
