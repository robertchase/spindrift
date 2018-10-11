from spindrift.database.dao import DAO
from spindrift.database.field import Field, coerce_int


class Parent(DAO):

    TABLENAME = 'parent'

    id = Field(coerce_int, is_primary=True)
    foo = Field(coerce_int)
    bar = Field(coerce_int, is_nullable=True)


def test_save(db):

    def on_save(rc, result):
        assert rc == 0
        assert isinstance(result.id, int)
        db.is_done = True

    Parent(foo=10).save(on_save, cursor=db.cursor)
    db.run()


def test_simultaneous(db):

    def on_save(rc, result):
        assert rc != 0
        assert result == 'query started before last query ended'
        db.is_done = True

    Parent(foo=10).save(on_save, cursor=db.cursor)
    Parent(foo=10).save(on_save, cursor=db.cursor)


def test_missing_null_field(db):

    def on_save(rc, result):
        assert rc != 0
        assert result == "Column 'foo' cannot be null"
        db.is_done = True

    Parent().save(on_save, cursor=db.cursor)
    db.run()


def test_reload(db):

    def on_load(rc, result):
        assert rc == 0
        assert result.foo == 123
        db.is_done = True

    def on_save(rc, result):
        assert rc == 0
        Parent.load(on_load, result.id, cursor=db.cursor)

    p = Parent(foo=123)
    p.save(on_save, cursor=db.cursor)
    db.run()


def test_insert(db):

    ID = 7

    def on_load(rc, result):
        assert rc == 0
        assert result.foo == 123
        db.is_done = True

    def on_insert(rc, result):
        assert rc == 0
        assert result.id == ID
        Parent.load(on_load, result.id, cursor=db.cursor)

    p = Parent(foo=123)
    p.insert(on_insert, id=ID, cursor=db.cursor)
    db.run()


def test_delete(db):

    ID = 7

    def on_load(rc, result):
        assert rc == 0
        assert result is None
        db.is_done = True

    def on_delete(rc, result):
        assert rc == 0
        Parent.load(on_load, ID, cursor=db.cursor)

    def on_insert(rc, result):
        assert rc == 0
        result.delete(on_delete, cursor=db.cursor)

    p = Parent(foo=123)
    p.insert(on_insert, id=ID, cursor=db.cursor)
    db.run()
