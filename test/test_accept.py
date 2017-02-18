import spindrift.network as network


PORT = 12345


class RejectServer(network.Handler):

    def on_accept(self):
        return False

    def on_close(self, reason):
        assert reason == 'connection not accepted'
        assert self.t_open == 0


def test_reject():
    n = network.Network()
    n.add_server(PORT, RejectServer)
    c = n.add_connection('localhost', PORT, network.Handler)
    while c.is_open:
        n.service()
    n.close()


class AcceptServer(network.Handler):

    def on_ready(self):
        self.test_close_reason = 'bye'
        self.close(self.test_close_reason)

    def on_close(self, reason):
        assert reason == self.test_close_reason
        assert self.t_open != 0


def test_accept():
    n = network.Network()
    n.add_server(PORT, network.Handler)
    c = n.add_connection('localhost', PORT, AcceptServer)
    while c.is_open:
        n.service()
    n.close()
