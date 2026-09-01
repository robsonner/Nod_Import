from .binary_reader import BinaryReader


class NadKeyframe:
    def __init__(self, reader: BinaryReader):
        self.frame = reader.ReadFloats(1)
        self.frame_scale = reader.ReadFloats(1)
        self.value = reader.ReadFloats(3)
        self.c_factor = reader.ReadFloats(3)
        self.b_factor = reader.ReadFloats(3)
        self.a_factor = reader.ReadFloats(3)


class NadBoneTrack:
    def __init__(self, reader: BinaryReader):
        self.num_keys = reader.ReadUInt32()
        self.bone_num = reader.ReadUInt32()
        self.track_type = reader.ReadUInt32()
        self.keys = [NadKeyframe(reader) for _ in range(self.num_keys)]


class NadTag:
    def __init__(self, reader: BinaryReader):
        self.frame = reader.ReadFloats(1)
        self.tag_type = reader.ReadUInt32()


class NadFile:
    def __init__(self, data: bytes):
        reader = BinaryReader(data, "little")
        self.version = reader.ReadUInt32()
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
