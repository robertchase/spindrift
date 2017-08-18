import logging

import spindrift.network as network
from spindrift.rest.handler import RESTHandler as Handler
from spindrift.rest.handler import RESTContext as Context
from spindrift.rest.mapper import RESTMapper as Mapper


logging.basicConfig(level=logging.DEBUG)


class MyHandler(Handler):

    def on_rest_exception(self, exception_type, exception_value, exception_traceback):
        import traceback
        return traceback.format_exc(exception_traceback)


def echo(request, stuff):

    def on_success(request, result):
        request.respond(201, result)

    def on_error(request, result):
        print(result)
        request.respond(400)

    request.call(
        echo_1,
        args=stuff,
        on_success=on_success,
        on_error=on_error,
        on_none_404=True,
    )


def echo_1(callback, stuff):
    if stuff == 'none':
        return callback(0, None)
    if stuff == 'error':
        return callback(1, 'oh no!')
    callback(0, 'echo-1: %s' % stuff)


m = Mapper()
m.add('/echo/(.*)$', get='example.call.echo')

n = network.Network()
n.add_server(12345, MyHandler, context=Context(m))
print('REST server started on 12345')
while True:  # runs forever: CTRL-C to exit
    n.service()
