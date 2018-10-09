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


def test_calculated(db):

    FOO = 20
    BAR = 30
    FOOBAR = FOO + BAR

    def on_load(rc, result):
        assert rc == 0
        assert result.foobar == result.foo + result.bar
        assert result.foobar == FOOBAR
        db.is_done = True

    def on_save(rc, result):
        assert rc == 0
        p.load(on_load, result.id, cursor=db.cursor)

    p = Parent(foo=FOO, bar=BAR)
    p.save(on_save, cursor=db.cursor)
    db.run()
