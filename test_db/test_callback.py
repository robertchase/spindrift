import pytest

import test_db.models as models


@pytest.fixture
def data(db):

    def on_child2(rc, result):
        assert rc == 0

    def on_child1(rc, result):
        assert rc == 0
        models.Node(parent_id=result.parent_id, name=models.NODE2).save(
            on_child2, cursor=db.cursor)

    def on_parent(rc, result):
        assert rc == 0
        models.Node(root=result, name=models.NODE1).save(
            on_child1, cursor=db.cursor)

    models.Root(foo=1, bar=2).save(on_parent, cursor=db.cursor)
    db.run()


def test_simple(data, db):

    def on_child(rc, result):
        assert rc == 0
        assert result is not None
        db.is_done = True

    models.Node.by_name(on_child, models.NODE1, db.cursor)
    db.run()


def test_list_all(data, db):

    def on_list(rc, result):
        assert rc == 0
        names = set([r.name for r in result])
        assert set((models.NODE1, models.NODE2)) == names
        db.is_done = True

    models.Node.list(on_list, cursor=db.cursor)
    db.run()


def test_list_where(data, db):

    def on_list(rc, result):
        assert rc == 0
        assert len(result) == 1
        assert result[0].name == models.NODE1
        db.is_done = True

    models.Node.list(
        on_list, where='name=%s', args=models.NODE1, cursor=db.cursor)
    db.run()


def test_count_all(data, db):

    def on_count(rc, result):
        assert rc == 0
        assert result == 2
        db.is_done = True

    models.Node.count(on_count, cursor=db.cursor)
    db.run()


def test_join(data, db):

    def on_join(rc, result):
        assert rc == 0
        assert len(result) == 2
        names = set([r.node.name for r in result])
        assert set((models.NODE1, models.NODE2)) == names
        db.is_done = True

    models.Root.query.join(models.Node).execute(on_join, cursor=db.cursor)
    db.run()


def test_children(data, db):

    def on_children(rc, result):
        assert rc == 0
        assert len(result) == 2
        names = set([c.name for c in result])
        assert set((models.NODE1, models.NODE2)) == names
        db.is_done = True

    def on_parent(rc, result):
        assert rc == 0
        result.nodes(on_children, cursor=db.cursor)

    models.Root.query.execute(on_parent, one=True, cursor=db.cursor)
    db.run()


def test_foreign(data, db):

    def on_parent(rc, result):
        assert rc == 0
        assert result is not None
        db.is_done = True

    def on_child(rc, result):
        assert rc == 0
        result.root(on_parent, cursor=db.cursor)

    models.Node.query.execute(on_child, one=True, cursor=db.cursor)
    db.run()
