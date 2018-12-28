${DOCKER:-docker} build -t spindrift-dev -f docker/Dockerfile.dev .
${DOCKER:-docker} build -t spindrift  -f docker/Dockerfile .
