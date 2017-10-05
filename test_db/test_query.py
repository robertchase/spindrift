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

    Child.by_name(on_child, CHILD1, db.cursor)
    db.run()


def test_list_all(data, db):

    def on_list(rc, result):
        assert rc == 0
        names = set([r.name for r in result])
        assert set((CHILD1, CHILD2)) == names

    Child.list(on_list, cursor=db.cursor)
    db.run()


def test_list_where(data, db):

    def on_list(rc, result):
        assert rc == 0
        assert len(result) == 1
        assert result[0].name == CHILD1

    Child.list(on_list, where='name=%s', args=CHILD1, cursor=db.cursor)
    db.run()


def test_count_all(data, db):

    def on_count(rc, result):
        assert rc == 0
        assert result == 2

    Child.count(on_count, cursor=db.cursor)
    db.run()


'''
def test_children(data):
    p = next(Parent.list())
    c = p.children(Child)
    assert len(c) == 2


def test_children_by_property(data):
    p = next(Parent.list())
    c = p.child
    assert len(c) == 2


def test_join(data):
    rs = Parent.query().join(Child).execute()
    assert len(rs) == 2
    names = [p.child.name for p in rs]
    assert len(names) == 2
    assert 'fred' in names
    assert 'sally' in names
'''
