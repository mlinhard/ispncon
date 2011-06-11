# -*- coding: utf-8 -*-

"""
Constant definition
"""

__author__ = "Michal Linhard"
__copyright__ = "(C) 2011 Red Hat Inc."

ISPNCON_VERSION = "0.8.1-SNAPSHOT"

USAGE = """USAGE: ispncon [options] <operation> [operation_options] <op_arguments>
    -c --client            client to use, possible values hotrod(default), memcached, rest
    -h --host <host>       hostname/ip address to connect to. Default: localhost
    -p --port <port>       port to connect to. Default:  11222 (hotrod default port)
    -C --cache-name <name> Named cache to use. Default: use default cache (no value)
    -v --version           prints the ispncon version and exits
    -e --exit-on-error     if operation fails, don't print ERROR output, but fail with error exit code
    use operation help to get list of supported operations
    or help <operation> to display info on particular operation"""

HELP = {
  "put" : """puts the specified entry (key, value) into the cache

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
    CONFLICT""",

  "get" : """gets the value under specific key from the cache
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
    VERSION <version>""",
    
  "help" : """prints help about an operation
  
  format:
    help <operation>
    
  note:
    if no operation is supplied, prints list of supported operations""",
    
  "delete" : """deletes the value under the specified key

  format:
    delete [options] <key>

  options:
    -v <version> deletes only if the specified version matches the version in the cache

  return: 
    (exit code 0)
    * entry was successfully deleted, one line:
    DELETED

    (exit code 1)
    * in case of general error, one line: 
    ERROR <msg>

    (exit code 2)
    * if the entry wasn't found in the cache, one line:
    NOT_FOUND

    (exit code 3)
    * if option -v was used and versions don't match, one line: 
    CONFLICT""",
    
  "clear" : """clears the cache

  format:
    clear

  return: 
    (exit code 0)
    * cache was successfully cleared, one line:
    DELETED

    (exit code 1)
    * in case of general error, one line: 
    ERROR <msg>""",

  "exists" : """verifies if the entry exists in the cache
    
  format:
    exists <key>
  
  return:
    (exit code 0)
    * in case entry with given key exists, one line:
    EXISTS
    
    (exit code 1)
    * in case of general error, one line: 
    ERROR <msg>
    
    (exit code 2)
    * if the requested entry wasn't found in the cache, one line:
    NOT_FOUND""",
    
  "config" : """changes internal state/config of the client. this has only client-side effect.
  
  format:
    config                   - to print current config
    config save              - to save config to ~/.ispncon
    config <key> <value>     - to change config for currently running session
    
  configuration values:
  cache       - cache name
  host        - host name
  port        - port on host
  client.type - client type: hotrod|memcached|rest
  
  return:
    (exit code 0)
    * if configuration/client state was updated successfully, one line:
    STORED
    * if config with no parameters was supplied
    <multiple line output,
     with config values>
    
    (exit code 1)
    * in case of general error, one line: 
    ERROR <msg>""",
    
  "include" : """processes cache commands from the specified file. 
  the output depends on the commands present in the input file. the commands will be processed line by line.

  format:
    include <filename>
  
  return:
    exit code = exit code of the last command in the file."""
                    
}