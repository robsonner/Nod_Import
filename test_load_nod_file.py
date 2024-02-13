import struct
from binary_reader import BinaryReader
from vector3 import Vector3
from vector2 import Vector2
from nod_vertex import NodVertex
from nod_face import NodFace
from nod_file import NodFile

def CheckType(data):

    return 1

def LoadModel(data):
    bs = BinaryReader(data, "little") #the files are in little-endian
    nod_file = NodFile(bs) 
    print("We read everything, now position of buffer: ",bs.position," and length: ", bs.length)

if __name__ == "__main__":
    in_file = open("F:\GOG Games\Vampire The Masquerade - Redemption\ExtractedModels\christof.nod", "rb") # opening for [r]eading as [b]inary
    data = in_file.read()
    in_file.close()
    LoadModel(data)