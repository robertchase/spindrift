# run tests in test/ and test_db/
#
# to override default tests, supply cmdline arguments, which will be passed to pytest
#
# to override default directories and names, set env variables:
#     TEST_GIT - location of git directory where spindrift is cloned ($HOME/git)
#     TEST_NET - name of docker network shared by mysql container (test)
#     TEST_MYSQL_HOST - name of mysql container (mysql)
#     TEST_IMAGE - name of python3.6 docker image (bob/python3.6)
#
# assumes: 1. docker is running
#          2. a python3.6+ image is available ($TEST_IMAGE below)
#             with mysql-client and pytest installed
#          3. mysql container is running
#          4. test_db/schema.sql has been run
#
TEST_GIT=${TEST_GIT:-$HOME/git}
TEST_NET=${TEST_NET:-test}
TEST_MYSQL_HOST=${TEST_MYSQL_HOST:-mysql}
TEST_IMAGE=${TEST_IMAGE:-bob/python3.6}

CMD=${*:-test test_db}

docker run --rm -v=$TEST_GIT:/opt/git -w /opt/git/spindrift --net $TEST_NET -e MYSQL_HOST=$TEST_MYSQL_HOST $TEST_IMAGE pytest $CMD
