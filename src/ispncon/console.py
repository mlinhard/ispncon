#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Command parsing and execution
"""
from ispncon import ISPNCON_VERSION, HELP
from ispncon.client import CacheClient, fromString
import getopt
import shlex
import sys

__author__ = "Michal Linhard"
__copyright__ = "(C) 2011 Red Hat Inc."

class CommandExecutor:
  def __init__(self, client):
    self.client = client
    
  def _cmd_include(self, args):
    f = open(args[0], 'r')
    for line in f:
        self.execute(line)
    f.close()
  
  def _cmd_put(self, args):
    """options:
  -i <filename> don't specify inline string value, instead put the whole contents of the specified file
  -V <version> put only if version equals version given
  -l <lifespan> specifies lifespan, integer, number of seconds
  -I <maxidle> specifies max idle time
  -a put if absent, same as put but returns CONFLICT if value already exists 
     and doesn't put anything in that case"""
        
    try:
      opts1, args1 = getopt.getopt(args, "i:v:l:I:a", ["input-filename=", "version=", "lifespan=", "maxidle=", "put-if-absent"])
    except getopt.GetoptError:          
      print "ERROR Wrong put command syntax."
    filename=None
    version=None
    lifespan=None
    maxidle=None
    put_if_absent=False
    value=None
    for opt, arg in opts1:
        if opt in ("-i", "--input-filename"):
            filename = arg
        if opt in ("-v", "--version"):
            version = arg
        if opt in ("-l", "--lifespan"):
            try:
              lifespan = int(arg)
            except ValueError:
              print "ERROR converting lifespan. must be an integer."
              return
        if opt in ("-I", "--maxidle"):
            try:
              maxidle = int(arg)
            except ValueError:
              print "ERROR converting lifespan. must be an integer."
              return
        if opt in ("-a", "--put-if-absent"):
            put_if_absent = True
    if filename == None:
      if (len(args) < 2):
        print "ERROR You must supply key and either value or input filename."
        return
      value = args[1]
    else:
      if (len(args) > 1):
        print "ERROR You cannot supply both value and input filename in one get operation."
        return
      f = None
      try:
        f = open(filename, "r")
        value = f.read()
      except IOError:
        print "ERROR while reading file ", filename
      finally:
        if (f != None):
          f.close()
    self.client.put(args[0], value, version, lifespan, maxidle, put_if_absent)
      
      
  def _cmd_get(self, args):
    print "doing get", "args=", args
    print self.client.get(args[0])
  
  def _cmd_help(self, args):
    if (len(args) == 0):
      print "Supported operations: \n", "\n".join(sorted(["%s\t%s" % (x, HELP[x].split("\n")[0]) for x in HELP.keys()]))
      return
    helptext = HELP[args[0]]
    if (helptext == None):
      print "Unknown operation: ", args[0]
      return
    print helptext
    
  def execute(self, line):
    if (line == None or line.strip() == ""):
      return
    tokens = shlex.split(line)
    self.execute_cmd(tokens[0], tokens[1:])
    
  def execute_cmd(self, cmd, args):
    if cmd == "put":
      self._cmd_put(args)
    elif cmd == "get":
      self._cmd_get(args)
    elif cmd == "include":
      self._cmd_include(args)
    elif cmd == "help":
      self._cmd_help(args)
    else:
      print "ERROR unknown command:",cmd

def usage():
    print("USAGE: ispncon [options] <operation> <op_arguments>")
    print("    -c --client (default: hotrod, other possible values memcached, http)")
    print("    -h --host <host> (default: localhost) ")
    print("    -p --port <port> (default: 11222)")
    print("    -n --cache-name <cache_name> (default: default cache will be used)")
    print("    -v --version prints the ispncon version")
    print("    use operation help to get list of supported operations")
    print("    and help <operation> to display info on particular operation")
 
def main(args):
    try:
        opts, args = getopt.getopt(sys.argv[1:], "c:h:p:C:v", ["client=", "host=", "port=", "cache-name=", "version"])
    except getopt.GetoptError:          
        usage()                         
        sys.exit(2)     
    client = "hotrod"
    host = "localhost"
    port = "11222"
    cache = None
    for opt, arg in opts:
        if opt in ("-c", "--client"):
            client = arg
        if opt in ("-h", "--host"):
            host = arg
        if opt in ("-p", "--port"):
            port = arg
        if opt in ("-C", "--cache-name"):
            cache = arg
        if opt in ("-v", "--version"):
            print ISPNCON_VERSION
            sys.exit(0)
    cache_client = fromString(client, host, port, cache)
    executor = CommandExecutor(cache_client)
    if (len(args) == 0):
      print "Infinispan Console v%s" % ISPNCON_VERSION
      keepon = True
      while keepon:
        try:
          executor.execute(raw_input("> "))
        except EOFError:
          keepon = False
        except KeyboardInterrupt:
          keepon = False
      print "\nGood bye!"
    else:
      executor.execute_cmd(args[0], args[1:])
    
