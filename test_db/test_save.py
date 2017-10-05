from spindrift.dao.dao import DAO


class Parent(DAO):

    TABLE = 'parent'

    FIELDS = (
        'id',
        'foo',
        'bar',
    )


def test_save(db):

    def on_save(rc, result):
        assert rc == 0
        assert isinstance(result.id, int)

    Parent(foo=10).save(on_save, cursor=db.cursor)
    db.run()


def test_simultaneous(db):

    def on_save(rc, result):
        assert rc != 0
        assert result == 'query started before last query ended'

    Parent(foo=10).save(on_save, cursor=db.cursor)
    Parent(foo=10).save(on_save, cursor=db.cursor)


def test_missing_null_field(db):

    def on_save(rc, result):
        assert rc != 0
        assert result == "Column 'foo' cannot be null"

    Parent().save(on_save, cursor=db.cursor)
    db.run()


def test_reload(db):

    test = {'is_loaded': False}

    def on_load(rc, result):
        assert rc == 0
        assert result.foo == 123
        test['is_loaded'] = True

    def on_save(rc, result):
        assert rc == 0
        Parent.load(on_load, result.id, cursor=db.cursor)

    p = Parent(foo=123)
    p.save(on_save, cursor=db.cursor)

    db.run()

    assert test['is_loaded']


def test_insert(db):

    test = {'is_loaded': False}
    ID = 7

    def on_load(rc, result):
        assert rc == 0
        assert result.foo == 123
        test['is_loaded'] = True

    def on_insert(rc, result):
        assert rc == 0
        assert result.id == ID
        Parent.load(on_load, result.id, cursor=db.cursor)

    p = Parent(foo=123)
    p.insert(on_insert, id=ID, cursor=db.cursor)

    db.run()

    assert test['is_loaded']


def test_delete(db):

    test = {'is_loaded': False}
    ID = 7

    def on_load(rc, result):
        assert rc == 0
        assert result is None
        test['is_loaded'] = True

    def on_delete(rc, result):
        assert rc == 0
        Parent.load(on_load, ID, cursor=db.cursor)

    def on_insert(rc, result):
        assert rc == 0
        result.delete(on_delete, cursor=db.cursor)

    p = Parent(foo=123)
    p.insert(on_insert, id=ID, cursor=db.cursor)

    db.run()

    assert test['is_loaded']
