#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Command parsing and execution
"""
from ispncon import ISPNCON_VERSION, HELP
from ispncon.client import fromString, CacheClientError, ConflictError,\
  NotFoundError
import getopt
import shlex
import sys

__author__ = "Michal Linhard"
__copyright__ = "(C) 2011 Red Hat Inc."

class CommandExecutionError(Exception):
  def __init__(self, msg, exit_code=1):
    self.msg = msg
    self.exit_code = exit_code

class CommandExecutor:
  def __init__(self, client_name, host, port, cache, exit_on_error):
    self.client_name = client_name
    self.host = host
    self.port = port
    self.cache = cache
    self.client = None
    self.exit_on_error = exit_on_error
    exit_on_error
  # get the client lazily
  def _get_client(self):
    if self.client == None:
      try:
        self.client = fromString(self.client_name, self.host, self.port, self.cache)
      except CacheClientError as e:
        raise e
      except Exception as e:
        self._error("creating client: %s" % e.args)
    return self.client
      
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
      self._error("Wrong put command syntax.")
    filename = None
    version = None
    lifespan = None
    maxidle = None
    put_if_absent = False
    value = None
    for opt, arg in opts1:
        if opt in ("-i", "--input-filename"):
            filename = arg
        if opt in ("-v", "--version"):
            version = arg
        if opt in ("-l", "--lifespan"):
            try:
              lifespan = int(arg)
            except ValueError:
              self._error("Converting lifespan. must be an integer.")
        if opt in ("-I", "--maxidle"):
            try:
              maxidle = int(arg)
            except ValueError:
              self._error("converting lifespan. must be an integer.")
        if opt in ("-a", "--put-if-absent"):
            put_if_absent = True
    if filename == None:
      if (len(args1) < 2):
        self._error("You must supply key and either value or input filename.")
      value = args1[1]
    else:
      if (len(args1) > 1):
        self._error("You cannot supply both value and input filename in one get operation.")
      f = None
      try:
        f = open(filename, "r")
        value = f.read()
      except IOError:
        self._error("while reading file %s" % filename)
      finally:
        if (f != None):
          f.close()
    self._get_client().put(args1[0], value, version, lifespan, maxidle, put_if_absent)
    print "STORED"
      
  def _cmd_get(self, args):
    _client = self._get_client()
    try:
      opts1, args1 = getopt.getopt(args, "o:v", ["output-filename=", "version"])
    except getopt.GetoptError:          
      self._error("Wrong get command syntax.")
    output_filename = None
    get_version = False
    if (len(args1) != 1):
      self._error("You must supply key.")
    for opt, arg in opts1:
        if opt in ("-o", "--output-filename"):
            output_filename = arg
        if opt in ("-v", "--version"):
            get_version = True
    version = None
    value = None
    if get_version:
      version, value = _client.get(args1[0], True)
      print "VERSION %s" % version
    else:
      value = _client.get(args1[0], False)

    if output_filename == None:
      print value
    else:
      try:
        outfile = open(output_filename, "w")
        outfile.write(value)
        outfile.close()
      except IOError:
        raise CacheClientError("writing file %s" % output_filename)
      
  def _cmd_delete(self, args):
    _client = self._get_client()
    try:
      opts1, args1 = getopt.getopt(args, "v:", ["version="])
    except getopt.GetoptError:          
      self._error("Wrong delete command syntax.")
    version = None
    if (len(args1) != 1):
      self._error("You must supply key.")
    for opt, arg in opts1:
        if opt in ("-v", "--version"):
            version = arg
    if (len(args1) != 1):
      self._error("You must supply key.")
    _client.delete(args1[0], version)
    print "DELETED"
    
  
  def _cmd_help(self, args):
    if (len(args) == 0):
      print "Supported operations: \n", "\n".join(sorted(["%s\t%s" % (x, HELP[x].split("\n")[0]) for x in HELP.keys()]))
      return
    helptext = HELP.get(args[0])
    if (helptext == None):
      self._error("Can't display help. Unknown operation: %s" % args[0])
    print helptext
  
  def _error(self, msg):
    raise CommandExecutionError(msg)
    
  def _possiblyexit(self, exit_code):
    if self.exit_on_error:
      sys.exit(exit_code)
      
  def execute(self, line):
    if (line == None or line.strip() == ""):
      return
    tokens = shlex.split(line)
    self.execute_cmd(tokens[0], tokens[1:])
    
  def execute_cmd(self, cmd, args):
    try:
      if cmd == "put":
        self._cmd_put(args)
      elif cmd == "get":
        self._cmd_get(args)
      elif cmd == "delete":
        self._cmd_delete(args)
      elif cmd == "include":
        self._cmd_include(args)
      elif cmd == "help":
        self._cmd_help(args)
      else:
        self._error("unknown command: %s" % cmd)
    except CommandExecutionError as e:
      print "ERROR", e.msg
      self._possiblyexit(e.exit_code)
    except NotFoundError as e:
      print "NOT_FOUND"
      self._possiblyexit(2)
    except ConflictError as e:
      print "CONFLICT"
      self._possiblyexit(3)
    except CacheClientError as e: # most general cache client error, it has to be handled last
      print "ERROR", e.msg
      self._possiblyexit(1)

def usage():
  print("USAGE: ispncon [options] <operation> [operation_options] <op_arguments>")
  print("    -c --client         client to use (default: hotrod, other possible values memcached, rest)")
  print("    -h --host <host>    hostname/ip address to connect to (default: localhost) ")
  print("    -p --port <port>    port to connect to (default: 11222(hotrod), 11211(memcached), 8080(rest))")
  print("    -v --version        prints the ispncon version and exits")
  print("    -e --exit-on-error  if operation fails, don't print ERROR output, but fail with error exit code")
  print("    use operation help to get list of supported operations")
  print("    or help <operation> to display info on particular operation")
 
def main(args):
  try:
    opts, args = getopt.getopt(sys.argv[1:], "c:h:p:C:v:e", ["client=", "host=", "port=", "cache-name=", "version", "exit-on-error"])
  except getopt.GetoptError:          
    usage()                         
    sys.exit(2)     
  client = "hotrod"
  host = "localhost"
  port = "11222"
  cache = None
  exit_on_error = False
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
    if opt in ("-e", "--exit-on-error"):
      exit_on_error = True
  executor = CommandExecutor(client, host, port, cache, exit_on_error)
  isatty = sys.stdin.isatty()
  prompt = "> " if isatty else ""
  if (len(args) == 0):
    if isatty:
      print "Infinispan Console v%s" % ISPNCON_VERSION
    keepon = True
    while keepon:
      try:
        executor.execute(raw_input(prompt))
      except EOFError:
        keepon = False
      except KeyboardInterrupt:
        keepon = False
    if isatty:
      print "\nGood bye!"
  else:
    executor.execute_cmd(args[0], args[1:])
