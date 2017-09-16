import spindrift.network as network
from spindrift.rest.handler import RESTHandler as Handler
from spindrift.rest.handler import RESTContext as Context
from spindrift.rest.mapper import RESTMapper as Mapper


def echo(request, stuff):
    request.respond(stuff)


m = Mapper()
m.add('/echo/(.*)$', get='example.recho.echo')

n = network.Network()
n.add_server(12345, Handler, context=Context(m))
print('REST server started on 12345')
while True:  # runs forever: CTRL-C to exit
    n.service()
