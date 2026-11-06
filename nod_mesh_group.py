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

    def __init__(self, bs: BinaryReader = None):
        if bs is None:
            self.material_id = -1
            self.reserved = b"\x00" * 12
            self.num_faces = 0
            self.num_vertices = 0
            self.min_vertices = 0
            self.group_flags = 0
            self.bone_num = 0
            self.mesh_num = 0
            self.trash = 0
            return

        self.material_id = bs.ReadInt32()
        self.reserved = bs.ReadBytes(12)
        self.num_faces = bs.ReadUInt16()
        self.num_vertices = bs.ReadUInt16()
        self.min_vertices = bs.ReadUInt16()
        self.group_flags = bs.ReadUInt16()
        self.bone_num = bs.ReadByte()
        self.mesh_num = bs.ReadByte()
        self.trash = bs.ReadUInt16()

    def write(self, bw) -> None:
        bw.WriteInt32(self.material_id)
        reserved = self.reserved if len(self.reserved) == 12 else (self.reserved + b"\x00" * 12)[:12]
        bw.WriteBytes(reserved)
        bw.WriteUInt16(self.num_faces)
        bw.WriteUInt16(self.num_vertices)
        bw.WriteUInt16(self.min_vertices)
        bw.WriteUInt16(self.group_flags)
        bw.WriteByte(self.bone_num)
        bw.WriteByte(self.mesh_num)
        bw.WriteUInt16(self.trash)
