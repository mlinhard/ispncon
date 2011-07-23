#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Command parsing and execution
"""
from ispncon import ISPNCON_VERSION, HELP, USAGE, DEFAULT_CACHE_NAME,\
  TRUE_STR_VALUES
from ispncon.client import CacheClientError, ConflictError, NotFoundError
from ispncon.codec import CODEC_NONE, CodecError
import ConfigParser
import getopt
import ispncon
import os
import shlex
import sys

__author__ = "Michal Linhard"
__copyright__ = "(C) 2011 Red Hat Inc."

MAIN_CONFIG_SECTION = "ispncon"
KNOWN_CONFIG_KEYS = ["client_type", "host", "port", "cache", "exit_on_error", "default_codec", "rest.server_url", "rest.content_type", "hotrod.use_river_string_keys"]

class Config(dict):
  def _override_with_user_config(self):
    user_cfg_file = os.path.expanduser("~/.ispncon")
    if not os.path.exists(user_cfg_file):
      return
    cfgp = ConfigParser.ConfigParser()
    cfgp.read(user_cfg_file)
    for key, value in cfgp.items(MAIN_CONFIG_SECTION):
      self[key]=value
    for section in cfgp.sections():
      if section != MAIN_CONFIG_SECTION:
        for key, value in cfgp.items(section):
          self[section + "." + key] = value
        
  def __init__(self, *args, **kw):
    super(Config, self).__init__(*args, **kw)
    # set defaults
    self["client_type"] = "hotrod"
    self["host"] = "localhost"
    self["port"] = "11222"
    self["cache"] = DEFAULT_CACHE_NAME
    self["exit_on_error"] = "False"
    self["default_codec"] = CODEC_NONE
    self["rest.server_url"] = "/infinispan-server-rest/rest"
    self["rest.content_type"] = "text/plain"
    self["hotrod.use_river_string_keys"] = "True"
    # override with whatever is in ~/.ispncon file
    self._override_with_user_config()
    
  def __str__(self):
    str = ""
    for  key in KNOWN_CONFIG_KEYS:
      str += "%s = %s\n" % (key, self[key])
    return str
  
  def __setitem__(self, key, value):
    if not key in KNOWN_CONFIG_KEYS:
      self._error("Unknown config key: %s" % key)
    super(Config, self).__setitem__(key, value)

  def _error(self, msg):
    raise CommandExecutionError(msg)
  
  def _parse_section_key(self, section_key):
    v = section_key.split(".")
    if len(v) == 1:
      return "ispncon", v[0]
    elif len(v) == 2:
      return v[0], v[1]
    else:
      self._error("Invalid key format. Must be <section>.<key>")

  def save(self):
    f = open(os.path.expanduser("~/.ispncon"), "w")
    cfgp = ConfigParser.ConfigParser()

    for section_key in self.iterkeys():
      section, key = self._parse_section_key(section_key)
      if not cfgp.has_section(section):
        cfgp.add_section(section)
      cfgp.set(section, key, self[section_key])

    cfgp.write(f)

class CommandExecutionError(Exception):
  def __init__(self, msg, exit_code=1):
    self.msg = msg
    self.exit_code = exit_code

class CommandExecutor:
  def __init__(self, config):
    self.config = config
    self.exit_on_error = (self.config["exit_on_error"] in TRUE_STR_VALUES)
    self.default_codec = ispncon.codec.fromString(self.config["default_codec"])
    self.client = None
    
  # get the client lazily
  def _get_client(self):
    if self.client == None:
      try:
        self.client = ispncon.client.fromString(self.config)
      except CacheClientError as e:
        raise e
      except Exception as e:
        self._error("creating client: %s" % str(e.args))
    return self.client
      
  def _optionally_encode(self, codec, value):
    if (codec == None):
      if (self.default_codec == None):
        return value
      else:
        return self.default_codec.encode(value)
    else:
      currentCodec = ispncon.codec.fromString(codec)
      if currentCodec == None:
        return value
      else:
        return currentCodec.encode(value)

  def _optionally_decode(self, codec, value):
    if (codec == None):
      if (self.default_codec == None):
        return value
      else:
        return self.default_codec.decode(value)
    else:
      currentCodec = ispncon.codec.fromString(codec)
      if currentCodec == None:
        return value
      else:
        return currentCodec.decode(value)

  def _cmd_include(self, args):
    if (len(args) != 1):
      self._error("Wrong include command syntax.")
      
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
      opts1, args1 = getopt.getopt(args, "i:v:l:I:ae:", ["input-filename=", "version=", "lifespan=", "max-idle=", "put-if-absent", "encode="])
    except getopt.GetoptError:          
      self._error("Wrong put command syntax.")
    filename = None
    version = None
    lifespan = None
    maxidle = None
    put_if_absent = False
    value = None
    codec = None
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
        if opt in ("-I", "--max-idle"):
            try:
              maxidle = int(arg)
            except ValueError:
              self._error("converting lifespan. must be an integer.")
        if opt in ("-a", "--put-if-absent"):
            put_if_absent = True
        if opt in ("-e", "--encode"):
            codec = arg
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
    try:
      encoded_value = self._optionally_encode(codec, value)
    except CodecError as e:
      self._error(e.args[0]);
    self._get_client().put(args1[0], encoded_value, version, lifespan, maxidle, put_if_absent)
    print "STORED"
      
  def _cmd_get(self, args):
    _client = self._get_client()
    try:
      opts1, args1 = getopt.getopt(args, "o:vd:", ["output-filename=", "version", "decode="])
    except getopt.GetoptError:          
      self._error("Wrong get command syntax.")
    output_filename = None
    get_version = False
    codec = None
    if (len(args1) != 1):
      self._error("You must supply key.")
    for opt, arg in opts1:
        if opt in ("-o", "--output-filename"):
            output_filename = arg
        if opt in ("-v", "--version"):
            get_version = True
        if opt in ("-d", "--decode"):
            codec = arg
    version = None
    value = None
    if get_version:
      version, value = _client.get(args1[0], True)
      print "VERSION %s" % version
    else:
      value = _client.get(args1[0], False)

    try:
      decoded_value = self._optionally_decode(codec, value)
    except CodecError as e:
      self._error(e.args[0]);
    if output_filename == None:
      print decoded_value
    else:
      try:
        outfile = open(output_filename, "w")
        outfile.write(decoded_value)
        outfile.close()
      except IOError:
        self._error("writing file %s" % output_filename)

  def _cmd_version(self, args):
    _client = self._get_client()
    if (len(args) != 1):
      self._error("You must supply key.")
    print _client.version(args[0])

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
      print "Supported operatiotype: <class 'ispncon.console.Config'>ns: \n", "\n".join(sorted(["%s\t\t%s" % (x, HELP[x].split("\n")[0]) for x in HELP.keys()]))
      return
    helptext = HELP.get(args[0])
    if (helptext == None):
      self._error("Can't display help. Unknown operation: %s" % args[0])
    print helptext
  
  def _cmd_clear(self, args):
    if (len(args) != 0):
      self._error("Clear command doesn't have any arguments.")
    self._get_client().clear()
    print "DELETED"

  def _cmd_exists(self, args):
    _client = self._get_client()
    if (len(args) < 1):
      self._error("You must supply key.")
    if (len(args) > 1):
      self._error("Wrong exists command syntax.")
    _client.exists(args[0])
    print "EXISTS"

  def _cmd_config(self, args):
    if (len(args) == 0):
      print self.config
      return
    if (len(args) == 1):
      if (args[0] != "save"):
        self._error("Wrong config command syntax.")
      else:
        self.config.save()
        print "STORED"
        return
    if (len(args) > 2):
      self._error("Wrong config command syntax.")

    self.config[args[0]] = args[1]
    self.client = None # throw away the old client
    self._get_client() # try to create new one
    print "STORED"
  
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
      elif cmd == "version":
        self._cmd_version(args)
      elif cmd == "delete":
        self._cmd_delete(args)
      elif cmd == "include":
        self._cmd_include(args)
      elif cmd == "help":
        self._cmd_help(args)
      elif cmd == "clear":
        self._cmd_clear(args)
      elif cmd == "exists":
        self._cmd_exists(args)
      elif cmd == "config":
        self._cmd_config(args)
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
 
def main(args):
  try:
    opts, args = getopt.getopt(sys.argv[1:], "c:h:p:C:veP:", ["client=", "host=", "port=", "cache-name=", "version", "exit-on-error", "config="])
  except getopt.GetoptError:          
    print USAGE              
    sys.exit(2)     

  config = Config() # values here will be overriden by anything passed in commandline
  for opt, arg in opts:
    if opt in ("-c", "--client"):
      config["client_type"] = arg
    if opt in ("-h", "--host"):
      config["host"] = arg
    if opt in ("-p", "--port"):
      config["port"] = arg
    if opt in ("-C", "--cache-name"):
      config["cache"] = arg
    if opt in ("-v", "--version"):
      print ISPNCON_VERSION
      sys.exit(0)
    if opt in ("-e", "--exit-on-error"):
      config["exit_on_error"] = "True"
    if opt in ("-P", "--config"):
      params = arg.split(" ")
      if (len(params) != 2):
        print ISPNCON_VERSION
        sys.exit(0)
      try:
        config[params[0]] = params[1]
      except CommandExecutionError as e:
        print e.msg
        sys.exit(1)

  executor = CommandExecutor(config)
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
