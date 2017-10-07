import pytest

from spindrift.dao.dao import DAO


CHILD1 = 'fred'
CHILD2 = 'sally'


class Parent(DAO):

    TABLE = 'parent'

    FIELDS = (
        'id',
        'foo',
        'bar',
    )

    DEFAULT = dict(
        foo=0,
    )

    CALCULATED_FIELDS = dict(
        foo_bar='%s.foo + %s.bar' % (TABLE, TABLE),
    )

    CHILDREN = dict(
        child='test_db.test_query.Child',
    )


class Child(DAO):

    TABLE = 'child'

    FIELDS = (
        'id',
        'parent_id',
        'name',
    )

    FOREIGN = dict(
        parent='test_db.test_query.Parent',
    )

    @classmethod
    def by_name(cls, callback, name, cursor):
        return cls.query().where('name=%s').execute(
            callback, name, one=True, cursor=cursor
        )


@pytest.fixture
def data(db):

    def on_child2(rc, result):
        assert rc == 0

    def on_child1(rc, result):
        assert rc == 0
        Child(parent_id=result.parent_id, name=CHILD2).save(on_child2, cursor=db.cursor)

    def on_parent(rc, result):
        assert rc == 0
        Child(parent=result, name=CHILD1).save(on_child1, cursor=db.cursor)

    Parent(foo=1, bar=2).save(on_parent, cursor=db.cursor)
    db.run()


def test_simple(data, db):

    def on_child(rc, result):
        assert rc == 0
        assert result is not None
        db.is_done = True

    Child.by_name(on_child, CHILD1, db.cursor)
    db.run()


def test_list_all(data, db):

    def on_list(rc, result):
        assert rc == 0
        names = set([r.name for r in result])
        assert set((CHILD1, CHILD2)) == names
        db.is_done = True

    Child.list(on_list, cursor=db.cursor)
    db.run()


def test_list_where(data, db):

    def on_list(rc, result):
        assert rc == 0
        assert len(result) == 1
        assert result[0].name == CHILD1
        db.is_done = True

    Child.list(on_list, where='name=%s', args=CHILD1, cursor=db.cursor)
    db.run()


def test_count_all(data, db):

    def on_count(rc, result):
        assert rc == 0
        assert result == 2
        db.is_done = True

    Child.count(on_count, cursor=db.cursor)
    db.run()


def test_join(data, db):

    def on_join(rc, result):
        assert rc == 0
        assert len(result) == 2
        names = set([p.child.name for p in result])
        assert set((CHILD1, CHILD2)) == names
        db.is_done = True

    Parent.query().join(Child).execute(on_join, cursor=db.cursor)
    db.run()


def test_children(data, db):

    def on_children(rc, result):
        assert rc == 0
        assert len(result) == 2
        names = set([c.name for c in result])
        assert set((CHILD1, CHILD2)) == names
        db.is_done = True

    def on_parent(rc, result):
        assert rc == 0
        result.children(on_children, Child, cursor=db.cursor)

    Parent.query().execute(on_parent, one=True, cursor=db.cursor)
    db.run()


def test_foreign(data, db):

    def on_parent(rc, result):
        assert rc == 0
        assert result is not None
        db.is_done = True

    def on_child(rc, result):
        assert rc == 0
        result.foreign(on_parent, Parent, cursor=db.cursor)

    Child.query().execute(on_child, one=True, cursor=db.cursor)
    db.run()
