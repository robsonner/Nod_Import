from . nod_header import NodHeader
from . nod_bone import NodBone
from . nod_vertex import NodVertex
from . nod_face import NodFace
from . nod_mesh_group import NodMeshGroup

class NodFile:
    header: NodHeader
    bones: list[NodBone]
    mesh_names: list[str]
    vertices: list[NodVertex]
    faces: list[NodFace]
    mesh_groups: list[NodMeshGroup]

    def __init__(self, bs):
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