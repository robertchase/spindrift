# use docker to run tests in test/ and test_db/
#
# to override default tests, supply cmdline arguments, which will be passed to pytest
#
# to override default directories and names, set env variables:
#     TEST_GIT - location of git directory where spindrift is cloned ($HOME/git)
#     TEST_NET - name of docker network shared by mysql container (test)
#     TEST_MYSQL_HOST - name of mysql container (mysql)
#     TEST_IMAGE - name of spindrift docker image (bob/spindrift-test)
#                  see docker/images/build.sh
#
# assumes: 1. docker is running
#          2. mysql container is running
#          3. test_db/schema.sql has been run
#
# variation: if you want non-database tests only, then the assumptions are simpler:
#          1. docker is running
#
#          * pass "test" to the script to limit pytest to the "test" directory
#
TEST_GIT=${TEST_GIT:-$HOME/git}
TEST_NET=${TEST_NET:-test}
TEST_MYSQL_HOST=${TEST_MYSQL_HOST:-mysql}
TEST_IMAGE=${TEST_IMAGE:-bob/spindrift-test}

CMD=${*:-test test_db}
GIT=/opt/git

docker run --rm -v=$TEST_GIT:$GIT -w $GIT/spindrift --net $TEST_NET -e MYSQL_HOST=$TEST_MYSQL_HOST -e PYTHONPATH=$GIT/ergaleia:$GIT/fsm:. $TEST_IMAGE pytest $CMD
