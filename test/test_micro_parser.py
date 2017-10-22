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
    assert p.log.is_stdout == 'false'
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
