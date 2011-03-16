#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Cache client abstraction with three implementations

HotRodCacheClient
RestCacheClient
MemcachedCacheClient
"""
from infinispan.remotecache import RemoteCache
import sys

__author__ = "Michal Linhard"
__copyright__ = "(C) 2010-2011 Red Hat Inc."
        

class CacheClientError(Exception):
  """Should serve for storing cache client exceptions"""
  def __init__(self, msg):
    self.message = msg

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
    print "memcached client is not supported yet!"
    sys.exit(1)
#    return MemcachedCacheClient(host, port, cache_name)
  elif client_str == "rest":
#    return RestCacheClient(host, port, cache_name)
    print "rest client is not supported yet!"
    sys.exit(1)
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
      if lifespan == None:
        lifespan=0 
      if max_idle == None:
        max_idle=0
      if (version == None):
        if (put_if_absent):
          self.remote_cache.put_if_absent(key, value, lifespan, max_idle)
        else:
          self.remote_cache.put(key, value, lifespan, max_idle)
      else:
          self.remote_cache.replace_with_version(key, value, version, lifespan, max_idle)
        
        
  def get(self, key):
      return self.remote_cache.get(key)
 
#TODO other implementations
   
class MemcachedCacheClient(CacheClient):
  pass

class RestCacheClient(CacheClient):
  pass