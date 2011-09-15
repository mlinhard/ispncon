#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Server management related code.
"""
from ispncon import TRUE_STR_VALUES
from subprocess import STDOUT
from xml.etree.ElementTree import register_namespace, parse
import os
import psutil
import shutil
import signal
import subprocess

XMLNS_DOMAIN = "urn:jboss:domain:1.0"
BAK = ".ispncon.backup"
DEFAULT_JAVA_OPTS_INTERNAL = "-Xms64m -Xmx256m -XX:MaxPermSize=128m -Djava.net.preferIPv4Stack=true -Dorg.jboss.resolver.warning=true -Dsun.rmi.dgc.client.gcInterval=3600000 -Dsun.rmi.dgc.server.gcInterval=3600000 -Djboss.modules.system.pkgs=org.jboss.byteman"
DEFAULT_DEBUG_PORT = 8787

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

#TODO: xml config parser/overwrite tool
#TODO: InfinispanServerManager
#TODO: EDG6ServerManager
#TODO: AS7RESTServerManager

PID_FILE_TEMPLATE = "/tmp/ispncon.server.%s.pid"
OUT_FILE_TEMPLATE = "/tmp/ispncon.server.%s.out"

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

class ServerManagerException(Exception):
  """Exception in ServerManager"""
  pass

class InvalidServerConfigException(ServerManagerException):
  """when server config is INVALID"""
  pass

class ServerManager():
  """Superclass for server managers"""
  
  def __init__(self, config, name):
    self._config = config
    self._name = name

  def executeCommand(self, command):
    raise ServerManagerException("Not implemented")

  def getStatus(self):
    raise ServerManagerException("Not implemented")

class ScriptServerManager(ServerManager):
  """ServerManager that uses custom management script to controll the server"""

  def __init__(self, config, name, script):
    self._script = script
    ServerManager.__init__(self, config, name)
    if not os.path.exists(script):
      raise ServerManagerException("configuration problem in server \"%s\": script doesn't exist: %s" % (name, script))
    if not os.access(script, os.X_OK):
      raise ServerManagerException("configuration problem in server \"%s\": script isn't executable: %s" % (name, script))

  def executeCommand(self, command):
    args = [self._script]
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
  
  def executeCommand(self, command):
    if command == "start":
      self.start()
    elif command == "stop":
      self.stop()
    elif command == "out":
      self.out()
    elif command == "log":
      self.log()
    else:
      raise ServerManagerException("Unknown command %s" % command)

  def writePid(self, pid):
    pidfile = open(PID_FILE_TEMPLATE % self._name, "w")
    pidfile.write(str(pid))
    pidfile.close()

  def start(self):
    raise ServerManagerException("This operation is not yet supported.")

  def stop(self):
    raise ServerManagerException("This operation is not yet supported.")

  def out(self):
    raise ServerManagerException("This operation is not yet supported.")

  def log(self):
    raise ServerManagerException("This operation is not yet supported.")

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

class InfinispanServerManager(BuiltInServerManager):
  """ServerManager for standard community Infinispan server"""

  def __init__(self, config, name):
    BuiltInServerManager.__init__(self, config, name)
    ispn_home = self._config.get("ispn_home")
    if ispn_home == None:
      raise InvalidServerConfigException("ispn_home config key is required for hotrod/memcached server manager")
    self._validate_ispn_home(ispn_home)

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

class AS7BasedServerManager(BuiltInServerManager):
  """ServerManager for servers based on JBoss AS 7"""

  def __init__(self, config, name):
    BuiltInServerManager.__init__(self, config, name)
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

  def start(self):
    if self.findPid() != -1:
      raise ServerManagerException("Server is already running.")

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

    args = [binary]
    env1 = { "JAVA_OPTS" : java_opts }

    outfile = open((OUT_FILE_TEMPLATE % self._name), 'w')

    #here we're just spawning a process and ending this one
    p = subprocess.Popen(args, env=env1, stdout=outfile, stderr=STDOUT)
    self.writePid(p.pid)

  def findPid(self):
    return jpsgrep("-Dispncon.server.name="+self._name)

  def getStatus(self):
    """
    will return one of these:
    INVALID - invalid configuration, or error occured
    RUNNING - server is running
    STOPPED - server is not running

    how to determine status:
    
    check if there's a java process running with string -Dispncon.server.name=<name> in the command
    if not:
       STOPPED
       delete following files if they exist:
       /tmp/ispncon.server.<name>.out 
       /tmp/ispncon.server.<name>.pid
    if yes:
       RUNNING
       check if /tmp/ispncon.server.<name>.pid exists, if not, create it
    """
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

  def stop(self):
    pid = self.findPid()
    if pid == -1:
      raise ServerManagerException("Server is not running.")
    else:
      kill = self._config.get("kill")
      if (kill != None) and (kill in TRUE_STR_VALUES):
        os.kill(pid, signal.SIGKILL)
      else:
        os.kill(pid, signal.SIGTERM)

  def out(self):
    pass

class EDG6ServerManager(AS7BasedServerManager):
  """ServerManager for JBoss Enterprise Datagrid 6"""
  pass

class AS7RESTServerManager(AS7BasedServerManager):
  pass

def createServerManager(config, name):
  type = config.pop("type", None)
  script = config.pop("script", None)
  if type == None or type == "custom":
    if script == None:
      raise InvalidServerConfigException
    else:
      return ScriptServerManager(config, name, script)
  else:  
    if (type == "hotrod") or (type == "memcached"):
      return InfinispanServerManager(config, name)
    elif type == "edg":
      return EDG6ServerManager(config, name)
    elif type == "rest_as7":
      return AS7RESTServerManager(config, name)
    else:
      raise ServerManagerException("Unknown server type \"%s\"" % type)
