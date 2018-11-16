import pytest

import test_db.models as models


@pytest.fixture
def data(sync):
    root = models.Root(foo=1, bar=2).save(sync)
    models.Node(root=root, name=models.NODE1).save(sync)
    models.Node(root=root, name=models.NODE2).save(sync)


def test_table(data, sync):
    result = models.Root.query().add(models.Node)
    assert result
