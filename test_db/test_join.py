import pytest

from spindrift.database.query import Query

import test_db.models as models


@pytest.fixture
def data(sync):
    root = models.Root(foo=1, bar=2).save(sync)
    models.Node(root=root, name=models.NODE1).save(sync)
    models.Node(root=root, name=models.NODE2).save(sync)


def test_table_only():
    table, field, table2, field2 = Query(models.Root)._normalize(
        models.Node, None)
    assert field == 'parent_id'
    assert table2.cls == models.Root
    assert field2 == 'id'


def test_table_and_field_only():
    table, field, table2, field2 = Query(models.Root)._normalize(
        models.Node, 'parent_id', None, None)
    assert table2.cls == models.Root
    assert field2 == 'id'


def test_non_dao_table():
    with pytest.raises(TypeError):
        models.Root.query._normalize('foo', None, None, None)


def test_no_foreign_keys():
    with pytest.raises(TypeError):
        models.Root.query._normalize(models.Root, None, None, None)


def test_no_matching_foreign_keys():
    with pytest.raises(TypeError):
        models.Root.query._normalize(models.OddKeysNode, None, None, None)


def test_missing_non_foreign_table2(data, sync):
    with pytest.raises(ValueError):
        models.Root.query._normalize(models.Node, 'name', None, None)


def test_non_dao_table_with_field(data, sync):
    with pytest.raises(TypeError):
        models.Root.query._normalize('blah', 'name', None, None)


def test_root_node(data, sync):
    result = models.Root.query.join(models.Node).execute(sync)
    assert result
    assert len(result) == 2
    r = result[0]
    n = r.node
    assert isinstance(n, models.Node)


def test_root_node_path(data, sync):
    result = models.Root.query.join('test_db.models.Node').execute(sync)
    assert result
    assert len(result) == 2
    r = result[0]
    n = r.node
    assert isinstance(n, models.Node)


def test_node_root(data, sync):
    result = models.Node.query.join(models.Root).execute(sync)
    assert result
    assert len(result) == 2
    r = result[0]
    n = r.node
    assert isinstance(n, models.Node)


def test_table2(data, sync):
    result = models.Node.query.join(models.Root, models.Node).execute(sync)
    assert result
    assert len(result) == 2
    n = result[0]
    r = n.root
    assert isinstance(n, models.Node)
    assert isinstance(r, models.Root)


def test_alias(data, sync):
    result = models.Root.query.join(models.Node, alias='akk').execute(sync)
    assert result
    assert len(result) == 2
    r = result[0]
    n = r.akk
    assert isinstance(n, models.Node)
