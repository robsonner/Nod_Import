class Vector2:
     x: float
     y: float
     
     def __init__(self, x,y):
          self.x = x
          self.y = y

     def __str__(self):
       return str(self.x) + "," + str(self.y)
     
     def __repr__(self):
       return "x:" + str(self.x) + ",y:" + str(self.y)

     def ReadBinaryReader(self, binaryReader):
          self.x = binaryReader.ReadFloats(1)
          self.y = binaryReader.ReadFloats(1)