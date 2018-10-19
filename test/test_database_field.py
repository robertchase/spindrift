import pytest

from spindrift.database.field import Field, coerce_bool, coerce_int


def test_basic():
    fld = Field()
    assert fld
    assert fld.coerce.__name__ == '<lambda>'
    assert fld.coerce('123') == '123'
    assert fld.default is None
    assert fld.name is None
    assert fld.is_nullable is False
    assert fld.is_primary is False
    assert fld.expression is None
    assert fld.is_readonly is False
    assert fld.is_database is True


def test_expression():
    fld = Field()
    assert fld.is_readonly is False
    fld = Field(expression='whatever')
    assert fld.is_readonly


@pytest.mark.parametrize(
    'value,result', [
        (True, True),
        ('true', True),
        ('TrUe', True),
        (1, True),
        ('1', True),
        (False, False),
        ('false', False),
        ('FaLsE', False),
        (0, False),
        ('0', False),
    ],
)
def test_coerce_bool(value, result):
    assert coerce_bool(value) == result


@pytest.mark.parametrize(
    'value', [
        (2),
        ('2'),
        ('akk'),
        ('simply not true'),
    ],
)
def test_coerce_bool_fail(value):
    with pytest.raises(ValueError):
        coerce_bool(value)


@pytest.mark.parametrize(
    'value,result', [
        (1, 1),
        (1.0, 1),
        ('1', 1),
        ('100', 100),
        (123, 123),
    ],
)
def test_coerce_int(value, result):
    assert coerce_int(value) == result


@pytest.mark.parametrize(
    'value', [
        (1.2),
        ('1.2'),
        ('akk'),
    ],
)
def test_coerce_int_fail(value):
    with pytest.raises(ValueError):
        coerce_int(value)
