import pytest

import spindrift.http as http
import spindrift.network as network


PORT = 12345


class Context(object):

    def __init__(self):
        self.server = 0
        self.client = 0


class Server(http.HTTPHandler):

    def on_http_data(self):
        self.context.server += 1
        self.http_send_server()


class Client(http.HTTPHandler):

    def on_ready(self):
        self.http_send()

    def on_http_data(self):
        self.context.client += 1
        self.close('done')


@pytest.fixture
def ctx():
    return Context()


@pytest.fixture
def net(ctx):
    n = network.Network()
    n.add_server(PORT, Server, context=ctx)
    yield n
    n.close()


def test_basic(ctx, net):
    c = net.add_connection('localhost', PORT, Client, context=ctx)
    while c.is_open:
        net.service()
    assert ctx.server == 1
    assert ctx.client == 1


class PipelineClient(http.HTTPHandler):

    def on_ready(self):
        self.http_send()
        self.http_send()
        self.http_send()

    def on_http_data(self):
        self.context.client += 1
        if self.context.client == 3:
            self.close()


def test_pipeline(ctx, net):
    c = net.add_connection('localhost', PORT, PipelineClient, context=ctx)
    while c.is_open:
        net.service()
    assert ctx.server == 3
    assert ctx.client == 3
