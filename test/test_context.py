import functools
import operator

import spindrift.network as network


PORT = 12345


class Context(object):

    def __init__(self):
        self.counter = 0


class CountingHandler(network.Handler):

    def on_ready(self):
        self.context.counter += 1  # bump the counter...
        self.close()               # and go away


def test_echo():
    c = Context()
    n = network.Network()
    n.add_server(PORT, CountingHandler, context=c)
    cons = []
    cons.append(n.add_connection('localhost', PORT, network.Handler))
    cons.append(n.add_connection('localhost', PORT, network.Handler))
    cons.append(n.add_connection('localhost', PORT, network.Handler))
    cons.append(n.add_connection('localhost', PORT, network.Handler))
    cons.append(n.add_connection('localhost', PORT, network.Handler))

    # keep going while any client connection is open
    while functools.reduce(operator.__or__, (c.is_open for c in cons), False):
        n.service()
    n.close()

    assert c.counter == len(cons)  # every connection counted once
