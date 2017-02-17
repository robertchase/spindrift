import spindrift.network as network


'''
    standard 'hello world' for a network library

    to start the echo server run:

        python example/echo.py

    you can then connect to it with telnet on port
    12345 and see your input echoed back. the python
    executable must be 3.6+.
'''


class Echo(network.Handler):
    ''' an Echo object is created for each new connection  '''

    def on_open(self):
        print('open cid=%s' % self.id)

    def on_data(self, data):
        print('echoing: %s' % data.decode('utf8'))
        self.send(data)

    def on_close(self, reason):
        print('close cid=%s: %s' % (self.id, reason))


n = network.Network()
n.add_server(12345, Echo)
print('echo server started on 12345')
while True:  # runs forever: CTRL-C to exit
    n.service()
