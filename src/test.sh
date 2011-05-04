#!/bin/sh
#these are variables to change in your local environment:
INFINISPAN_DISTRIBUTION_NAME=infinispan-4.2.1.FINAL
INFINISPAN_DISTRIBUTION=/home/mlinhard/dev/install/infinispan-4.2.1.FINAL-all.zip
JBOSS_HOME=/home/mlinhard/dev/projects/jbossas7/jboss-7.0.0.Beta3

startserver() {
   if [ "${SERVER_RUNNING}x" != "x" ]; then
      fail "server already running"
   fi
   SERVER_TYPE=$1
   echo "starting server: $SERVER_TYPE"
   if [ $SERVER_TYPE == "memcached" -o $SERVER_TYPE == "hotrod" ]; then
      pushd $WORKDIR > /dev/null
      $ISPN_HOME/bin/startServer.sh -r $SERVER_TYPE -l localhost &> infinispan_stdout.log &
      SERVER_SHELL_PID=$!
      popd > /dev/null
      SERVER_RUNNING=true
      sleep 2
      echo "server started"
   elif [ $SERVER_TYPE == "rest" ]; then
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
      echo -e "deploy $ISPN_HOME/modules/rest/infinispan-server-rest.war\nquit" | $JBOSS_HOME/bin/jboss-admin.sh --connect localhost &> $WORKDIR/jbossadminlog_deploy.txt
      echo "war deployed"
   else
     fail "unknown server type"
   fi
}

stopserver() {
   echo "stopping server: $SERVER_TYPE"
   if [ $SERVER_TYPE == "memcached" -o $SERVER_TYPE == "hotrod" ]; then
      SERVER_PID=`ps -A -o "%p|%a" | grep "org\\.infinispan\\.server\\.core\\.Main" | cut -d\| -f 1`
      echo "SERVER_SHELL_PID=$SERVER_SHELL_PID, SERVER_PID=$SERVER_PID"
      kill -9 $SERVER_SHELL_PID
      kill -9 $SERVER_PID
      unset SERVER_RUNNING
   elif [ $SERVER_TYPE == "rest" ]; then
      echo -e "undeploy infinispan-server-rest.war\nquit" | $JBOSS_HOME/bin/jboss-admin.sh --connect localhost &> $WORKDIR/jbossadminlog_undeploy.txt
      SERVER_PID=`ps -A -o "%p|%a" | grep "org\\.jboss\\.as\\.standalone" | cut -d\| -f 1`
      echo "SERVER_SHELL_PID=$SERVER_SHELL_PID, SERVER_PID=$SERVER_PID"
      kill -9 $SERVER_SHELL_PID
      kill $SERVER_PID
      start_info=""
      while [ "${start_info}x" == "x" ]; do
          if [ -f $LOG_FILE ]; then
             start_info=`tail $LOG_FILE | grep "[org\.jboss\.as].*stopped in"`
          fi
          sleep 1
      done
      echo "server stopped"
      unset SERVER_RUNNING
   else
     fail "unknown server type"
   fi
}

fail() {
   echo $1
   if [ "${SERVER_RUNNING}x" != "x" ]; then
      stopserver $SERVER_TYPE
   fi
   exit 1
}

CMD=./ispncon.py
WORKDIR=work
mkdir -p $WORKDIR
ISPN_HOME=$WORKDIR/$INFINISPAN_DISTRIBUTION_NAME
if [ \! \( -d $ISPN_HOME \) ]; then
   pushd $WORKDIR
   unzip -q $INFINISPAN_DISTRIBUTION
   popd
fi

if [ -f ~/.ispncon ]; then
  echo "saving ~/.ispncon to $WORKDIR/user_ispncon"
  cp ~/.ispncon $WORKDIR/user_ispncon
fi


startserver memcached

echo -e "[ispncon]\nclient_type= memcached\nhost= localhost\nport= 11211" > ~/.ispncon

$CMD put a a
ret=`$CMD get a`

if [ $ret != "a" ]; then
   echo "expected: \"a\", returned: \"$ret\""
   fail "get didn't return expected value"
fi

stopserver memcached

startserver hotrod

echo -e "[ispncon]\nclient_type= hotrod\nhost= localhost\nport= 11222" > ~/.ispncon

$CMD put a a
ret=`$CMD get a`

if [ $ret != "a" ]; then
   echo "expected: \"a\", returned: \"$ret\""
   fail "get didn't return expected value"
fi

stopserver hotrod

startserver rest

echo -e "[ispncon]\nclient_type= rest\nhost= localhost\nport= 8080" > ~/.ispncon

$CMD put a a
ret=`$CMD get a`

if [ $ret != "a" ]; then
   echo "expected: \"a\", returned: \"$ret\""
   fail "get didn't return expected value"
fi

stopserver rest

if [ -f $WORKDIR/user_ispncon ]; then
  echo "restoring ~/.ispncon from $WORKDIR/user_ispncon"
  cp $WORKDIR/user_ispncon ~/.ispncon
fi



