import pytest
import spindrift.micro_fsm.parser as parser


@pytest.fixture
def par():
    p = parser.Parser()
    return p


def test_empty(par):
    assert par.setup is None
    assert par.teardown is None
    assert par.database is None
    assert len(par.connections) == 0
    assert len(par.servers) == 0


def test_recursive_file():
    with pytest.raises(parser.RecursiveMicro):
        parser.load('foo', files=['foo'])


def test_invalid_micro_file(par):
    with pytest.raises(parser.InvalidMicroSpecification):
        par.parse(dict())


def test_incomplete_line(par):
    with pytest.raises(parser.IncompleteLine):
        par.parse(['FOO'])


def test_unexpected_directive(par):
    with pytest.raises(parser.UnexpectedDirective):
        par.parse(['FOO bar'])


def test_parser_file_exception(par):
    with pytest.raises(parser.ParserFileException):
        par.parse(['CONNECTION 1'])


def test_log(par):
    p = par.parse(['log name=test level=info is_stdout=false'])
    assert p
    assert p.log.name == 'test'
    assert p.log.level == 'info'
    assert not p.log.is_stdout
    with pytest.raises(parser.ParserFileException):
        par.parse(['log name=test level=info is_stdout=false foo=bar'])


def test_server(par):
    p = par.parse(['server test 12345'])
    assert p
    assert len(p.servers) == 1
    s = p.servers['test']
    assert s.name == 'test'
    assert s.port == 12345
    c = p.config.server.test
    assert c
    assert c.port == 12345
    assert c.is_active
    assert not c.ssl.is_active
    with pytest.raises(parser.ParserFileException):
        par.parse(['server test 12345 foo=bar'])


def test_duplicate_port(par):
    with pytest.raises(parser.ParserFileException):
        par.parse([
            'server test 12345',
            'route abc',
            'server test 12345'
        ])


def test_unexpected_route(par):
    with pytest.raises(parser.UnexpectedDirective):
        par.parse(['route abc'])


def test_route(par):
    p = par.parse([
        'server test 12345',
        'route abc'
    ])
    assert p
    s = p.servers['test']
    assert len(s.routes) == 1
    r = s.routes[0]
    assert r.pattern == 'abc'
    assert len(r.methods) == 0


def test_method(par):
    p = par.parse([
        'server test 12345',
        'route abc',
        'get a.b.c',
        'put d.e.f',
        'route xyz',
        'get x.y.x',
        'post 1.2.3',
        'delete whatever',
    ])
    assert p
    s = p.servers['test']
    r = s.routes
    assert len(r) == 2
    t = r[0]
    assert t.pattern == 'abc'
    assert len(t.methods) == 2
    assert t.methods['get'] == 'a.b.c'
    assert t.methods['put'] == 'd.e.f'
    t = r[1]
    assert t.pattern == 'xyz'
    assert len(t.methods) == 3


def test_database(par):
    p = par.parse([])
    assert p.database is None
    p = par.parse(['database is_active=true'])
    assert p
    assert p.database.is_active
    assert p.database.user is None
    assert p.database.password is None
    assert p.database.database is None
    assert p.database.host is None
    assert p.database.port == 3306
    assert p.database.isolation == 'READ COMMITTED'
    assert p.database.timeout == 60.0
    assert p.database.long_query == 0.5
    assert not p.database.fsm_trace
    p = par.parse([
        (
            'database'
            ' is_active=false'
            ' user=foo password=bar database=yeah'
            ' host=localhost port=1234'
            " isolation='READ UNCOMMITTED'"
            ' timeout=42.5 long_query=1.0 fsm_trace=true'
        )
    ])
    assert p
    assert not p.database.is_active
    assert p.database.user == 'foo'
    assert p.database.password == 'bar'
    assert p.database.database == 'yeah'
    assert p.database.host == 'localhost'
    assert p.database.port == 1234
    assert p.database.isolation == 'READ UNCOMMITTED'
    assert p.database.timeout == 42.5
    assert p.database.long_query == 1.0
    assert p.database.fsm_trace


def test_connection(par):
    p = par.parse([])
    assert len(p.connections) == 0

    p = par.parse(['connection foo url'])
    assert p
    c = p.connections['foo']
    assert c
    assert c.url == 'url'
    assert c.is_json
    assert c.is_verbose
    assert c.timeout == 5.0
    assert c.handler is None
    assert c.wrapper is None
    assert c.setup is None
    assert not c.is_form
    assert c.code is None

    p = par.parse([(
        'connection foo'
        ' url=http://123.com'
        ' is_json=false'
        ' is_verbose=false'
        ' timeout=10.0'
        ' handler=a.b.c'
        ' wrapper=j.z'
        ' setup=whatever'
        ' is_form=true'
        ' code=rocks'
    )])
    assert p
    c = p.connections['foo']
    assert c
    assert c.url == 'http://123.com'
    assert not c.is_json
    assert not c.is_verbose
    assert c.timeout == 10.0
    assert c.handler == 'a.b.c'
    assert c.wrapper == 'j.z'
    assert c.setup == 'whatever'
    assert c.is_form
    assert c.code == 'rocks'
