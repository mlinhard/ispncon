#!/bin/sh
#################################### configuration #################################

#these are variables to change in your local environment:

# Infinispan 5.0.0.CR8
ISPN_HOME=/home/mlinhard/dev/projects/ispncon/test/infinispan-5.0.0.CR8
# JBoss AS 7.0.0.Final
JBOSS_HOME=/home/mlinhard/dev/projects/ispncon/test/as7

# you can obtain the Infinispan and JBoss AS distributions here:
# http://www.jboss.org/jbossas/downloads
# http://sourceforge.net/projects/infinispan/files/infinispan
# WARNING: the tests might modify files inside the given distribution directories

TESTHOST=localhost

CONFIG_MEMCACHED="\
[ispncon]\n\
client_type= memcached\n\
host= $TESTHOST\n\
port= 11211"

CONFIG_REST="\
[ispncon]\n\
client_type= rest\n\
host= $TESTHOST\n\
port= 8080"

CONFIG_HOTROD="\
[ispncon]\n\
client_type= hotrod\n\
host= $TESTHOST\n\
port= 11222"

#################################### test cases ####################################

test_basic_put_get() {
test_case_begin "test_basic_put_get"
	
ret=`$CMD put a a`
assertEquals "STORED" $ret
ret=`$CMD get a`
assertEquals "a" $ret

}

test_basic_put_get_return_codes() {
test_case_begin "test_basic_put_get_return_codes"

$CMD put a a > /dev/null
assertEquals "0" $?
$CMD get a > /dev/null
assertEquals "0" $?

}

test_versioned_put() {
test_case_begin "test_versioned_put"

ret=`$CMD put a_versioned a`
assertEquals "STORED" $ret
a_version=`$CMD version a_versioned`
wrong_version=`expr $a_version + 1`
ret=`$CMD put -v $wrong_version a_versioned b` # put with wrong version
assertEquals "CONFLICT" $ret
ret=`$CMD get a_versioned`
assertEquals "a" $ret # value shouldn't have changed
ret=`$CMD put -v $a_version a_versioned b` # put with right version
assertEquals "STORED" $ret
ret=`$CMD get a_versioned`
assertEquals "b" $ret # value should be changed

}

test_versioned_put_return_codes() {
test_case_begin "test_versioned_put_return_codes"

$CMD put a_versioned a > /dev/null
assertEquals "0" $?
a_version=`$CMD version a_versioned`
wrong_version=`expr $a_version + 1`
$CMD put -v $wrong_version a_versioned b > /dev/null # put with wrong version
assertEquals "3" $?
$CMD put -v $a_version a_versioned b > /dev/null # put with right version
assertEquals "0" $?

}

test_put_get_file() {
test_case_begin "test_put_get_file"

rm -rf $WORKDIR/file_input.txt
rm -rf $WORKDIR/file_output.txt

echo "This is sample file contents" > $WORKDIR/file_input.txt

ret=`$CMD put -i $WORKDIR/file_input.txt a_file`
assertEquals "STORED" $ret
ret=`$CMD get -o $WORKDIR/file_output.txt a_file`
assertEquals "" $ret
ret=`diff $WORKDIR/file_input.txt $WORKDIR/file_output.txt`
assertEquals "" $ret

}

#################################### helper functions ##############################

startserver() {
   if [ "${SERVER_RUNNING}x" != "x" ]; then
      fail "server already running"
   fi
   SERVER_TYPE=$1
   echo "starting server: $SERVER_TYPE"
   if [ $SERVER_TYPE == "memcached" -o $SERVER_TYPE == "hotrod" ]; then
      pushd $WORKDIR > /dev/null
      $ISPN_HOME/bin/startServer.sh -r $SERVER_TYPE -l $TESTHOST &> infinispan_stdout.log &
      SERVER_SHELL_PID=$!
      popd > /dev/null
      SERVER_RUNNING=true
      sleep 2
      echo "server started"
   elif [ $SERVER_TYPE == "rest" ]; then
      configFile=$JBOSS_HOME/standalone/configuration/standalone.xml
      sed "s/<inet-address value=\"[^\"]\+\"\/>/<inet-address value=\"${TESTHOST}\"\/>/" -i $configFile
      LOG_FILE=$WORKDIR/jbosslog.txt
      $JBOSS_HOME/bin/standalone.sh &> $LOG_FILE &
      SERVER_SHELL_PID=$!
      SERVER_RUNNING=true
      start_info=""
      while [ "${start_info}x" == "x" ]; do
          if [ -f $LOG_FILE ]; then
             start_info=`tail $LOG_FILE | grep "[org\.jboss\.as].*started in"`
          fi
          sleep 1
      done
      echo "server started"
      echo -e "deploy $ISPN_HOME/modules/rest/infinispan-server-rest.war\nquit" | $JBOSS_HOME/bin/jboss-admin.sh --connect $TESTHOST &> $WORKDIR/jbossadminlog_deploy.txt
      echo "war deployed"
   else
     fail "unknown server type"
   fi
}

