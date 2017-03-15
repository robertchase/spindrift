from spindrift.micro.micro import Micro


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
    ]
    micro = Micro().load(s, None).start()

    c = micro.connection.pinger.get(on_ping, PATH, is_json=False)
    while c.is_open:
        micro.service()
    assert c.t_http_data > 0
    micro.close()
