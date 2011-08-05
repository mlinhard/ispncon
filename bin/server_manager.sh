#!/bin/sh
################################## Infinispan server management script ##################################

usage() {
	printf "Usage: %s: [<options>] <command> <server_type> <server_name>\n" $(basename $0)
   echo   " options:"
   echo   "  -h <host>"
   echo   "  -p <port>"
   echo   "  -d <port> enable java remote debugger at this port"
   echo   "  -D <port> enable java remote debugger at this port, suspend mode"
   echo   "  -i <dir>  Infinispan home directory"
   echo   "  -f <dir>  server home directory"
   echo   "  -c <file> server config file"
   echo   "  -k        kill the server with SIGKILL (only for stop command)"
   echo   " command:"
   echo   "   start   - start the server"
   echo   "   log     - show tail of the server log"
   echo   "   out     - show tail of the server stdout"
   echo   "   stop    - stop the server"
   echo   " server_type:"
   echo   "   hotrod"
   echo   "   memcached"
   echo   "   rest"
   echo   "   edg"
   exit 1
}

################################## Functions ############################################################

# Validates Infinispan distribution home folder
# arg1 = ispn home folder
validate_ispn_home() {

if [ ! -d $1 ]; then
	echo "ERROR Infinispan distribution directory doesn't exist: ${1}"
	exit 1
fi
if [ ! -d $1/bin ]; then
   echo "ERROR Invalid Infinispan distribution directory: ${1}. Missing bin subdirectory."
   exit 1
fi
if [ ! -f $1/bin/startServer.sh ]; then
   echo "ERROR Invalid Infinispan distribution directory: ${1}. Missing startServer.sh script."
   exit 1
fi

}

# Validates JBoss AS 7 home folder
# arg1 = jboss home folder
validate_jbossas7_home() {

if [ ! -d "$1" ]; then
   echo "ERROR JBoss AS7 home directory doesn't exist: ${1}"
   exit 1
fi
if [ ! -d "$1/bin" ]; then
   echo "ERROR Invalid JBoss AS7 home directory: ${1}. Missing bin subdirectory."
   exit 1
fi
if [ ! -d "$1/standalone" ]; then
   echo "ERROR Invalid JBoss AS7 home directory: ${1}. Missing standalone subdirectory."
   exit 1
fi
if [ ! -f "$1/bin/standalone.sh" ]; then
   echo "ERROR Invalid JBoss AS7 home directory: ${1}. Missing standalone.sh script."
   exit 1
fi
if [ ! -f "$1/standalone/configuration/standalone.xml" ]; then
   echo "ERROR Invalid JBoss AS7 home directory: ${1}. Missing standalone.xml config file."
   exit 1
fi

}

