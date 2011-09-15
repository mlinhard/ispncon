'''
Created on Jul 18, 2011

@author: mlinhard
'''
from ispncon.codec import RiverStringCodec, RiverByteArrayCodec
from servermanagement import jpsgrep
import psutil
from xml.etree.ElementTree import Element, ElementTree, parse,\
  register_namespace
from ispncon.servermanagement import AS7ConfigXmlEditor

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

def test_psutil(): 
    pid = jpsgrep("name")
    if pid != -1:
      print psutil.Process(pid)

def test_xml():
  bla = Element("bla")
  subbla1 = Element("subbla1")
  subbla2 = Element("subbla2")
  subbla2.text = "text of subbla2"
  subbla1.attrib["foo"] = "bar"
  bla.append(subbla1)
  bla.append(subbla2)
  ElementTree(bla).write("test.xml", "UTF-8")

def test_xml_parse_and_write():
  editor = AS7ConfigXmlEditor("standalone.xml")
  editor.setHost("ddddd asdf")
  editor.save()

test_xml_parse_and_write()

