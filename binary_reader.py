import struct
from typing import Literal

class BinaryReader:
        endianess: Literal['little', 'big'] = "little",
        length: int
        position: int
        buffer: bytes
        
        def __init__(self, wdata: bytes, endianess: Literal['little', 'big'] = "little"):
            self.buffer = wdata
            self.position = 0
            self.length = len(wdata)
            self.endianess = endianess

        def PeekByte(self):
             return self.buffer[self.position]
        
        def ReadByte(self):
             byte = self.buffer[self.position]
             self.position += 1
             return byte
                
        def ReadBytes(self, byteCount):
             retBuffer = []
             for x in range(byteCount):
                  retBuffer.append(self.buffer[self.position])
                  self.position += 1
             return retBuffer
                
        def ReadUInt16(self):
              int16 = int.from_bytes([self.buffer[self.position],self.buffer[self.position+1]], self.endianess)
              self.position += 2
              return int16
                
        def ReadInt16(self):
              int16 = int.from_bytes([self.buffer[self.position],self.buffer[self.position+1]], self.endianess,signed="True")
              self.position += 2
              return int16
        
        def ReadUInt32(self):
              int32 = int.from_bytes([self.buffer[self.position],
                                      self.buffer[self.position+1],
                                      self.buffer[self.position+2],
                                      self.buffer[self.position+3]], self.endianess)
              self.position += 4
              return int32
                
        def ReadInt32(self):
              int32 = int.from_bytes([self.buffer[self.position],
                                      self.buffer[self.position+1],
                                      self.buffer[self.position+2],
                                      self.buffer[self.position+3]], self.endianess)
              self.position += 4
              return int32
        
        def ReadString(self, count: int):
             ret = ""
             for i in range (0, count):
                  ret += chr(self.buffer[self.position + i])
             self.position+= count
             return ret
        
        #reads multiple floats
        def ReadFloats(self, floatsCount: int):
             tmpBuff = []
             result = []
             for i in range (0, floatsCount):
                  for x in range(4):
                    tmpBuff.append(self.buffer[self.position+x])
                  self.position+= 4

             bytesBuff = bytes(tmpBuff)         
             if self.endianess == "little":
                 result = struct.unpack("<" +str(floatsCount) + "f", bytesBuff)
             else:
                 result = struct.unpack(">" + str(floatsCount) + "f", bytesBuff)

             #struct unpack always returns tuple even if it's only one float,
             # so this is a little bit hacky but i am no python expert :P
             if floatsCount == 1:  
                 return result[0]
             else:
                 return result