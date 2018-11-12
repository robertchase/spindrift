FROM ubuntu:16.04
RUN apt-get update && apt-get upgrade -y && apt-get install -y vim git man screen curl unzip telnet tree htop lsof
RUN rm /bin/sh && ln -s /bin/bash /bin/sh

RUN apt-get update && apt-get upgrade -y && apt-get install -y python python-pip python-dev libffi-dev libssl-dev
RUN apt-get install -y libbz2-dev

RUN curl https://www.python.org/ftp/python/3.6.4/Python-3.6.4.tgz -o Python-3.6.4.tgz
RUN tar xvzf Python-3.6.4.tgz && cd Python-3.6.4 && ./configure && make altinstall && make install

RUN rm /usr/bin/python && ln -s /usr/local/bin/python3.6 /usr/bin/python
