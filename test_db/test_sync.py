import pytest

import test_db.models as models


@pytest.fixture
def data(sync):
    root = models.Root(foo=1, bar=2).save(sync)
    models.Node(root=root, name=models.NODE1).save(sync)
    models.Node(root=root, name=models.NODE2).save(sync)


def test_simple(data, sync):
    result = models.Node.by_name(sync, models.NODE1)
    assert isinstance(result, models.Node)
    assert result.name == models.NODE1


def test_list_all(data, sync):
    result = models.Node.list(sync)
    assert result
    names = set([r.name for r in result])
    assert set((models.NODE1, models.NODE2)) == names


def test_list_where(data, sync):
    result = models.Node.list(sync, where='name=%s', args=models.NODE1)
    assert result
    assert len(result) == 1
    assert result[0].name == models.NODE1


def test_count_all(data, sync):
    result = models.Node.count(sync)
    assert result
    assert result == 2


def test_join(data, sync):
    result = models.Root.query().join(
        models.Node, 'parent_id', models.Root, 'id').execute(sync)
    assert result
    assert len(result) == 2
    names = set([p.child.name for p in result])
    assert set((models.NODE1, models.NODE2)) == names


def test_children(data, sync):
    result = models.Root.query().execute(sync, one=True)
    assert result
    child = result.nodes(sync)
    assert child
    assert len(child) == 2
    names = set([c.name for c in child])
    assert set((models.NODE1, models.NODE2)) == names


def test_foreign(data, sync):
    result = models.Node.query().execute(sync, one=True)
    assert result
    parent = result.root(sync)
    assert parent


def test_select(data, sync):
    cols, rows = models.Node.select(
        sync, 'select * from child'
    )
    assert len(cols) == 5
    assert len(rows) == 2
    names = [row.name for row in rows]
    assert set(names) == set((models.NODE1, models.NODE2))
