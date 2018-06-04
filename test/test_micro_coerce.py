import datetime

from spindrift.micro import Micro


PORT = 12345
PATH = '/test/coerce'
ID = 123
DATE = datetime.date(2018, 12, 13)


def to_date(ts):
    return datetime.datetime.strptime(ts, '%Y-%m-%d').date()


def coerce(request, id, when):
    return (id, when)


def on_coerce(rc, result):
    assert rc == 0
    a, b = result
    assert a == ID
    assert b == DATE


def test_ping():
    s = [
        'SERVER coerce {}'.format(PORT),
        '  ROUTE {}/(\d+)$'.format(PATH),
        '    ARG int',
        '    GET test.test_micro_coerce.coerce',
        '        CONTENT when type=test.test_micro_coerce.to_date',
        'CONNECTION coerce http://localhost:{}'.format(PORT),
        '  RESOURCE get {}/{} is_json=False'.format(PATH, ID),
        '    REQUIRED when',
    ]
    micro = Micro().load(s).setup()

    c = micro.connection.coerce.resource.get(
        on_coerce,
        DATE.isoformat(),
    )
    while c.is_open:
        micro.network.service()
    assert c.t_http_data > 0
    micro.close()
