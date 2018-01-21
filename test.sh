# use docker to run tests in test/ and test_db/
#
# to override default tests, supply cmdline arguments, which will be passed to pytest
#
# to override default directories and names, set env variables:
#     TEST_GIT - location of git directory where spindrift and ergaleia are cloned ($HOME/git)
#     TEST_NET - name of docker network shared by mysql container (test)
#     TEST_MYSQL_HOST - name of mysql container (mysql)
#     TEST_IMAGE - name of python3.6 docker image (bob/python3.6)
#
# assumes: 1. docker is running
#          2. a python3.6+ image is available ($TEST_IMAGE below)
#             with pytest installed
#          3. mysql container is running
#          4. test_db/schema.sql has been run
#
# variation: if you want non-database tests only, then the assumptions are simpler:
#          1. docker is running
#          2. a python3.6+ image is available with pytest installed
#
#          * pass "test" to the script to limit pytest to the "test" directory
#
TEST_GIT=${TEST_GIT:-$HOME/git}
TEST_NET=${TEST_NET:-test}
TEST_MYSQL_HOST=${TEST_MYSQL_HOST:-mysql}
TEST_IMAGE=${TEST_IMAGE:-bob/python3.6}

CMD=${*:-test test_db}
GIT=/opt/git

docker run --rm -v=$TEST_GIT:$GIT -w $GIT/spindrift --net $TEST_NET -e MYSQL_HOST=$TEST_MYSQL_HOST -e PYTHONPATH=$GIT/spindrift:$GIT/ergaleia:$GIT/fsm $TEST_IMAGE pytest $CMD
