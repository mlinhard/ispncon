# -*- coding: utf-8 -*-

"""
Constant definition
"""

__author__ = "Michal Linhard"
__copyright__ = "(C) 2011 Red Hat Inc."

ISPNCON_VERSION = "0.8.0"

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
    if no operation is supplied, prints list of supported operations"""
                    
}