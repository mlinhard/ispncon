Infinispan Console
------------------

Infinispan Console is a linux console tool written in python capable of doing simple operations with infinispan cache using the chosen client access (hotrod, memcached, rest/http). This might be handy for cache debugging/testing purposes and also provides a command line interface usable by linux shell scripts.


Documentation
-------------

http://community.jboss.org/wiki/InfinispanCommand-lineConsole


Version history
---------------

0.8.0
-----
tag of state as announced on infinispan-dev list

0.8.1
-----
fixed version info output
put parameter changed from --maxidle to --max-idle
fixed USAGE output
README.txt contains just basic info and points to wiki documentation
added version history
exists operation will be implemented by get operation in memcached
added version operation
"config save" works
issue_1: fix ConfigParser problem under python 2.6
issue_11: add -P --config "<key> <value>" command-line option
issue_7: hotrod client compatibility with java hotrod client
