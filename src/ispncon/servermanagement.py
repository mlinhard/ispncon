#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Server management related code.
"""
from ispncon import TRUE_STR_VALUES, CommandExecutionError
from subprocess import STDOUT
from xml.etree.ElementTree import register_namespace, parse
import getopt
import io
import os
import psutil
import re
import shutil
import signal
import subprocess
import time
from zipfile import ZipFile

XMLNS_DOMAIN = "urn:jboss:domain:1.0"
BAK = ".ispncon.backup"
DEFAULT_JAVA_OPTS_INTERNAL_EDG = "-Xms64m -Xmx256m -XX:MaxPermSize=128m -Djava.net.preferIPv4Stack=true -Dorg.jboss.resolver.warning=true -Dsun.rmi.dgc.client.gcInterval=3600000 -Dsun.rmi.dgc.server.gcInterval=3600000 -Djboss.modules.system.pkgs=org.jboss.byteman"
DEFAULT_DEBUG_PORT = 8787
DEFAULT_REST_WAR_NAME = "infinispan-server-rest.war"

register_namespace("domain"       , XMLNS_DOMAIN) 
register_namespace("logging"      , "urn:jboss:domain:logging:1.0")
register_namespace("transactions" , "urn:jboss:domain:transactions:1.0") 
register_namespace("web"          , "urn:jboss:domain:web:1.0")
register_namespace("jgroups"      , "urn:jboss:domain:jgroups:1.0") 
register_namespace("infinispan"   , "urn:jboss:domain:infinispan:1.0") 
register_namespace("endpoint"     , "urn:redhat:domain:datagrid:endpoint:1.0") 
register_namespace("deplscanner"  , "urn:jboss:domain:deployment-scanner:1.0")
register_namespace("ee"           , "urn:jboss:domain:ee:1.0")
register_namespace("jaxrs"        , "urn:jboss:domain:jaxrs:1.0") 
register_namespace("jmx"          , "urn:jboss:domain:jmx:1.0")
register_namespace("naming"       , "urn:jboss:domain:naming:1.0") 
register_namespace("remoting"     , "urn:jboss:domain:remoting:1.0") 
register_namespace("security"     , "urn:jboss:domain:security:1.0")
register_namespace("threads"      , "urn:jboss:domain:threads:1.0")

PID_FILE_TEMPLATE = "/tmp/ispncon.server.%s.pid"
OUT_FILE_TEMPLATE = "/tmp/ispncon.server.%s.out"
ACTIVE_WAIT_SLEEP = 0.2

def jpsgrep(str):
  """find first java process id that contains str among it's parameters
     if no such process is found returns -1
  """
  pids = psutil.get_pid_list()
  for pid in pids:
    proc = psutil.Process(pid)
    if len(proc.cmdline) > 0 and proc.cmdline[0].endswith("java"): 
      for arg in proc.cmdline[1:]:
        if arg.find(str) != -1:
          return pid
  return -1

def tailFile(file, lines):
  f = io.open(file, "rb")
  BUFSIZ = 1024
  f.seek(0, io.SEEK_END)
  bytes = f.tell()
  size = lines
  block = -1
  data = []
  while size > 0 and bytes > 0:
    if (bytes - BUFSIZ > 0):
      # Seek back one whole BUFSIZ
      f.seek(block*BUFSIZ, 2)
      # read BUFFER
      data.append(f.read(BUFSIZ))
    else:
      # file too small, start from begining
      f.seek(0,0)
      # only read what was not read
      data.append(f.read(bytes))
    linesFound = data[-1].count('\n')
    size -= linesFound
    bytes -= BUFSIZ
    block -= 1
  f.close()
  return ''.join(data).splitlines()[-lines:]

def folowFrom(file, offset):
    """Follow a file from specific offset"""
    try:
      # wait until file exists
      while not os.path.exists(file):
        time.sleep(ACTIVE_WAIT_SLEEP)

      f = io.open(file, "r")
      f.seek(offset, io.SEEK_SET)
      line = f.readline()
      while True:
        if line: #line available, print it!
          print line,
        else: # line not available
          time.sleep(ACTIVE_WAIT_SLEEP)
        line = f.readline()
    except KeyboardInterrupt:
      f.close()

def findTailOffset(file, lines):
  f = io.open(file, "rb")
  BUFSIZ = 1024
  f.seek(0, io.SEEK_END)
  bytes = f.tell()
  size = lines
  block = -1
  data = None
  while size > 0 and bytes > 0:
    if (bytes - BUFSIZ > 0):
      # Seek back one whole BUFSIZ
      f.seek(block*BUFSIZ, io.SEEK_END)
      # read BUFFER
      data = f.read(BUFSIZ)
    else:
      # file too small, start from begining
      f.seek(0, io.SEEK_SET)
      # only read what was not read
      data = f.read(bytes)
    linesFound = data.count('\n')
    size -= linesFound
    bytes -= BUFSIZ
    block -= 1
  if (bytes - BUFSIZ > 0):
    block += 1
    f.seek(block*BUFSIZ, io.SEEK_END)
  else:
    f.seek(0, io.SEEK_SET)
  while size <= 0:
    f.readline()
    size += 1
  pos = f.tell()
  f.close()
  return pos

def waitForLine(file, patterns):
  """Wait until a line that matches a pattern appears in the given file. The file might be a constantly growing log."""
  try:
    # wait until file exists
    while not os.path.exists(file):
      time.sleep(ACTIVE_WAIT_SLEEP)

    # wait until the pattern is found in a line
    f = io.open(file, "r")
    line = f.readline()
    while True:
      if line:
        for result, pattern in patterns.iteritems():
          if re.match(pattern, line): # line matches
            return result
          else: # line doesn't match the pattern
            line = f.readline()
      else: # line not available
        time.sleep(ACTIVE_WAIT_SLEEP)
        line = f.readline()
    f.close()
  except KeyboardInterrupt:
    print "Waiting interrupted."

class ServerManagerException(Exception):
  """Exception in ServerManager"""
  pass

class InvalidServerConfigException(ServerManagerException):
  """when server config is INVALID"""
  pass

class ServerManager():
  """Superclass for server managers"""

  def __init__(self, ispncon_config, server_name):
    self._ispncon_config = ispncon_config
    self._config = self._get_server_config_with_defaults(server_name)
    self._name = server_name

  def _get_server_config_with_defaults(self, server_name):
    server_config = self._ispncon_config.get_section("server:" + server_name)

    if server_config.get("listen_addr") == None:
      dla = self._ispncon_config.get("default_listen_addr")
      if dla:
        server_config["listen_addr"] = dla
    if server_config.get("listen_port") == None:
      dlp = self._ispncon_config.get("default_listen_port")
      if dlp:
        server_config["listen_port"] = dlp
    if server_config.get("java_opts") == None:
      djo = self._ispncon_config.get("default_java_opts")
      if djo:
        server_config["java_opts"] = djo

    return server_config

  def _applyConfigOverrides(self, overrides):
    for key, value in overrides.iteritems():
      self._config[key] = value

  def start(self, wait=False, config_overrides={}):
    """Start the server instance"""
    raise ServerManagerException("Not implemented")

  def stop(self, kill=False, wait=False, config_overrides={}):
    """Stop the server instance"""
    raise ServerManagerException("Not implemented")

  def out(self, mode="tail", num_lines=10, config_overrides={}):
    raise ServerManagerException("Not implemented")

  def getStatus(self):
    raise ServerManagerException("Not implemented")

  def jstack(self):
    raise ServerManagerException("jstack command is not supported for this server manager")

class ScriptServerManager(ServerManager):
  """ServerManager that uses custom management script to controll the server"""

  def __init__(self, ispncon_config, server_name, script):
    self._script = script
    ServerManager.__init__(self, ispncon_config, server_name)
    if not os.path.exists(script):
      raise ServerManagerException("configuration problem in server \"%s\": script doesn't exist: %s" % (server_name, script))
    if not os.access(script, os.X_OK):
      raise ServerManagerException("configuration problem in server \"%s\": script isn't executable: %s" % (server_name, script))

  def start(self, wait=False, config_overrides={}):
    self.executeCommand("start")

  def stop(self, kill=False, wait=False, config_overrides={}):
    self.executeCommand("stop")

  def out(self, mode="tail", num_lines=10, config_overrides={}):
    self.executeCommand("out")

  def executeCommand(self, command):
    args = [self._script]
    if command == "start":
      cfg_listen_addr = self._config.pop("listen_addr", None)
      cfg_listen_port = self._config.pop("listen_port", None)
      if (cfg_listen_addr != None):
        args.append("-h")
        args.append(cfg_listen_addr)
      if (cfg_listen_port != None):
        args.append("-p")
        args.append(cfg_listen_port)
      cfg_debug = self._config.pop("debug", None)
      if (cfg_debug != None and cfg_debug in TRUE_STR_VALUES):
        cfg_debug_port = self._config.pop("debug_port", None)
        cfg_debug_suspend = self._config.pop("debug_suspend", None)
        if cfg_debug_port == None:
          cfg_debug_port = DEFAULT_DEBUG_PORT
        if (cfg_debug_suspend != None and cfg_debug_suspend in TRUE_STR_VALUES):
          args.append("-D")
          args.append(cfg_debug_port)
        else:
          args.append("-d")
          args.append(cfg_debug_port)
    if command == "stop":
      cfg_kill = self._config.pop("kill", None)
      if cfg_kill != None and cfg_kill in TRUE_STR_VALUES:
        args.append("-k")
    #pass rest of the config parameters via -P options
    for Pkey, Pvalue in self._config:
      args.append("-P")
      args.append("\"%s %s\"" % (Pkey, Pvalue))

    args.append(command)
    args.append(self._name)

    subproc = subprocess.Popen(args)

    try:
      subproc.wait()
    except KeyboardInterrupt:
      subproc.terminate()


class BuiltInServerManager(ServerManager):
  """Common superclass for built-in server managers"""

  def writePid(self, pid):
    pidfile = open(PID_FILE_TEMPLATE % self._name, "w")
    pidfile.write(str(pid))
    pidfile.close()

class JavaServerManager(BuiltInServerManager):
  """Server manager superclass for all JVM based servers"""

  def findPid(self):
    return jpsgrep("-Dispncon.server.name="+self._name)

  def checkRunning(self):
    if self.findPid() != -1:
      raise ServerManagerException("Server is already running.")

  def getStatus(self):
    """return server status"""
    try:
      pid = self.findPid()
      pidfile = PID_FILE_TEMPLATE % self._name
      if pid == -1:
        if os.path.exists(pidfile):
          os.remove(pidfile)
        outfile = OUT_FILE_TEMPLATE % self._name
        if os.path.exists(outfile):
          os.remove(outfile)
        return "STOPPED"
      else:
        if not os.path.exists(pidfile):
          self.writePid(pid)
        return "RUNNING"
    except Exception as e:
      raise ServerManagerException(e.args[0])

  def stop(self, kill=False, wait=False, config_overrides={}):
    try:
      self._applyConfigOverrides(config_overrides)
      pid = self.findPid()
      if pid == -1:
        raise ServerManagerException("Server is not running.")
      else:
        if kill:
          os.kill(pid, signal.SIGKILL)
        else:
          os.kill(pid, signal.SIGTERM)
          if wait:
            while self.findPid() != -1:
              time.sleep(ACTIVE_WAIT_SLEEP)
      pidfile = PID_FILE_TEMPLATE % self._name
      outfile = OUT_FILE_TEMPLATE % self._name
      if os.path.exists(pidfile):
        os.remove(pidfile)
      if os.path.exists(outfile):
        os.remove(outfile)
      print "SERVER_STOP " + self._name
    except Exception as e:
      raise ServerManagerException(e.args[0])

  def out(self, mode="tail", num_lines=10, config_overrides={}):
    self._applyConfigOverrides(config_overrides)
    if self.findPid() == -1:
      raise ServerManagerException("Server is not running.")
    if mode == "tail":
      taillines = tailFile(OUT_FILE_TEMPLATE % self._name, num_lines)
      for line in taillines:
        print line
    elif mode == "full":
      f = open(OUT_FILE_TEMPLATE % self._name, "r")
      for line in f:
        print line,
    elif mode == "follow":
      pos = findTailOffset(OUT_FILE_TEMPLATE % self._name, num_lines)
      folowFrom(OUT_FILE_TEMPLATE % self._name, pos)
    else:
      raise ServerManagerException("Unknown mode for out command: %s. Only tail|full|follow are supported." % mode)

  def jstack(self):
    try:
      pid = self.findPid()
      if pid == -1:
        raise ServerManagerException("Server is not running.")

      p = subprocess.Popen([ "jstack", str(pid) ])
      p.wait()
    except ServerManagerException as e:
      raise e
    except Exception as e:
      raise ServerManagerException(e.args[0])


class InfinispanServerManager(JavaServerManager):
  """ServerManager for standard community Infinispan server"""

  def __init__(self, ispncon_config, server_name):
    BuiltInServerManager.__init__(self, ispncon_config, server_name)
    self.ispn_home = self._config.get("ispn_home")
    if self.ispn_home == None:
      raise InvalidServerConfigException("ispn_home config key is required for hotrod/memcached server manager")
    self._validate_ispn_home(self.ispn_home)

  def _validate_ispn_home(self, path):
    if not (os.path.exists(path) and os.path.isdir(path)):
      raise InvalidServerConfigException("ispn_home directory doesn't exist: %s" % path)
    checkpath = path + "/bin"
    if not (os.path.exists(checkpath) and os.path.isdir(checkpath)):
      raise InvalidServerConfigException("Invalid ispn_home directory: %s. Missing bin subdirectory." % path)
    checkpath = path + "/bin/startServer.sh"
    if not (os.path.exists(checkpath) and os.path.isfile(checkpath)):
      raise InvalidServerConfigException("Invalid ispn_home directory: %s. Missing startServer.sh script." % path)
    if not os.access(checkpath, os.X_OK):
      raise InvalidServerConfigException("Problem in ispn_home directory: %s. startServer.sh is not executable." % path)

  def start(self, wait=False, config_overrides={}):
    try:
      self._applyConfigOverrides(config_overrides)
      self.checkRunning()

      if wait:
        print "WARNING: wait-for-start not supported in memcached/hotrod server manager."

      #TODO: change for Windows
      binary = self.ispn_home + "/bin/startServer.sh"

      java_opts = self._config.get("java_opts")
      debug = self._config.get("debug")
      if debug != None and debug in TRUE_STR_VALUES:
        debug_suspend = self._config.get("debug_suspend")
        debug_port = self._config.get("debug_port", DEFAULT_DEBUG_PORT)
        suspend = "n"
        if debug_suspend != None and debug_suspend in TRUE_STR_VALUES:
          suspend = "y"
        java_opts = "%s -Xrunjdwp:transport=dt_socket,address=%s,server=y,suspend=%s" % (java_opts, debug_port, suspend)
      java_opts += " -Dispncon.server.name=%s" % self._name

      args = [binary, "-r", self._config["type"]]
      listen_addr = self._config.get("listen_addr")
      if listen_addr:
        args.append("-l")
        args.append(listen_addr)
      listen_port = self._config.get("listen_port")
      if listen_port:
        args.append("-p")
        args.append(listen_port)
      config_xml = self._config.get("config_xml")
      if config_xml:
        args.append("-c")
        args.append(config_xml)

      env1 = { "JVM_PARAMS" : java_opts, "JAVA_HOME" : os.environ["JAVA_HOME"] }

      outfile_name = OUT_FILE_TEMPLATE % self._name
      outfile = open(outfile_name, 'w')

      #here we're just spawning a process and ending this one
      p = subprocess.Popen(args, env=env1, stdout=outfile, stderr=STDOUT)
      self.writePid(p.pid)
      print "SERVER_START " + self._name
    except Exception as e:
      raise ServerManagerException(e.args[0])

class AS7ConfigXmlEditor:
  """Encapsulates the knowledge about structure of standalone.xml configuration file for AS7"""
  def __init__(self, path):
    self._path = path
    self._tree = parse(self._path)

  def _getxpath(self, xpath, *namespaces):
    return self._tree.getroot().findall(xpath.format(*[("{%s}" % s) for s in namespaces]))

  def setAllInterfaces(self, addr):
    inet_addrs = self._getxpath("{0}interfaces/{0}interface/{0}inet-address", XMLNS_DOMAIN)
    if inet_addrs != None:
      for inet_addr in inet_addrs:
        inet_addr.attrib["value"] = addr

  def save(self):
    backupxml = self._path + BAK
    if not os.path.exists(backupxml):
      shutil.copyfile(self._path, backupxml)
    self._tree.write(self._path, encoding="UTF-8")

class AS7BasedServerManager(JavaServerManager):
  """ServerManager for servers based on JBoss AS 7"""

  def __init__(self, ispncon_config, server_name):
    JavaServerManager.__init__(self, ispncon_config, server_name)
    self.jboss_home = self._config.get("jboss_home")
    if self.jboss_home == None:
      raise InvalidServerConfigException("jboss_home config key is required for AS7 based server manager")
    self._validate_jbossas7_home(self.jboss_home)

  def _validate_jbossas7_home(self, path):
    if not (os.path.exists(path) and os.path.isdir(path)):
      raise InvalidServerConfigException("jboss_home directory doesn't exist: %s" % path)
    checkpath = path + "/bin"
    if not (os.path.exists(checkpath) and os.path.isdir(checkpath)):
      raise InvalidServerConfigException("Invalid jboss_home directory: %s. Missing bin subdirectory." % path)
    checkpath = path + "/standalone"
    if not (os.path.exists(checkpath) and os.path.isdir(checkpath)):
      raise InvalidServerConfigException("Invalid jboss_home directory: %s. Missing standalone subdirectory." % path)
    checkpath = path + "/bin/standalone.sh"
    if not (os.path.exists(checkpath) and os.path.isfile(checkpath)):
      raise InvalidServerConfigException("Invalid jboss_home directory: %s. Missing standalone.sh script." % path)
    if not os.access(checkpath, os.X_OK):
      raise InvalidServerConfigException("Problem in jboss_home directory: %s. standalone.sh is not executable." % path)
    if not (os.path.exists(checkpath) and os.path.isfile(checkpath)):
      raise InvalidServerConfigException("Invalid jboss_home directory: %s. Missing standalone.xml config file." % path)

  def startAS7(self, wait=False):
    try:
      #TODO: change for Windows
      binary = self.jboss_home + "/bin/standalone.sh"
      standaloneXml = self.jboss_home + "/standalone/configuration/standalone.xml"

      # user supplied config exists
      config_xml = self._config.get("config_xml")
      if config_xml != None:
        backupxml = standaloneXml + BAK
        if not os.path.exists(backupxml):
          shutil.copyfile(self._path, backupxml)
        shutil.copyfile(config_xml, standaloneXml) #overwrite old standalone.xml

      # we want to change hostname in the config
      listen_addr = self._config.get("listen_addr")
      if (listen_addr != None):
        editor = AS7ConfigXmlEditor(standaloneXml)
        editor.setAllInterfaces(listen_addr)
        editor.save() # this will create backup if previous step didn't

      if (self._config.get("listen_port") != None):
        print "WARNING: listen_port config key is ignored in AS7 based server manager"

      java_opts = self._config.get("java_opts", "")
      debug = self._config.get("debug")
      if debug != None and debug in TRUE_STR_VALUES:
        debug_suspend = self._config.get("debug_suspend")
        debug_port = self._config.get("debug_port", DEFAULT_DEBUG_PORT)
        suspend = "n"
        if debug_suspend != None and debug_suspend in TRUE_STR_VALUES:
          suspend = "y"
        java_opts = "%s -Xrunjdwp:transport=dt_socket,address=%s,server=y,suspend=%s" % (java_opts, debug_port, suspend)
      java_opts += " -Dispncon.server.name=%s" % self._name

      args = [binary]
      env1 = { "JAVA_OPTS" : java_opts }

      outfile_name = OUT_FILE_TEMPLATE % self._name
      outfile = open(outfile_name, 'w')

      #here we're just spawning a process and ending this one
      p = subprocess.Popen(args, env=env1, stdout=outfile, stderr=STDOUT)
      self.writePid(p.pid)

      if (wait):
        result = waitForLine(outfile_name, { "ok" : ".*[org\.jboss\.as].*started in.*", "error" : ".*[org\.jboss\.as].*started (with errors) in.*" })
        if result == "ok":
          print "SERVER_START " + self._name
        elif result == "error":
          print "SERVER_START_WITH_ERRORS " + self._name
      else:
        print "SERVER_START " + self._name
    except Exception as e:
      raise ServerManagerException(e.args[0])


class EDG6ServerManager(AS7BasedServerManager):
  """ServerManager for JBoss Enterprise Datagrid 6"""

  def __init__(self, ispncon_config, server_name):
    AS7BasedServerManager.__init__(self, ispncon_config, server_name)
    if self._config.get("java_opts") == None:
      self._config["java_opts"] = DEFAULT_JAVA_OPTS_INTERNAL_EDG

  def start(self, wait=False, config_overrides={}):
    self._applyConfigOverrides(config_overrides)
    self.checkRunning()
    self.startAS7(wait)


class AS7RESTServerManager(AS7BasedServerManager):
  """ServerManager for REST server module + AS7 combination"""

  def __init__(self, ispncon_config, server_name):
    AS7BasedServerManager.__init__(self, ispncon_config, server_name)
    if self._config.get("deployment_name") == None:
      self._config["deployment_name"] = DEFAULT_REST_WAR_NAME

  def start(self, wait=False, config_overrides={}):
    self._applyConfigOverrides(config_overrides)
    self.checkRunning()
    self.checkRestWar()
    self.startAS7(wait)

  def checkRestWar(self):
    #check whether we need to create and deploy the WAR
    deployment_name = self._config["deployment_name"]
    deployment_path = self.jboss_home + "/standalone/deployments/" + deployment_name;
    if not os.path.exists(deployment_path):
      ispn_home = self._config.get("ispn_home")
      if not ispn_home:
        raise ServerManagerException("ispn_home is needed to install Infinispan REST server WAR deployment.")
      deployment_source = ispn_home + "/modules/rest/infinispan-server-rest.war"
      shutil.copyfile(deployment_source, deployment_path)
      ispn_cfg = self._config.get("infinispan_config_xml")
      if ispn_cfg:
        if not os.path.exists(ispn_cfg):
          raise ServerManagerException("the config file specified in infinispan_config_xml doesn't exist")
        warzip = ZipFile(deployment_path, "a")
        warzip.write(ispn_cfg, "WEB-INF/classes/infinispan.xml")
        warzip.close()
    else:
      #if deployment exists but is failed, retry the deployment on startup
      if os.path.exists(deployment_path + ".failed"):
        os.remove(deployment_path + ".failed")

class ServerCommandExecutor:

  def __init__(self, ispncon_config):
    self.ispncon_config = ispncon_config

  def _error(self, msg):
    raise CommandExecutionError(msg)

  def listServers(self):
    try:
      for server_name in self.ispncon_config.get_configured_servers():
        try:
          print server_name, self._createServerManager(server_name).getStatus()
        except InvalidServerConfigException:
          print server_name, "INVALID"
    except ServerManagerException as e:
      self._error(e.args[0])

  def _createServerManager(self, server_name):
    type = self.ispncon_config.get("server:%s.type" % server_name, None)
    script = self.ispncon_config.get("server:%s.script" % server_name, None)
    if type == None or type == "custom":
      if script == None:
        raise InvalidServerConfigException("script config key must be present for custom server manager")
      else:
        return ScriptServerManager(self.ispncon_config, server_name, script)
    else:
      if (type == "hotrod") or (type == "memcached"):
        return InfinispanServerManager(self.ispncon_config, server_name)
      elif type == "edg":
        return EDG6ServerManager(self.ispncon_config, server_name)
      elif type == "rest_as7":
        return AS7RESTServerManager(self.ispncon_config, server_name)
      else:
        raise InvalidServerConfigException("Unknown server type \"%s\"" % type)

  """Parses and executes ispncon server commands"""
  def executeCommand(self, server_command, args):
    try:
      if server_command == "start":
        self.start(args)
      elif server_command == "stop":
        self.stop(args)
      elif server_command == "out":
        self.out(args)
      elif server_command == "jstack":
        self.jstack(args)
      else:
        self._error("Unknown server command: %s" % server_command)
    except ServerManagerException as e:
      self._error(e.args[0])

  def _parseOptsAndCreateManager(self, args, command, short_opts, long_opts):
    try:
      opts1, args1 = getopt.getopt(args, short_opts, long_opts)
    except getopt.GetoptError:
      self._error("Wrong server %s command syntax." % command)
    if (len(args1) > 1):
      self._error("Wrong server %s command syntax." % command)
    if len(args1) == 1:
      server_name = args1[0]
    else:
      server_name = self.ispncon_config.get("server_management.default_server")
    if server_name == None:
      self._error("Please specify server name or configure default server name.")

    return opts1, self._createServerManager(server_name)

  def start(self, args):
    opts, serverManager = self._parseOptsAndCreateManager(args, "start", "l:p:d:D:P:w", ["listen-addr=", "listen-port=", "debug=", "debug-suspend=", "config", "wait-for-start"])

    wait1 = False
    config_overrides1 = {}

    #override config with inline options
    for opt, arg in opts:
      if opt in ("-l", "--listen-addr"):
        config_overrides1["listen_addr"] = arg
      if opt in ("-p", "--listen-port"):
        config_overrides1["listen_port"] = arg
      if opt in ("-d", "--debug"):
        config_overrides1["debug"] = "True"
        config_overrides1["debug_port"] = arg
        config_overrides1["debug_suspend"] = "False"
      if opt in ("-D", "--debug-suspend"):
        config_overrides1["debug"] = "True"
        config_overrides1["debug_port"] = arg
        config_overrides1["debug_suspend"] = "True"
      if opt in ("-w", "--wait-for-start"):
        wait1 = True
      if opt in ("-P", "--config"):
        kvpair = arg.split(" ")
        if (len(kvpair) != 2):
          self._error("invalid key value pair in -P option")
        config_overrides1[kvpair[0]] = kvpair[1]

    serverManager.start(wait=wait1, config_overrides=config_overrides1)

  def stop(self, args):
    opts, serverManager = self._parseOptsAndCreateManager(args, "stop", "P:ksw", ["config", "kill", "shutdown", "wait-for-stop"])
    cfg_kill = self.ispncon_config.get("server_management.kill_by_default")
    kill1 = ((cfg_kill != None) and (cfg_kill in TRUE_STR_VALUES))
    wait1 = False
    config_overrides1 = {}

    #override config with inline options
    for opt, arg in opts:
      if opt in ("-k", "--kill"):
        kill1 = True
      if opt in ("-s", "--shutdown"):
        kill1 = False
      if opt in ("-w", "--wait-for-stop"):
        wait1 = True
      if opt in ("-P", "--config"):
        kvpair = arg.split(" ")
        if (len(kvpair) != 2):
          self._error("invalid key value pair in -P option")
        config_overrides1[kvpair[0]] = kvpair[1]

    serverManager.stop(kill = kill1, wait = wait1, config_overrides = config_overrides1)

  def out(self, args):
    opts, serverManager = self._parseOptsAndCreateManager(args, "stop", "P:n:fFt", ["config", "num-lines", "follow", "full", "tail"])

    try:
      cfg_num_lines = int(self.ispncon_config.get("server_management.out_tail_size", "10"))
    except ValueError:
      raise InvalidServerConfigException("server_management.out_tail_size must be a number")

    cfg_mode = self.ispncon_config.get("server_management.out_view", "tail")
    config_overrides1 = {}

    #override config with inline options
    for opt, arg in opts:
      if opt in ("-n", "--num-lines"):
        try:
          cfg_num_lines = int(arg)
        except ValueError:
          self._error("--num-lines or -n option must be a number")
      if opt in ("-f", "--follow"):
        cfg_mode = "follow"
      if opt in ("-F", "--full"):
        cfg_mode = "full"
      if opt in ("-t", "--tail"):
        cfg_mode = "tail"
      if opt in ("-P", "--config"):
        kvpair = arg.split(" ")
        if (len(kvpair) != 2):
          self._error("invalid key value pair in -P option")
        config_overrides1[kvpair[0]] = kvpair[1]

    serverManager.out(mode = cfg_mode, num_lines = cfg_num_lines, config_overrides = config_overrides1)

  def jstack(self, args):
    self._parseOptsAndCreateManager(args, "jstack", "", [])[1].jstack()
