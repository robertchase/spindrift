import spindrift.network as network


PORT = 12345


class EchoServer(network.Handler):

    def on_data(self, data):
        self.send(data)


class EchoClient(network.Handler):

    def on_ready(self):
        self.test_data = b'test_data'
        self.send(self.test_data)

    def on_data(self, data):
        assert data == self.test_data
        self.close()


def test_echo():
    n = network.Network()
    n.add_server(PORT, EchoServer)
    c = n.add_connection('localhost', PORT, EchoClient)
    while c.is_open:
        n.service()
