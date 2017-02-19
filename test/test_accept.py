import spindrift.network as network


PORT = 12345


class RejectServer(network.Handler):

    def on_accept(self):
        return False  # not letting anybody in

    def on_close(self, reason):
        assert reason == 'connection not accepted'  # message from Listener's close
        assert self.t_open == 0                     # connection never completed


def test_reject():
    n = network.Network()
    n.add_server(PORT, RejectServer)
    c = n.add_connection('localhost', PORT, network.Handler)  # random connection
    while c.is_open:
        n.service()
    n.close()


class AcceptServer(network.Handler):

    def on_ready(self):  # if we're here, we made it past on_accept
        self.test_close_reason = 'bye'
        self.close(self.test_close_reason)

    def on_close(self, reason):
        assert reason == self.test_close_reason  # message from on_ready close
        assert self.t_open != 0                  # connection completed


def test_accept():
    n = network.Network()
    n.add_server(PORT, AcceptServer)
    c = n.add_connection('localhost', PORT, network.Handler)  # random connection
    while c.is_open:
        n.service()
    n.close()
