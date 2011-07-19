#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Codecs
"""
import struct
        
CODEC_NONE = "None"
CODEC_RIVER_STRING = "RiverString"
CODEC_RIVER_BYTE_ARRAY = "RiverByteArray"

KNOWN_CODECS = [ CODEC_NONE, CODEC_RIVER_STRING, CODEC_RIVER_BYTE_ARRAY ]
        
RIVER_VERSION = 0x03
RIVER_ID_STR_EMPTY =  0x3d
RIVER_ID_STR_SMALL =  0x3e
RIVER_ID_STR_MEDIUM = 0x3f
RIVER_ID_STR_LARGE =  0x40

RIVER_ID_ARRAY_EMPTY   = 0x41
RIVER_ID_ARRAY_SMALL   = 0x42
RIVER_ID_ARRAY_MEDIUM  = 0x43
RIVER_ID_ARRAY_LARGE   = 0x44
RIVER_ID_PRIM_BYTE     = 0x21

  
def fromString(codecSpec):
  if codecSpec == None:
    return None
  elif codecSpec == CODEC_NONE:
    return None
  elif codecSpec == CODEC_RIVER_STRING:
    return RiverStringCodec()
  elif codecSpec == CODEC_RIVER_BYTE_ARRAY:
    return RiverByteArrayCodec()
  else:
    raise CodecError("unknown codec")

class CodecError(Exception):
  pass

class RiverStringCodec:
  """marshalls strings the same way as RiverMarshaller/RiverUnmarshaller"""
  def encode(self, str):
    utfstr = unicode(str, "utf-8").encode("utf-8")
    strlen = len(utfstr)
    bytes = struct.pack(">B", RIVER_VERSION)
    if (strlen == 0):
      bytes += struct.pack(">B", RIVER_ID_STR_EMPTY)
    elif (strlen <= 0x100):
      bytes += struct.pack(">B", RIVER_ID_STR_SMALL)
      bytes += struct.pack(">B", (strlen, 0)[strlen == 0x100])
    elif (strlen <= 0x10000):
      bytes += struct.pack(">B", RIVER_ID_STR_MEDIUM)
      bytes += struct.pack(">H", (strlen, 0)[strlen == 0x10000])
    else:
      bytes += struct.pack(">B", RIVER_ID_STR_LARGE)
      bytes += struct.pack(">i", strlen)
      
    bytes += utfstr
    return bytes
  
  def decode(self, bytes):
    if ord(bytes[0]) != RIVER_VERSION:
      raise CodecError("Unknown river marshaller version")
    id = ord(bytes[1])
    if (id == RIVER_ID_STR_EMPTY):
      return ""
    elif (id == RIVER_ID_STR_SMALL):
      strlen = ord(bytes[2])
      if (strlen == 0): strlen = 0x100
      return unicode(bytes[3:strlen+3], "utf-8").decode("utf-8")
    elif (id == RIVER_ID_STR_MEDIUM):
      strlen = struct.unpack(">H", bytes[2:4])[0];
      if (strlen == 0): strlen = 0x10000
      return unicode(bytes[4:strlen+4], "utf-8").decode("utf-8")
    elif (id == RIVER_ID_STR_LARGE):
      strlen = struct.unpack(">i", bytes[2:6])[0];
      return unicode(bytes[6:strlen+6], "utf-8").decode("utf-8")
    else:
      raise CodecError("Invalid RiverString value")
    
class RiverByteArrayCodec:
  """marshalls byte arrays the same way as RiverMarshaller/RiverUnmarshaller"""
  def encode(self, str):
    strlen = len(str)
    bytes = struct.pack(">B", RIVER_VERSION)
    if (strlen == 0):
      bytes += struct.pack(">B", RIVER_ID_ARRAY_EMPTY)
    elif (strlen <= 0x100):
      bytes += struct.pack(">B", RIVER_ID_ARRAY_SMALL)
      bytes += struct.pack(">B", (strlen, 0)[strlen == 0x100])
    elif (strlen <= 0x10000):
      bytes += struct.pack(">B", RIVER_ID_ARRAY_MEDIUM)
      bytes += struct.pack(">H", (strlen, 0)[strlen == 0x10000])
    else:
      bytes += struct.pack(">B", RIVER_ID_ARRAY_LARGE)
      bytes += struct.pack(">i", strlen)

    bytes += struct.pack(">B", RIVER_ID_PRIM_BYTE)
    bytes += str
    return bytes
  
  def decode(self, bytes):
    if ord(bytes[0]) != RIVER_VERSION:
      raise CodecError("Unknown river marshaller version")
    id = ord(bytes[1])
    if (id == RIVER_ID_ARRAY_EMPTY):
      return ""
    elif (id == RIVER_ID_ARRAY_SMALL):
      strlen = ord(bytes[2])
      if (strlen == 0): strlen = 0x100
      if ord(bytes[3]) != RIVER_ID_PRIM_BYTE:
        raise CodecError("Invalid RiverByteArray value")
      return unicode(bytes[4:strlen+4], "utf-8").decode("utf-8")
    elif (id == RIVER_ID_ARRAY_MEDIUM):
      strlen = struct.unpack(">H", bytes[2:4])[0];
      if (strlen == 0): strlen = 0x10000
      if ord(bytes[4]) != RIVER_ID_PRIM_BYTE:
        raise CodecError("Invalid RiverByteArray value")
      return unicode(bytes[5:strlen+5], "utf-8").decode("utf-8")
    elif (id == RIVER_ID_ARRAY_LARGE):
      strlen = struct.unpack(">i", bytes[2:6])[0];
      if ord(bytes[6]) != RIVER_ID_PRIM_BYTE:
        raise CodecError("Invalid RiverByteArray value")
      return unicode(bytes[7:strlen+7], "utf-8").decode("utf-8")
    else:
      raise CodecError("Invalid RiverByteArray value")
