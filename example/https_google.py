import spindrift.network as network

from example.http_google import Google


n = network.Network()
c = n.add_connection('www.google.com', 443, Google, is_ssl=True)
while c.is_open:
    n.service()
