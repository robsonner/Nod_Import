from . binary_reader import BinaryReader

class NodMeshGroup:
    material_id: int #Signed Integer (SINT)
    reserved: [] #12 bytes
    num_faces: int #WORD
    num_vertices: int #WORD
    min_vertices: int #WORD
    group_flags: int #WORD
    bone_num: int #BYTE
    mesh_num: int #Byte
    trash: int #2 bytes,for some reason there is 2 bytes at the end of mesh group that's not in documentation

    def __init__(self, bs : BinaryReader):
        self.material_id = bs.ReadInt32()
        self.reserved = bs.ReadBytes(12)
        self.num_faces = bs.ReadUInt16()
        self.num_vertices = bs.ReadUInt16()
        self.min_vertices = bs.ReadUInt16()
        #self.trash = bs.ReadUInt16() 
        self.group_flags = bs.ReadUInt16()
        self.bone_num = bs.ReadByte()
        self.mesh_num = bs.ReadByte()
        #seems like there is some aditional data that's doing nothing and is not in doc
        #it's probably last, i don't know why
        self.trash = bs.ReadUInt16() 