# use docker to run tests in test/ and test_db/
#
# to override default tests, supply cmdline arguments, which will be passed to pytest
#
# to override default directories and names, set env variables:
#     TEST_DIR - location of directory where spindrift is cloned ($HOME/git)
#     TEST_NET - name of docker network shared by mysql container (test)
#     TEST_MYSQL - name of mysql container (mysql)
#     IMAGE - name of spindrift docker image (spindrift-dev)
#             see docker/Dockerfile.dev and docker-build.sh
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
./container.sh pytest "$@"
