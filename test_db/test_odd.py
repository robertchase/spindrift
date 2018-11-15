import pytest

import test_db.models as models


ROOTNAME = 'whatever'


@pytest.fixture
def data(sync):
    root = models.OddKeysRoot(name=ROOTNAME).save(sync)
    models.OddKeysNode(oddkeysroot=root, name=models.NODE1).save(sync)
    models.OddKeysNode(oddkeysroot=root, name=models.NODE2).save(sync)


def test_simple(data, sync):
    result = models.OddKeysRoot.list(sync)[0]
    assert isinstance(result, models.OddKeysRoot)
    assert result.name == ROOTNAME


def test_list_nodes(data, sync):
    result = models.OddKeysNode.list(sync)
    assert result
    names = set([r.name for r in result])
    assert set((models.NODE1, models.NODE2)) == names


def test_load(data, sync):
    root = models.OddKeysRoot.list(sync)[0]
    result = models.OddKeysRoot.load(sync, root.my_key)
    assert result
    assert result.name == ROOTNAME


def test_insert(data, sync):
    key = models.OddKeysRoot.list(sync)[0].my_key * 2
    root = models.OddKeysRoot(name=ROOTNAME)
    result = root.insert(sync, key)
    assert result
    assert result.name == ROOTNAME


def test_update(data, sync):
    root = models.OddKeysRoot.list(sync)[0]
    root.name = ROOTNAME + ROOTNAME
    root.save(sync)
    result = root.load(sync, root.my_key)
    assert result
    assert result.name == ROOTNAME + ROOTNAME


def test_children(data, sync):
    result = models.OddKeysRoot.query().execute(sync, one=True)
    assert result
    child = result.odd_nodes(sync)
    assert child
    assert len(child) == 2
    names = set([c.name for c in child])
    assert set((models.NODE1, models.NODE2)) == names


def test_foreign(data, sync):
    result = models.OddKeysNode.query().execute(sync, one=True)
    assert result
    parent = result.oddkeysroot(sync)
    assert parent
