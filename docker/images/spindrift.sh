cp ../../requirements.txt spindrift-test/
${DOCKER:-docker} build -t bob/spindrift-test spindrift-test
