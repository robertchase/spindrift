from spindrift.micro import Micro


PORT = 12345
PATH = '/test/ping'


def ping(request):
    return 'pong'


def on_ping(rc, result):
    assert rc == 0
    assert result == 'pong'


def test_ping():
    s = [
        'SERVER ping %s' % PORT,
        '  ROUTE %s$' % PATH,
        '    GET test.test_micro_ping.ping',
        'CONNECTION pinger http://localhost:%s' % PORT,
        '  RESOURCE get %s is_json=False' % PATH,
    ]
    micro = Micro().load(s).setup()

    c = micro.connection.pinger.resource.get(on_ping)
    while c.is_open:
        micro.network.service()
    assert c.t_http_data > 0
    micro.close()
