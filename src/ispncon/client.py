#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Cache client abstraction with three implementations

HotRodCacheClient
RestCacheClient
MemcachedCacheClient
"""
from httplib import HTTPConnection, CONFLICT, OK, NOT_FOUND, NO_CONTENT
from infinispan.remotecache import RemoteCache, RemoteCacheError
from ispncon import DEFAULT_CACHE_NAME, TRUE_STR_VALUES
from ispncon.codec import RiverStringCodec
from memcache import Client
##from memcache import __ersion__ as memcache_version
#import socket # because of MyMemcachedClient

__author__ = "Michal Linhard"
__copyright__ = "(C) 2011 Red Hat Inc."
        

class CacheClientError(Exception):
  """Should serve for storing cache client exceptions"""
  def __init__(self, msg):
    self.msg = msg

class ConflictError(CacheClientError): 
  def __init__(self):
    self.msg = "CONFLICT"

class NotFoundError(CacheClientError):
  def __init__(self):
    self.msg = "NOT_FOUND"

class CacheClient(object):
  """Base class for all cache Clients, lists methods they should support"""
  def __init__(self, host, port, cache_name):
    self.host = host
    self.port = port
    self.cache_name = cache_name
  def put(self, key, value, version=None, lifespan=None, maxidle=None, put_if_absent=False):
    """Put data under the given key
       key - key to store to
       value - value to store, this can be either string or byte array (result of file.read())
       version - store only if version in cache is equal to given version, takes priority above put_if_absent
       lifespan - number of seconds to live
       max_idle - number of seconds the entry is allowed to be inactive, if exceeded entry is deleted
       put_if_absent - if true, the put will be successful only if there is no previous entry under given key
    """
    pass
  def get(self, key, get_version=False):
    """Get entry under the given key
      key - key
      get_version - get version flag
      returns (version, data) if get_version otherwise returns just data
    """
    pass
  def version(self, key):
    """Get version of entry with the given key
      key - key of the entry to get
      returns version string (format depends on the client type)
    """
    # default inefficient implementation
    return self.get(key, True)[0]

  def exists(self, key):
    """Raise NotFoundError if entry under the given key doesn't exist, otherwise do nothing.
      key - key
      returns nothing
    """
    # default inefficient implementation
    self.get(key) #this throws NotFoundError if not found

  def delete(self, key):
    """Delete the entry under the given key
      key - key
      returns nothing
    """
    pass

  def clear(self):
    """Clears the whole cache
      returns nothing
    """
    pass

  def _error(self, msg):
    raise CacheClientError(msg)
  
def fromString(config):
  client_str = config["client_type"]
  if client_str == "hotrod":
    return HotRodCacheClient(config)
  elif client_str == "memcached":
    return MemcachedCacheClient(config)
  elif client_str == "rest":
    return RestCacheClient(config)
  else:
    raise CacheClientError("unknown client type")
    

class HotRodCacheClient(CacheClient):
  """HotRod cache client implementation."""
    
  def __init__(self, config):
    super(HotRodCacheClient, self).__init__(config["host"], config["port"], config["cache"])
    self.config = config
    if config["hotrod.use_river_string_keys"] in TRUE_STR_VALUES:
      self.river_keys = RiverStringCodec()
    else:
      self.river_keys = None
    if self.cache_name == DEFAULT_CACHE_NAME: 
      self.cache_name = "";
    self.remote_cache = RemoteCache(self.host, int(self.port), self.cache_name)
    return

  def _optionally_encode_key(self, key_unmarshalled):
      if self.river_keys == None:
        return key_unmarshalled;
      else:
        return self.river_keys.encode(key_unmarshalled)

  def put(self, key, value, version=None, lifespan=None, max_idle=None, put_if_absent=False):
    key = self._optionally_encode_key(key)
    if lifespan == None:
      lifespan=0 
    if max_idle == None:
      max_idle=0
    try:
      if (version == None):
        if (put_if_absent):
          retval = self.remote_cache.put_if_absent(key, value, lifespan, max_idle)
          if retval:
            return
          else:
            raise ConflictError
        else:
          self.remote_cache.put(key, value, lifespan, max_idle)
      else:
          numversion = None
          try:
            numversion = int(version)
          except ValueError:
            self._error("hotrod client only accepts numeric versions")
          retval = self.remote_cache.replace_with_version(key, value, numversion, lifespan, max_idle)
          if retval == 1:
            return
          elif retval == 0:
            raise NotFoundError
          elif retval == -1:
            raise ConflictError
          else:
            self._error("unexpected return value from hotrod client")
    except RemoteCacheError as e:
      self._error(e.args)
        
  def get(self, key, get_version=False):
    try:
      value = None
      version = None
      key = self._optionally_encode_key(key)
      if get_version:
        version, value = self.remote_cache.get_versioned(key)
      else:
        value = self.remote_cache.get(key)
      if value == None:
        raise NotFoundError
      if get_version:
        return version, value
      else:
        return value
    except RemoteCacheError as e:
      self._error(e.args)

  def delete(self, key, version=None):
    try:
      key = self._optionally_encode_key(key)
      if version == None:
        retval = self.remote_cache.remove(key)
        if retval:
          return
        else:
          raise NotFoundError
      else:
        numversion = None
        try:
          numversion = int(version)
        except ValueError:
          self._error("hotrod client only accepts numeric versions")
        retval = self.remote_cache.remove_with_version(key, numversion)
        if retval == 1:
          return
        elif retval == 0:
          raise NotFoundError
        elif retval == -1:
          raise ConflictError
        else:
          self._error("unexpected return value from hotrod client")
      
    except RemoteCacheError as e:
      self._error(e.args)
    
  def clear(self):
    self.remote_cache.clear()
    
  def exists(self, key):
    try:
      key = self._optionally_encode_key(key)
      if not self.remote_cache.contains_key(key):
        raise NotFoundError
    except RemoteCacheError as e:
      self._error(e.args) 

class RestCacheClient(CacheClient):
  """REST cache client implementation."""
    
  def __init__(self, config):
    super(RestCacheClient, self).__init__(config["host"], config["port"], config["cache"])
    self.config = config
    self.http_conn = HTTPConnection(self.host, self.port)
    return
  
  def _makeurl(self, key):
    suffix = ""
    if (key != None):
      suffix = "/" + key               
    return self.config["rest.server_url"] + "/" + self.cache_name + suffix
  
  def put(self, key, value, version=None, lifespan=None, max_idle=None, put_if_absent=False):
    url = self._makeurl(key)
    method = "PUT"
    if (put_if_absent):
      method = "POST" # doing POST instead of PUT will cause conflict in case the entry exists
    headers =  {"Content-Type": self.config["rest.content_type"]}
    if lifespan != None:
      headers["timeToLiveSeconds"] = lifespan
    if max_idle != None:
      headers["maxIdleTimeSeconds"] = max_idle
    if version != None:
      headers["If-Match"] = version
    self.http_conn.request(method, url, value, headers)
    resp = self.http_conn.getresponse()
    if resp.status == OK:
      return
    elif resp.status == CONFLICT:
      raise ConflictError
    else:
      self._error("Unexpected HTTP Status: %s" % resp.status)
    
  def get(self, key, get_version=False):
    url = self._makeurl(key)
    headers =  {"Content-Type": self.config["rest.content_type"]}
    
    self.http_conn.request("GET", url, None, headers)
    resp = self.http_conn.getresponse()
    if resp.status == OK:
      value = resp.read()
      version = resp.getheader("ETag", None)
      return (version, value) if get_version else value
    elif resp.status == NOT_FOUND:
      raise NotFoundError
    else:
      self._error("Unexpected HTTP Status: %s" % resp.status)

  def delete(self, key, version=None):
    url = self._makeurl(key)
    headers =  {}
    if version != None:
      headers["If-Match"] = version
      
    self.http_conn.request("DELETE", url, None, headers)
    resp = self.http_conn.getresponse()
    if resp.status == OK:
      return
    elif resp.status == NO_CONTENT:
      raise NotFoundError
    elif resp.status == CONFLICT:
      raise ConflictError
    else:
      self._error("Unexpected HTTP Status: %s" % resp.status)
    
  def clear(self):
    url = self._makeurl(None)
      
    self.http_conn.request("DELETE", url, None, {})
    resp = self.http_conn.getresponse()
    if resp.status == NO_CONTENT:
      return
    else:
      self._error("Unexpected HTTP Status: %s" % resp.status)
    
  def exists(self, key):
    url = self._makeurl(key)
    headers =  {"Content-Type": self.config["rest.content_type"]}
    
    self.http_conn.request("HEAD", url, None, headers)
    resp = self.http_conn.getresponse()
    if resp.status == OK:
      return
    elif resp.status == NOT_FOUND:
      raise NotFoundError
    else:
      self._error("Unexpected HTTP Status: %s" % resp.status)

  def version(self, key):
    url = self._makeurl(key)
    headers =  {"Content-Type": self.config["rest.content_type"]}

    self.http_conn.request("HEAD", url, None, headers)
    resp = self.http_conn.getresponse()
    if resp.status == OK:
      version = resp.getheader("ETag", None)
      if (version == None):
        self._error("Couldn't obtain version info from the REST server")
      return version
    elif resp.status == NOT_FOUND:
      raise NotFoundError
    else:
      self._error("Unexpected HTTP Status: %s" % resp.status)
    
MEMCACHED_LIFESPAN_MAX_SECONDS = 60*60*24*30

# extension of python-memcached client that can distinguish some more return states of the set operation
# it needs to exist because of following issues in the python-memcache library:
# https://bugs.launchpad.net/python-memcached/+bug/684689
# https://bugs.launchpad.net/python-memcached/+bug/684690
# as soon as these are solved we can return to the original Client
# so far to prevent mysterious bugs we'll require fixed memcache version 1.47

# other possibility is that we'll document limitations of memcached client.

#class MyMemcachedClient(Client):
#  def __init__(self, *args, **kw):
#    super(MyMemcachedClient, self).__init__(*args, **kw)
#    if memcache_version != "1.47":
#      raise CacheClientError("Unsupported python-memcached library version")
#    self.last_set_status = None
#    
#  def _set(self, cmd, key, val, time, min_compress_len = 0):
#    self.check_key(key)
#    server, key = self._get_server(key)
#    if not server:
#      return 0
#    
#    self._statlog(cmd)
#    
#    store_info = self._val_to_store_info(val, min_compress_len)
#    if not store_info: return(0)
#    
#    if cmd == 'cas':
#      if key not in self.cas_ids:
#        return self._set('set', key, val, time, min_compress_len)
#      fullcmd = "%s %s %d %d %d %d\r\n%s" % (
#          cmd, key, store_info[0], time, store_info[1],
#          self.cas_ids[key], store_info[2])
#    else:
#      fullcmd = "%s %s %d %d %d\r\n%s" % (
#          cmd, key, store_info[0], time, store_info[1], store_info[2])
#    
#    try:
#      server.send_cmd(fullcmd)
#      self.last_set_status = server.expect("STORED") 
#      return(self.last_set_status == "STORED")
#    except socket.error, msg:
#      if isinstance(msg, tuple): msg = msg[1]
#      server.mark_dead(msg)
#      self.last_set_status = "ERROR socket error"
#    return 0
#  
#  def delete(self, key, time=0):
#    self.check_key(key)
#    server, key = self._get_server(key)
#    if not server:
#        return 0
#    self._statlog('delete')
#    if time != None:
#        cmd = "delete %s %d" % (key, time)
#    else:
#        cmd = "delete %s" % key
#    
#    try:
#        server.send_cmd(cmd)
#        line = server.readline()
#        if line:
#          self.last_set_status = line.strip() 
#          if self.last_set_status in ['DELETED', 'NOT_FOUND']: return 1
#        self.debuglog('Delete expected DELETED or NOT_FOUND, got: %s'
#                % repr(line))
#    except socket.error, msg:
#        if isinstance(msg, tuple): msg = msg[1]
#        server.mark_dead(msg)
#        self.last_set_status = "ERROR socket error"
#    return 0


class MemcachedCacheClient(CacheClient):
  """Memcached cache client implementation."""
    
  def __init__(self, config):
    super(MemcachedCacheClient, self).__init__(config["host"], config["port"], config["cache"])
    self.config = config
    if self.cache_name != DEFAULT_CACHE_NAME:
      print "WARNING: memcached client doesn't support named caches. cache_name config value will be ignored and default cache will be used instead."
    self.memcached_client = Client([self.host + ':' + self.port], debug=0)
    return
  
  def put(self, key, value, version=None, lifespan=None, max_idle=None, put_if_absent=False):
    time = 0
    if lifespan != None:
      if lifespan > MEMCACHED_LIFESPAN_MAX_SECONDS:
        self._error("Memcached cache client supports lifespan values only up to %s seconds (30 days)." % MEMCACHED_LIFESPAN_MAX_SECONDS)
      time = lifespan
    if max_idle != None:
      self._error("Memcached cache client doesn't support max idle time setting.")
    try:
      if (version == None):
        if (put_if_absent):
          if not self.memcached_client.add(key, value, time, 0):
          # current python-memcached doesn't recoginze these states
          # if self.memcached_client.last_set_status == "NOT_STORED":
          #   raise ConflictError
          # else:
          #   self._error("Operation unsuccessful. " + self.memcached_client.last_set_status)
            self._error("Operation unsuccessful. Possibly CONFLICT.")
        else:
          if not self.memcached_client.set(key, value, time, 0):
          # self._error("Operation unsuccessful. " + self.memcached_client.last_set_status)
            self._error("Operation unsuccessful.")
      else:
        try:
          self.memcached_client.cas_ids[key] = int(version)
        except ValueError:
          self._error("Please provide an integer version.")
        if not self.memcached_client.cas(key, value, time, 0):
#         if self.memcached_client.last_set_status == "EXISTS":
#           raise ConflictError
#         if self.memcached_client.last_set_status == "NOT_FOUND":
#           raise NotFoundError
#         else:
#           self._error("Operation unsuccessful. " + self.memcached_client.last_set_status)
          self._error("Operation unsuccessful. Possibly CONFLICT, NOT_FOUND.")
    except CacheClientError as e:
      raise e #rethrow
    except Exception as e:
      self._error(e)
    
  def get(self, key, get_version=False):
    try:
      if get_version:
        val = self.memcached_client.gets(key)
        if val == None:
          raise NotFoundError
        version = self.memcached_client.cas_ids[key]
        if version == None:
          self._error("Couldn't obtain version info from memcached server.")
        return version, val
      else:
        val = self.memcached_client.get(key)
        if val == None:
          raise NotFoundError
        return val 
    except CacheClientError as e:
      raise e #rethrow
    except Exception as e:
      self._error(e.args)

  def delete(self, key, version=None):
    try:
      if version:
        self._error("versioned delete operation not available for memcached client")
      if self.memcached_client.delete(key, 0):
        if self.memcached_client.last_set_status == "NOT_FOUND":
          raise NotFoundError
      else:
        self._error("Operation unsuccessful. " + self.memcached_client.last_set_status)
    except CacheClientError as e:
      raise e #rethrow
    except Exception as e:
      self._error(e.args)
    
  def clear(self):
    try:
      self.memcached_client.flush_all()
    except CacheClientError as e:
      raise e #rethrow
    except Exception as e:
      self._error(e.args)
