import spindrift.rest.mapper as mapper


def handler1():
    pass


def handler2():
    pass


def test_simple():
    m = mapper.RESTMapper()
    m.add('/foo/bar$', get='test.test_restmapper.handler1')
    h, g = m.match('/foo/bar', 'GET')
    assert h == handler1
    assert len(g) == 0


def test_no_match():
    m = mapper.RESTMapper()
    m.add('/foo/bar$', get='test.test_restmapper.handler1')
    h, g = m.match('/foo/beer', 'GET')
    assert h is None
    assert g is None


def test_group():
    m = mapper.RESTMapper()
    m.add('/foo/(\d+)/bar$', get='test.test_restmapper.handler1')
    h, g = m.match('/foo/123/bar', 'GET')
    assert h == handler1
    assert g[0] == '123'


def test_first_wins():
    m = mapper.RESTMapper()
    m.add('/foo/bar$', get='test.test_restmapper.handler1')
    m.add('/foo/bar$', get='test.test_restmapper.handler2')
    h, g = m.match('/foo/bar', 'GET')
    assert h == handler1
