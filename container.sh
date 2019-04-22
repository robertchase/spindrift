#!/usr/bin/env bash
DIR=${TEST_DIR:-$HOME/git}
NET=${TEST_NET:-test}
MYSQL_HOST=${TEST_MYSQL:-mysql}
IMAGE=${IMAGE:-spindrift-dev}

docker run $OPT -it --rm -v=$DIR:/opt/git -w /opt/git/spindrift --net $NET -e PYTHONPATH=. -e MYSQL_HOST=$MYSQL_HOST --name spindrift $IMAGE "$@"
