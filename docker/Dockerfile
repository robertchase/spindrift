FROM spindrift-dev

RUN mkdir -p /install/spindrift
COPY . /install/spindrift
RUN cd /install/spindrift && rm -rf dist && ls -l && python setup.py install
