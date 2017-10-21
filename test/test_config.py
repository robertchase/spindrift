import pytest
import spindrift.config as config


@pytest.mark.parametrize('value,expected', [
    (0, 0),
    (1, 1),
    (-1, -1),
    (5, 5),
    ('0', 0),
    ('1', 1),
    ('-1', -1),
    ('5', 5),
])
def test_validate_int(value, expected):
    assert config.validate_int(value) == expected


def test_validate_int_error():
    with pytest.raises(ValueError):
        config.validate_int('wrong')


@pytest.mark.parametrize('value,expected', [
    (0, False),
    (1, True),
    (True, True),
    ('true', True),
    ('TRUE', True),
    ('TrUe', True),
    (False, False),
    ('false', False),
    ('FALSE', False),
    ('FaLsE', False),
])
def test_validate_bool(value, expected):
    assert config.validate_bool(value) == expected


@pytest.mark.parametrize('value', [
    5,
    'wrong',
])
def test_validate_bool_error(value):
    with pytest.raises(ValueError):
        config.validate_bool(value)


@pytest.fixture
def cfg():
    c = config.Config()
    c._define('foo', value='bar')
    return c


def test_default(cfg):
    assert cfg.foo == 'bar'


def test_set(cfg):
    cfg._set('foo', 'whatever')
    assert cfg.foo == 'whatever'


def test_int(cfg):
    cfg._define('foo', value=0, validator=config.validate_int)
    cfg._set('foo', '100')
    assert cfg.foo == 100
    with pytest.raises(ValueError):
        cfg._set('foo', 'wrong')


def test_load(cfg):
    cfg._load(['foo=123'])
    assert cfg.foo == '123'


@pytest.mark.parametrize('value,expected', [
    (['foo=test', '#foo=comment'], 'test'),
    (['foo=test#etc'], 'test'),
    (['foo=test\#etc'], 'test#etc'),
    (['#foo=test'], 'bar'),
    (['#foo=#test'], 'bar'),
])
def test_comment(value, expected, cfg):
    cfg._load(value)
    assert cfg.foo == expected
