#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Cache client abstraction with three implementations

HotRodCacheClient
RestCacheClient
MemcachedCacheClient
"""
from infinispan.remotecache import RemoteCache, RemoteCacheError
from report.plugins.bugzilla.filer import getVersion
import sys

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
  
def fromString(client_str, host, port, cache_name):
  if client_str == "hotrod":
    return HotRodCacheClient(host, port, cache_name)
  elif client_str == "memcached":
#    return MemcachedCacheClient(host, port, cache_name)
    raise CacheClientError("memcached client is not supported yet!")
  elif client_str == "rest":
#    return RestCacheClient(host, port, cache_name)
    raise CacheClientError("rest client is not supported yet!")
  else:
    raise CacheClientError("unknown client type")
    
class HotRodCacheClient(CacheClient):
    
  def __init__(self, host, port, cache_name):
    super(HotRodCacheClient, self).__init__(host, port, cache_name)
    if self.cache_name == None:
      self.cache_name = "";
    self.remote_cache = RemoteCache(host, int(port), self.cache_name)
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
    
#TODO other implementations
   
class MemcachedCacheClient(CacheClient):
  pass

class RestCacheClient(CacheClient):
  pass