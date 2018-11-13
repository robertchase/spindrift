import datetime

from spindrift.micro import Micro


PORT = 12345
PATH = '/test/coerce'
ID = 123
DATE = datetime.date(2018, 12, 13)


def to_date(ts):
    return datetime.datetime.strptime(ts, '%Y-%m-%d').date()


def coerce(request, id, when):
    assert id == ID
    return when.isoformat()


def on_coerce(rc, result):
    assert rc == 0
    assert result == DATE.isoformat()


def test_ping():
    s = [
        'SERVER coerce {}'.format(PORT),
        r'  ROUTE {}/(?P<id>\d+)$'.format(PATH),
        '    TYPE int',
        '    GET test.test_micro_coerce.coerce',
        '        CONTENT when type=test.test_micro_coerce.to_date',
        'CONNECTION coerce http://localhost:{}'.format(PORT),
        '  RESOURCE get %s/{id} is_json=False' % PATH,
        '    REQUIRED when',
    ]
    micro = Micro().load(s).setup()

    c = micro.connection.coerce.resource.get(
        on_coerce,
        ID,
        DATE.isoformat(),
    )
    while c.is_open:
        micro.network.service()
    assert c.t_http_data > 0
    micro.close()
