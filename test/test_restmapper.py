import pytest

import spindrift.rest.mapper as mapper


def handler1():
    pass


def handler2():
    pass


def test_simple():
    m = mapper.RESTMapper()
    m.add(
        '/foo/bar$',
        dict(get=mapper.RESTMethod('test.test_restmapper.handler1')),
    )
    rest_match = m.match('/foo/bar', 'GET')
    assert rest_match.handler == handler1
    assert len(rest_match.groups) == 0


def test_no_match():
    m = mapper.RESTMapper()
    m.add(
        '/foo/bar$',
        dict(get=mapper.RESTMethod('test.test_restmapper.handler1')),
    )
    rest_match = m.match('/foo/beer', 'GET')
    assert rest_match is None


def test_group():
    m = mapper.RESTMapper()
    m.add(
        '/foo/(\d+)/bar$',
        dict(get=mapper.RESTMethod('test.test_restmapper.handler1')),
    )
    rest_match = m.match('/foo/123/bar', 'GET')
    assert rest_match.handler == handler1
    assert rest_match.groups[0] == '123'


def test_first_wins():
    m = mapper.RESTMapper()
    m.add(
        '/foo/bar$',
        dict(get=mapper.RESTMethod('test.test_restmapper.handler1')),
    )
    m.add(
        '/foo/bar$',
        dict(get=mapper.RESTMethod('test.test_restmapper.handler2')),
    )
    rest_match = m.match('/foo/bar', 'GET')
    assert rest_match.handler == handler1


def test_rest_method():
    method = mapper.RESTMethod(
        None,
        [mapper.RESTArg(int)],
        [mapper.RESTArg(int, 'foo')]
    )
    assert method
    args, kwargs = method.coerce(
        ['1', '1'],
        {'foo': '10'}
    )
    assert args[0] == 1
    assert args[1] == '1'
    assert kwargs['foo'] == 10


def test_rest_method_error():
    method = mapper.RESTMethod(
        None,
        [mapper.RESTArg(int)],
        [mapper.RESTArg(int, 'foo')]
    )
    with pytest.raises(mapper.ArgumentCountMismatch):
        args, kwargs = method.coerce(
            [],
            {}
        )
    with pytest.raises(mapper.MissingRequiredContent):
        args, kwargs = method.coerce(
            [1],
            {}
        )