#start standalone infinispan server as in bin/startServer.sh
#needs only ispn_home
start_ispn_server() {
   validate_ispn_home "$ispn_home"
   
	source "$ispn_home/bin/functions.sh"
	
	add_classpath "$ispn_home"/*.jar
	add_classpath "$ispn_home/lib"
	add_classpath "$ispn_home/modules/memcached"
	add_classpath "$ispn_home/modules/hotrod"
	add_classpath "$ispn_home/modules/websocket"
	
	add_jvm_args $JVM_PARAMS
	add_jvm_args '-Djava.net.preferIPv4Stack=true'
	
	if [ "x${debugport}" != "x" ]; then
      add_jvm_args "-Xrunjdwp:transport=dt_socket,address=${debugport},server=y,suspend=${debugsuspend}"
	fi
	
   add_program_args "-l ${srvhost}"
   add_program_args "-p ${srvport}"
	
	start org.infinispan.server.core.Main
}

#start AS7 with infinispan-server-rest.war deployment
#needs both server_home and ispn_home
start_rest_server() {
   validate_ispn_home "$ispn_home"
   validate_jbossas7_home "$server_home"

}

#start JBoss Enterprise Datagrid (contains all server modules)
#needs only server_home
start_edg_server() {
   validate_jbossas7_home "$server_home"

   configFile="$server_home/standalone/configuration/standalone.xml"

   if [ "${srvconfig}x" != "x" ]; then
   	if [ ! -f "${srvconfig}" ]; then
   		echo "Error: cannot find AS7 server configuration file: ${srvconfig}"
   		exit 1
   	fi
   	#overwrite standalone.xml
   	cp -f "$srvconfig" "$configFile"
   fi
   
   sed "s/<inet-address value=\"[^\"]*\"\/>/<inet-address value=\"${srvhost}\"\/>/" -i "$configFile"
   
   JAVA_OPTS="-Xms64m -Xmx256m -XX:MaxPermSize=128m -Djava.net.preferIPv4Stack=true -Dorg.jboss.resolver.warning=true -Dsun.rmi.dgc.client.gcInterval=3600000 -Dsun.rmi.dgc.server.gcInterval=3600000"
   JAVA_OPTS="$JAVA_OPTS -Djboss.modules.system.pkgs=org.jboss.byteman"
   JAVA_OPTS="$JAVA_OPTS -Dispnconsrv.name=${srvname}"
   if [ "x${debugport}" != "x" ]; then
      JAVA_OPTS="$JAVA_OPTS -Xrunjdwp:transport=dt_socket,address=${debugport},server=y,suspend=${debugsuspend}"
   fi
   export JAVA_OPTS
   
   $server_home/bin/standalone.sh &> $srvoutfile &

   start_info=""
   error_info=""
   while [ "${start_info}x" == "x" -a "${error_info}x" == "x" ]; do
      if [ -f $srvoutfile ]; then
         start_info=`tail $srvoutfile | grep "[org\.jboss\.as].*started in"`
         error_info=`tail $srvoutfile | grep "[org\.jboss\.as].*started (with errors) in"`
      fi
      sleep 1
   done

   SERVER_PID=`ps -A -o "%p|%a" | grep "\-Dispnconsrv\\.name=${srvname}.*org\\.jboss\\.as\\.standalone" | cut -d\| -f 1`
   if [ "${SERVER_PID}x" == "x" ]; then
      echo "WARNING: couldn't grep server PID, you'll have to kill the server manually" 
   fi
   echo $SERVER_PID > $srvpidfile

   if [ "${error_info}x" == "x" ]; then
      echo "SERVER_STARTED"
   else
      echo "SERVER_STARTED_WITH_ERRORS"
   fi
}

stop_edg_server() {
	if [ "${killharsh}" == "true" ]; then
      kill -9 `cat $srvpidfile`  
      if [ $? != 0 ]; then
      	echo "ERROR kill unsuccessfull"
      	exit 1
      fi
	else
      kill `cat $srvpidfile`  
      if [ $? != 0 ]; then
         echo "ERROR kill unsuccessfull"
         exit 1
      fi
	   start_info=""
	   while [ "${start_info}x" == "x" ]; do
	      if [ -f $srvoutfile ]; then
	         start_info=`tail $srvoutfile | grep "[org\.jboss\.as].*stopped in"`
	      fi
	      sleep 1
	   done
	fi
   rm $srvoutfile
   rm $srvpidfile

   echo "SERVER_STOPPED"
}

assert_not_running() {
   if [ -f "$srvpidfile" -o -f "$srvoutfile" ]; then
   	echo "ERROR Server \"${srvname}\" is already running."
      echo "       (if you suspect that this is not true, please remove these files manually:"
      echo "       $srvpidfile"
      echo "       $srvoutfile)"
   	exit 1
   fi
}

assert_running() {
   if [ ! -f "$srvpidfile" -o ! -f "$srvoutfile" ]; then
      echo "ERROR Server \"${srvname}\" is not running."
         if [ -f "$srvpidfile" ]; then
         echo "Removing file $srvpidfile"
         rm $srvpidfile
      fi
      if [ -f "$srvoutfile" ]; then
      	echo "Removing file $srvoutfile"
      	rm $srvoutfile
      fi
      exit 1
   fi
}

################################## Script start #########################################################

srvhost=
srvport=
srvconfig=
debugport=
debugsuspend="n"
server_home=
ispn_home=
killharsh="false"
while getopts 'h:p:d:D:i:f:c:k' OPTION
   do
   case $OPTION in
      h) srvhost="$OPTARG"
      ;;
      p) srvport="$OPTARG"
      ;;
      d) debugport="$OPTARG"
      ;;
      D) debugport="$OPTARG"
         debugsuspend="y"
      ;;
      i) ispn_home="$OPTARG"
      ;;
      f) server_home="$OPTARG"
      ;;
      c) srvconfig="$OPTARG"
      ;;
      k) killharsh="true"
      ;;
      ?) usage
      ;;
   esac
done
shift $(($OPTIND - 1))
if [ $# -ne 3 ]; then
   usage
fi
srvcommand="$1"
srvtype="$2"
srvname="$3"
if [[ "$srvcommand" != @(start|log|out|stop) ]]; then
   echo "ERROR Unsupported command: $srvcommand"
   exit 1
fi
if [[ "$srvtype" != @(hotrod|memcached|rest|edg) ]]; then
   echo "ERROR Unsupported server type: $srvtype"
   exit 1
fi
if [[ ! "$srvname" =~ ^[a-zA-Z0-9_]+$ ]]; then
   echo "ERROR Illegal character in server name: $srvname"
   exit 1
fi
srvpidfile="/tmp/ispnconsrv.${srvname}.pid"
srvoutfile="/tmp/ispnconsrv.${srvname}.out"

# everything should be validated by now
#echo "srvcommand=${srvcommand}"
#echo "srvtype=${srvtype}"
#echo "srvname=${srvname}"
#echo "srvhost=${srvhost}"
#echo "srvport=${srvport}"
#echo "debugport=${debugport}"
#echo "debugsuspend=${debugsuspend}"
#echo "ispn_home=${ispn_home}"
#echo "server_home=${server_home}"

#now let's branch into different activities

if [ "$srvcommand" == "start" ]; then
	assert_not_running
   if [[ "$srvtype" == @(hotrod|memcached) ]]; then
   	echo "ERROR not yet supported"
   elif [ "$srvtype" == "rest" ]; then
      echo "ERROR not yet supported"
   elif [ "$srvtype" == "edg" ]; then
      start_edg_server
   fi
elif [ "$srvcommand" == "log" ]; then
   echo "ERROR not yet supported"
elif [ "$srvcommand" == "out" ]; then
   assert_running
   tail -f $srvoutfile
elif [ "$srvcommand" == "stop" ]; then
   assert_running
   if [[ "$srvtype" == @(hotrod|memcached) ]]; then
      echo "ERROR not yet supported"
   elif [ "$srvtype" == "rest" ]; then
      echo "ERROR not yet supported"
   elif [ "$srvtype" == "edg" ]; then
      stop_edg_server
   fi
else
   echo "ERROR Unsupported command: $srvcommand"
   exit 1
fi

