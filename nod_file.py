from .binary_writer import BinaryWriter
from .nod_header import NodHeader
from .nod_bone import NodBone
from .nod_vertex import NodVertex
from .nod_face import NodFace
from .nod_mesh_group import NodMeshGroup


class NodFile:
    header: NodHeader
    bones: list[NodBone]
    mesh_names: list[str]
    vertices: list[NodVertex]
    faces: list[NodFace]
    mesh_groups: list[NodMeshGroup]

    def __init__(self, bs=None):
        if bs is None:
            self.header = NodHeader()
            self.bones = []
            self.mesh_names = []
            self.vertices = []
            self.faces = []
            self.mesh_groups = []
            return

        self.header = NodHeader(bs)
        self.bones = []
        for i in range(self.header.num_bones):
            self.bones.append(NodBone(bs))

        self.mesh_names = []
        for i in range(self.header.num_meshes):
            self.mesh_names.append(str(bs.ReadString(32)))

        self.vertices = []
        for i in range(self.header.num_vertices):
            self.vertices.append(NodVertex(bs))
        if self.header.HASLOD:
            for i in range(self.header.num_vertices):
                self.vertices[i].lod_index = bs.ReadUInt16()

        self.faces = []
        for i in range(self.header.num_faces):
            self.faces.append(NodFace(bs))

        self.mesh_groups = []
        for i in range(self.header.num_groups):
            self.mesh_groups.append(NodMeshGroup(bs))

        if bs.position != bs.length:
            print(f"WARNING: NOD reader ended at {bs.position} of {bs.length} bytes")

    def write(self, bw: BinaryWriter) -> None:
        self.header.num_bones = len(self.bones)
        self.header.num_meshes = len(self.mesh_names)
        self.header.num_vertices = len(self.vertices)
        self.header.num_faces = len(self.faces)
        self.header.num_groups = len(self.mesh_groups)
        self.header._sync_flags()

        self.header.write(bw)
        for bone in self.bones:
            bone.write(bw)
        for mesh_name in self.mesh_names:
            bw.WriteString(mesh_name, 32)
        for vertex in self.vertices:
            vertex.write(bw)
        if self.header.HASLOD:
            for vertex in self.vertices:
                bw.WriteUInt16(vertex.lod_index)
        for face in self.faces:
            face.write(bw)
        for group in self.mesh_groups:
            group.write(bw)

    def to_bytes(self) -> bytes:
        bw = BinaryWriter("little")
        self.write(bw)
        return bw.to_bytes()
