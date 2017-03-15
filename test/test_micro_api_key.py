from spindrift.micro.micro import Micro


PORT = 12345
PATH = '/test/ping'
KEY = 'my_secret'


def ping(request):
    return 'pong'


def on_ping_noauth(rc, result):
    assert rc == 1
    assert result == 'Unauthorized'


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
    cfg = [
        'server.ping.api_key=%s' % KEY,
    ]
    micro = Micro().load(s, cfg).start()

    c = micro.connection.pinger.get(on_ping_noauth, PATH, is_json=False)
    cc = micro.connection.pinger.get(on_ping, PATH, api_key=KEY, is_json=False)
    while c.is_open or cc.is_open:
        micro.service()
    assert c.t_http_data > 0
    assert cc.t_http_data > 0
    micro.close()
