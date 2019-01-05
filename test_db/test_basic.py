from spindrift.database.dao import DAO
from spindrift.database.field import Field, coerce_int


class Parent(DAO):

    TABLENAME = 'parent'

    id = Field(coerce_int, is_primary=True)
    foo = Field(coerce_int, default=10)
    bar = Field(coerce_int, is_nullable=True)
    foobar = Field(expression='foo+bar')


def test_default():

    p = Parent()
    assert p.foo == 10


def test_calculated(sync):

    FOO = 20
    BAR = 30
    FOOBAR = FOO + BAR

    p = Parent(foo=FOO, bar=BAR).save(sync)
    result = Parent.load(sync, p.id)
    assert result.foobar == result.foo + result.bar
    assert result.foobar == FOOBAR
