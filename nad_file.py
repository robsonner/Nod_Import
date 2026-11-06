from .binary_reader import BinaryReader
from .binary_writer import BinaryWriter


class NadKeyframe:
    def __init__(self, reader: BinaryReader = None):
        if reader is None:
            self.frame = 0.0
            self.frame_scale = 0.0
            self.value = (0.0, 0.0, 0.0)
            self.c_factor = (0.0, 0.0, 0.0)
            self.b_factor = (0.0, 0.0, 0.0)
            self.a_factor = (0.0, 0.0, 0.0)
            return

        self.frame = reader.ReadFloats(1)
        self.frame_scale = reader.ReadFloats(1)
        self.value = reader.ReadFloats(3)
        self.c_factor = reader.ReadFloats(3)
        self.b_factor = reader.ReadFloats(3)
        self.a_factor = reader.ReadFloats(3)

    def write(self, bw: BinaryWriter) -> None:
        bw.WriteFloats(self.frame)
        bw.WriteFloats(self.frame_scale)
        bw.WriteFloats(self.value)
        bw.WriteFloats(self.c_factor)
        bw.WriteFloats(self.b_factor)
        bw.WriteFloats(self.a_factor)


class NadBoneTrack:
    def __init__(self, reader: BinaryReader = None):
        if reader is None:
            self.num_keys = 0
            self.bone_num = 0
            self.track_type = 0
            self.keys = []
            return

        self.num_keys = reader.ReadUInt32()
        self.bone_num = reader.ReadUInt32()
        self.track_type = reader.ReadUInt32()
        self.keys = [NadKeyframe(reader) for _ in range(self.num_keys)]

    def write(self, bw: BinaryWriter) -> None:
        self.num_keys = len(self.keys)
        bw.WriteUInt32(self.num_keys)
        bw.WriteUInt32(self.bone_num)
        bw.WriteUInt32(self.track_type)
        for key in self.keys:
            key.write(bw)


class NadTag:
    def __init__(self, reader: BinaryReader = None, frame: float = 0.0, tag_type: int = 0):
        if reader is None:
            self.frame = frame
            self.tag_type = tag_type
            return

        self.frame = reader.ReadFloats(1)
        self.tag_type = reader.ReadUInt32()

    def write(self, bw: BinaryWriter) -> None:
        bw.WriteFloats(self.frame)
        bw.WriteUInt32(self.tag_type)


class NadFile:
    def __init__(self, data: bytes = None):
        if data is None:
            self.version = 3
            self.num_bone_tracks = 0
            self.flags = 0
            self.duration = 0.0
            self.bone_tracks = []
            self.num_tags = 0
            self.tags = []
            return

        reader = BinaryReader(data, "little")
        self.version = reader.ReadUInt32()
        if self.version != 3:
            print(f"WARNING: NAD version is {self.version}, expected 3")
        self.num_bone_tracks = reader.ReadUInt32()
        self.flags = reader.ReadUInt32()
        self.duration = reader.ReadFloats(1)
        self.bone_tracks = [
            NadBoneTrack(reader) for _ in range(self.num_bone_tracks)
        ]
        self.num_tags = reader.ReadUInt32()
        self.tags = [NadTag(reader) for _ in range(self.num_tags)]

        if reader.position != reader.length:
            print(f"WARNING: NAD reader ended at {reader.position} of "
                  f"{reader.length} bytes")

    def write(self, bw: BinaryWriter) -> None:
        self.num_bone_tracks = len(self.bone_tracks)
        self.num_tags = len(self.tags)
        bw.WriteUInt32(self.version)
        bw.WriteUInt32(self.num_bone_tracks)
        bw.WriteUInt32(self.flags)
        bw.WriteFloats(self.duration)
        for track in self.bone_tracks:
            track.write(bw)
        bw.WriteUInt32(self.num_tags)
        for tag in self.tags:
            tag.write(bw)

    def to_bytes(self) -> bytes:
        bw = BinaryWriter("little")
        self.write(bw)
        return bw.to_bytes()
