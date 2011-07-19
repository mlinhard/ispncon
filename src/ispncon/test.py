'''
Created on Jul 18, 2011

@author: mlinhard
'''
from ispncon.codec import RiverStringCodec, RiverByteArrayCodec

def ByteToHex(byteStr):
  return ''.join([ "%02X " % ord(x) for x in byteStr ]).strip()

def hex(byteStr):
  if len(byteStr) > 20:
    return ByteToHex(byteStr[0:20]) + "...(next " + str(len(byteStr) - 20) + " chars)"
  else:
    return ByteToHex(byteStr) 
  
def char(byteStr):
  if len(byteStr) > 20:
    return byteStr[0:20] + "...(next " + str(len(byteStr) - 20) + " chars)"
  else:
    return byteStr
  
def test_codec_simple(m, str):
  bytes = m.encode(str)
  print char(str) + " = " + hex(bytes)
  strunmarshalled = m.decode(bytes)
  print "unmarshalled size: %i" % len(strunmarshalled)
  if (str != strunmarshalled):
    print "ERROR '" + char(str) + "' != '" + char(strunmarshalled) + "'"
    print "original    : "+hex(str)
    print "unmarshalled: "+hex(strunmarshalled)
   
def test_codec(m):
  test_codec_simple(m, "")
  test_codec_simple(m, "a")
  test_codec_simple(m, "b")
  test_codec_simple(m, "c")
  a256 = ""
  for i in range(1,256): a256+="a"
  a257 = a256+"a";
  a258 = a257+"a";
  a65336 = "";
  a65536 = "";
  a65537 = "";
  for i in range(1,65336): a65336+="a"
  for i in range(1,65536): a65536+="a"
  for i in range(1,65537): a65537+="a"
  a65538 = a65537+"a";
  
  test_codec_simple(m, a256)
  test_codec_simple(m, a257)
  test_codec_simple(m, a258)
  test_codec_simple(m, a65336)
  test_codec_simple(m, a65536)
  test_codec_simple(m, a65537)
  test_codec_simple(m, a65538)

print "testing RiverString"
test_codec(RiverStringCodec())
print "testing RiverByteArray"    
test_codec(RiverByteArrayCodec())    
    
      
