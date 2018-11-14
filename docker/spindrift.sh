cp ../../requirements.txt spindrift/
${DOCKER:-docker} build -t spindrift spindrift
