.PHONY: bash connect build flake test mysql mysql-build

IMAGE := spindrift-dev
NAME := spindrift
NET := --net test
GIT := $(HOME)/git
WORKING := -w /opt/git/spindrift

VOLUMES := -v=$(GIT):/opt/git

DOCKER := docker run $(OPT) -it --rm  $(VOLUMES) $(WORKING) $(NET) -e PYTHONPATH=. --name $(NAME) $(IMAGE)

bash:
	$(DOCKER) /bin/bash

connect:
	docker exec -it $(NAME) bash

build:
	docker build -t $(IMAGE) -f Dockerfile.dev .

flake:
	$(DOCKER) flake8 spindrift test test_db

# --- test without database:
#     ARGS=test make test
test:
	$(DOCKER) pytest $(ARGS)

# --- MYSQL: start container and build test database
mysql:
	docker run $(OPT) -d -p 3306:3306 --name mysql $(NET) $(VOLUMES) -v=$(HOME)/mysql_data/:/var/lib/mysql/ -e MYSQL_ALLOW_EMPTY_PASSWORD=yes mysql:5.6

mysql-build:
	docker exec -it mysql bash -c "mysql -v < /opt/git/spindrift/test_db/schema.sql"
