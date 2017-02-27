import spindrift.network as network
import spindrift.rest as rest
import spindrift.rest_mapper as rest_mapper


class Rest(rest.RESTHandler):

    def on_open(self):
        print('open cid=', self.id)

    def on_rest_data(self, request, *groups):
        print('rest cid=', self.id, 'method=', self.http_method, 'resource=', self.http_resource)

    def on_rest_no_match(self):
        print('failed match cid=', self.id, 'method=', self.http_method, 'resource=', self.http_resource)

    def on_close(self, reason):
        print('close cid=', self.id, ':', reason)


def ping(request):
    request.respond('pong')


m = rest_mapper.RESTMapper()
m.add('/test/ping$', get='example.rest.ping')

n = network.Network()
n.add_server(12345, Rest, context=m)
print('rest server started on 12345')
while True:  # runs forever: CTRL-C to exit
    n.service()