stopserver() {
   if [ "$1" != "quiet" ]; then
     echo "stopping server: $SERVER_TYPE"
   fi
   if [ $SERVER_TYPE == "memcached" -o $SERVER_TYPE == "hotrod" ]; then
      SERVER_PID=`ps -A -o "%p|%a" | grep "org\\.infinispan\\.server\\.core\\.Main" | cut -d\| -f 1`
      if [ "$1" != "quiet" ]; then
        echo "SERVER_SHELL_PID=$SERVER_SHELL_PID, SERVER_PID=$SERVER_PID"
      fi
      kill -9 $SERVER_SHELL_PID &> /dev/null
      kill -9 $SERVER_PID &> /dev/null
      unset SERVER_RUNNING
   elif [ $SERVER_TYPE == "rest" ]; then
      if [ "$1" != "quiet" ]; then
        echo -e "undeploy infinispan-server-rest.war\nquit" | $JBOSS_HOME/bin/jboss-admin.sh --connect $TESTHOST &> $WORKDIR/jbossadminlog_undeploy.txt
      fi
      SERVER_PID=`ps -A -o "%p|%a" | grep "org\\.jboss\\.as\\.standalone" | cut -d\| -f 1`
      if [ "$1" != "quiet" ]; then
        echo "SERVER_SHELL_PID=$SERVER_SHELL_PID, SERVER_PID=$SERVER_PID"
      fi
      kill -9 $SERVER_SHELL_PID &> /dev/null
      kill $SERVER_PID &> /dev/null
      start_info=""
      while [ "${start_info}x" == "x" ]; do
          if [ -f $LOG_FILE ]; then
             start_info=`tail $LOG_FILE | grep "[org\.jboss\.as].*stopped in"`
          fi
          sleep 1
      done
      if [ "$1" != "quiet" ]; then
        echo "server stopped"
      fi
      unset SERVER_RUNNING
   else
     fail "unknown server type"
   fi
}

restore_user_config() {
   if [ -f $WORKDIR/user_ispncon ]; then
   	 if [ "$1" != "quiet" ]; then 
       echo "restoring ~/.ispncon from $WORKDIR/user_ispncon"
   	 fi
     cp $WORKDIR/user_ispncon ~/.ispncon
   fi
}

fail() {
  echo "FAIL $TESTCASE($SERVER_TYPE): $1"
  if [ "${SERVER_RUNNING}x" != "x" ]; then
    stopserver "quiet"
  fi
  restore_user_config "quiet"
  exit 1
}

assertEquals() { # 1 expected, 2 actual
  if [ "$1" != "$2" ]; then
  	fail "expected \"$1\", got \"$2\""
  fi
}

test_case_begin() {
    TESTCASE=$1
    echo "$1"
}


#################################### test run ####################################

CMD=ispncon
WORKDIR=work
mkdir -p $WORKDIR
TESTCASE="UNKNOWN"

# backup ~/.ispncon configuration file
if [ -f ~/.ispncon ]; then
  echo "saving ~/.ispncon to $WORKDIR/user_ispncon"
  cp ~/.ispncon $WORKDIR/user_ispncon
fi

# memcached tests
startserver memcached
echo -e $CONFIG_MEMCACHED > ~/.ispncon

test_basic_put_get
test_basic_put_get_return_codes
test_put_get_file

stopserver

# hotrod tests
startserver hotrod
echo -e $CONFIG_HOTROD > ~/.ispncon

test_basic_put_get
test_basic_put_get_return_codes
test_put_get_file
test_versioned_put
# doesn't work yet
#test_versioned_put_return_codes

stopserver

# rest tests
startserver rest
echo -e $CONFIG_REST > ~/.ispncon

test_basic_put_get
test_basic_put_get_return_codes
test_put_get_file

stopserver

# restore user's ~/.ispncon
restore_user_config
