import pytest

from spindrift.database.dao import DAO
from spindrift.database.field import Field, Children


NODE1 = 'fred'
NODE2 = 'sally'


class Root(DAO):

    TABLENAME = 'parent'

    id = Field(int, is_primary=True)
    foo = Field(int, default=0)
    bar = Field(int, is_nullable=True)
    foo_bar = Field(expression='`{}`.foo + `{}`.bar'.format(
        TABLENAME, TABLENAME
    ))

    nodes = Children('test_db.test_query.Node')


class Node(DAO):

    TABLENAME = 'child'

    id = Field(int, is_primary=True)
    parent_id = Field(int, foreign='test_db.test_query.Root')
    name = Field(str)

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
        Node(parent_id=result.parent_id, name=NODE2).save(
            on_child2, cursor=db.cursor)

    def on_parent(rc, result):
        assert rc == 0
        Node(root=result, name=NODE1).save(on_child1, cursor=db.cursor)

    Root(foo=1, bar=2).save(on_parent, cursor=db.cursor)
    db.run()


def test_simple(data, db):

    def on_child(rc, result):
        assert rc == 0
        assert result is not None
        db.is_done = True

    Node.by_name(on_child, NODE1, db.cursor)
    db.run()


def test_list_all(data, db):

    def on_list(rc, result):
        assert rc == 0
        names = set([r.name for r in result])
        assert set((NODE1, NODE2)) == names
        db.is_done = True

    Node.list(on_list, cursor=db.cursor)
    db.run()


def test_list_where(data, db):

    def on_list(rc, result):
        assert rc == 0
        assert len(result) == 1
        assert result[0].name == NODE1
        db.is_done = True

    Node.list(on_list, where='name=%s', args=NODE1, cursor=db.cursor)
    db.run()


def test_count_all(data, db):

    def on_count(rc, result):
        assert rc == 0
        assert result == 2
        db.is_done = True

    Node.count(on_count, cursor=db.cursor)
    db.run()


def test_join(data, db):

    def on_join(rc, result):
        assert rc == 0
        assert len(result) == 2
        names = set([p.child.name for p in result])
        assert set((NODE1, NODE2)) == names
        db.is_done = True

    Root.query().join(Node, 'parent_id', Root, 'id').execute(
        on_join, cursor=db.cursor)
    db.run()


def test_children(data, db):

    def on_children(rc, result):
        assert rc == 0
        assert len(result) == 2
        names = set([c.name for c in result])
        assert set((NODE1, NODE2)) == names
        db.is_done = True

    def on_parent(rc, result):
        assert rc == 0
        result.nodes(on_children, cursor=db.cursor)

    Root.query().execute(on_parent, one=True, cursor=db.cursor)
    db.run()


def test_foreign(data, db):

    def on_parent(rc, result):
        assert rc == 0
        assert result is not None
        db.is_done = True

    def on_child(rc, result):
        assert rc == 0
        result.root(on_parent, cursor=db.cursor)

    Node.query().execute(on_child, one=True, cursor=db.cursor)
    db.run()
