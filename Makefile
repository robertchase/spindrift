.PHONY: bash build test

GIT := $(HOME)/git
IMAGE := spindrift-dev
NAME := spindrift
VOLUMES := -v=$(GIT):/opt/git
WORK := -w /opt/git/$(NAME)
NET := --net test

RUN := docker run $(OPT) -it --rm $(VOLUMES) $(NET) --name $(NAME) $(WORK) $(IMAGE)

bash:
	$(RUN) bash

build:
	docker build -t $(IMAGE) -f docker/Dockerfile.dev .

test:
	$(RUN) pytest $(ARGS)
