FROM ubuntu:18.04
RUN apt-get update && apt-get upgrade -y && apt-get install -y vim git man screen curl unzip telnet tree htop lsof python3-pip python3-pytest
RUN rm /bin/sh && ln -s /bin/bash /bin/sh
RUN ln -s /usr/bin/python3 /usr/bin/python
RUN ln -s /usr/bin/pip3 /usr/bin/pip
RUN ln -s /usr/bin/pytest-3 /usr/bin/pytest

COPY requirements.txt /opt
RUN pip install -r /opt/requirements.txt
