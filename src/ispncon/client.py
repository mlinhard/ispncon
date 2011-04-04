#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Cache client abstraction with three implementations

HotRodCacheClient
RestCacheClient
MemcachedCacheClient
"""
from infinispan.remotecache import RemoteCache, RemoteCacheError
from httplib import HTTPConnection, CONFLICT, OK, NOT_FOUND, NO_CONTENT

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
    pass
  def get(self, key):
    pass
  def exists(self, key):
    pass
  def delete(self, key):
    pass
  def clear(self):
    pass
  
def fromString(config):
  client_str = config["client_type"]
  if client_str == "hotrod":
    return HotRodCacheClient(config)
  elif client_str == "memcached":
#    return MemcachedCacheClient(host, port, cache_name)
    raise CacheClientError("memcached client is not supported yet!")
  elif client_str == "rest":
    return RestCacheClient(config)
  else:
    raise CacheClientError("unknown client type")
    

class HotRodCacheClient(CacheClient):
  """HotRod cache client implementation."""
    
  def __init__(self, config):
    super(HotRodCacheClient, self).__init__(config["host"], config["port"], config["cache"])
    self.config = config
    if self.cache_name == None:
      self.cache_name = "";
    self.remote_cache = RemoteCache(self.host, int(self.port), self.cache_name)
    return
  
  def put(self, key, value, version=None, lifespan=None, max_idle=None, put_if_absent=False):
    """key - key to store to
       value - value to store
       version - store only if version in cache is equal to given version, takes priority above put_if_absent
       lifespan - number of seconds to live
       max_idle - number of seconds the entry is allowed to be inactive, if exceeded entry is deleted
       put_if_absent - if true, the put will be successful only if there is no previous entry under given key
    """
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
            raise CacheClientError("hotrod client only accepts numeric versions")
          retval = self.remote_cache.replace_with_version(key, value, numversion, lifespan, max_idle)
          if retval == 1:
            return
          elif retval == 0:
            raise NotFoundError
          elif retval == -1:
            raise ConflictError
          else:
            raise CacheClientError("unexpected return value from hotrod client")
    except RemoteCacheError as e:
      raise CacheClientError(e.args)
        
  def get(self, key, get_version=False):
    try:
      value = None
      version = None
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
      raise CacheClientError(e.args)

  def delete(self, key, version=None):
    try:
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
          raise CacheClientError("hotrod client only accepts numeric versions")
        retval = self.remote_cache.remove_with_version(key, numversion)
        if retval == 1:
          return
        elif retval == 0:
          raise NotFoundError
        elif retval == -1:
          raise ConflictError
        else:
          raise CacheClientError("unexpected return value from hotrod client")
      
    except RemoteCacheError as e:
      raise CacheClientError(e.args)
    
  def clear(self):
    self.remote_cache.clear()
    
  def exists(self, key):
    try:
      if not self.remote_cache.contains_key(key):
        raise NotFoundError
    except RemoteCacheError as e:
      raise CacheClientError(e.args) 

REST_SERVER_URL = "/infinispan-server-rest/rest"
    
class RestCacheClient(CacheClient):
  """REST cache client implementation."""
    
  def __init__(self, config):
    super(RestCacheClient, self).__init__(config["host"], config["port"], config["cache"])
    self.config = config
    if self.cache_name == None or self.cache_name == "":
      self.cache_name = "___defaultcache";
    self.http_conn = HTTPConnection(self.host, self.port)
    return
  
  def _makeurl(self, key):
    suffix = ""
    if (key != None):
      suffix = "/" + key               
    return self.config["rest.server_url"] + "/" + self.cache_name + suffix
  
  def put(self, key, value, version=None, lifespan=None, max_idle=None, put_if_absent=False):
    """key - key to store to
       value - value to store
       version - store only if version in cache is equal to given version, takes priority above put_if_absent
       lifespan - number of seconds to live
       max_idle - number of seconds the entry is allowed to be inactive, if exceeded entry is deleted
       put_if_absent - if true, the put will be successful only if there is no previous entry under given key
    """
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
      raise CacheClientError("Unexpected HTTP Status: %s" % resp.status)
    
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
      raise CacheClientError("Unexpected HTTP Status: %s" % resp.status)

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
      raise CacheClientError("Unexpected HTTP Status: %s" % resp.status)
    
  def clear(self):
    url = self._makeurl(None)
      
    self.http_conn.request("DELETE", url, None, {})
    resp = self.http_conn.getresponse()
    if resp.status == NO_CONTENT:
      return
    else:
      raise CacheClientError("Unexpected HTTP Status: %s" % resp.status)
    
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
      raise CacheClientError("Unexpected HTTP Status: %s" % resp.status)
    
#TODO
class MemcachedCacheClient(CacheClient):
  """Memcached cache client implementation."""
    
  def __init__(self, config):
    super(RestCacheClient, self).__init__(config["host"], config["port"], config["cache"])
    self.config = config
    if self.cache_name == None or self.cache_name == "":
      self.cache_name = "___defaultcache";
    self.http_conn = HTTPConnection(self.host, self.port)
    return
  
  def _makeurl(self, key):
    suffix = ""
    if (key != None):
      suffix = "/" + key               
    return self.config["rest.server_url"] + "/" + self.cache_name + suffix
  
  def put(self, key, value, version=None, lifespan=None, max_idle=None, put_if_absent=False):
    """key - key to store to
       value - value to store
       version - store only if version in cache is equal to given version, takes priority above put_if_absent
       lifespan - number of seconds to live
       max_idle - number of seconds the entry is allowed to be inactive, if exceeded entry is deleted
       put_if_absent - if true, the put will be successful only if there is no previous entry under given key
    """
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
      raise CacheClientError("Unexpected HTTP Status: %s" % resp.status)
    
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
      raise CacheClientError("Unexpected HTTP Status: %s" % resp.status)

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
      raise CacheClientError("Unexpected HTTP Status: %s" % resp.status)
    
  def clear(self):
    url = self._makeurl(None)
      
    self.http_conn.request("DELETE", url, None, {})
    resp = self.http_conn.getresponse()
    if resp.status == NO_CONTENT:
      return
    else:
      raise CacheClientError("Unexpected HTTP Status: %s" % resp.status)
    
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
      raise CacheClientError("Unexpected HTTP Status: %s" % resp.status)
