Infinispan Client Console design
--------------------------------

Infinispan Client Console would be a linux console tool that would be 
capable of doing simple operations with the infinispan cache using
the chosen client access (hotrod, memcached, rest/http)
This might be handy for cache debugging purposes and maybe have some
usecases for linux shell scripts wanting to use infinispan cache.

it will be able to process a file with simple cache commands.

usage
-----

ispncon [options] <operation> <operation_options> <op_arguments>
	-c --client (default: hotrod, other possible values memcached, rest)
	-h --host <host> (default: localhost) 
	-p --port <port> (default: 11222(hotrod), 11211(memcached), 8080(rest))
	-v --version prints the ispncon version

config file
-----------
file ~/.ispncon will be read in the beginning if exists
it contains properties in form of setconfig commands	

operations
----------

usually operations return something to the stdout

help
====

prints help about an operation
  
  format:
    help <operation>
    
  note:
    if no operation is supplied, prints list of supported operations

put
===

puts the specified entry (key, value) into the cache

  format:
    put [options] <key> <value>
        
  options:
    -i <filename>  don't specify inline string value, instead put the whole contents of the specified file
    -v <version>   put only if version equals version given
    -l <lifespan>  specifies lifespan, integer, number of seconds
    -I <maxidle>   specifies max idle time, integer, number of seconds
    -a             put if absent, same as put but returns CONFLICT if value already exists 
                   and doesn't put anything in that case
  
  return:
    * in case the entry was stored successfully, one line: 
    STORED
    * in case of error, one line: 
    ERROR <msg>
    * if option -a was used and the entry already exists, one line: 
    CONFLICT

get
===

gets the value under specific key from the cache
  format:
    get [options] <key>

  options:
    -o <filename>  stores the output of the get operation into the file specified
    -V             gets version of the data
    
  return:
    * in case no filename was specified
    <data...
    ... possibly on multiple lines
    ... possibly binary content, not suitable for terminal>
    * in case a filename was specified
    no output
    * in case -V was specified, the output is prepended with one line
    VERSION <version>

delete
======

delete [options] <key>
deletes the entry under given key 

stdout:
DELETED - when deleted successfully
or
NOT_FOUND -when entry didn't exist
or
CONFLICT - if version was specified and entry didn't have the version required

clear
=====

clear
clears the cache
stdout:
DELETED

exists
======

exists <key>
stdout:
EXISTS - if value exists
NOT_FOUND - if not

setconfig
=========

setconfig key value
	cache - cache name
	host - host name
	port - port on host
	client - client type: hotrod|memcached|rest

include
=======

include <filename>
	processes cache commands from specified file











