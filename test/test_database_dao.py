import pytest

from spindrift.database.dao import DAO
from spindrift.database.field import Field, coerce_int


@pytest.fixture
def Structure():
    class Structure(DAO):
        TABLENAME = 'test'
        the_key = Field(coerce_int, is_primary=True)
        name = Field()
        age = Field(coerce_int, is_nullable=True)
        random = Field(default='foo', is_database=False)
    return Structure


@pytest.fixture
def data(Structure):
    return Structure()


def test_basic(data):
    assert data


def test_pk(data):
    pk = data._fields.pk
    assert pk == 'the_key'


def test_is_nullable(data):
    with pytest.raises(TypeError):
        data.name = None


def test_db_read(data):
    db = data._fields.db_read
    assert isinstance(db, list)
    assert len(db) == 3
    assert set(fld.name for fld in db) == set(('the_key', 'name', 'age'))


def test_db_insert(data):
    db = data._fields.db_insert
    assert isinstance(db, list)
    assert len(db) == 3
    assert set(fld.name for fld in db) == set(('the_key', 'name', 'age'))


def test_db_update(data):
    db = data._fields.db_update
    assert isinstance(db, list)
    assert len(db) == 2
    assert set(fld.name for fld in db) == set(('name', 'age'))


def test_init(Structure):
    e = Structure(name='Fred', age=100, random='yeah')
    assert e
    assert e.name == 'Fred'
    assert e.age == 100
    assert e.random == 'yeah'


def test_init_invalid(Structure):
    with pytest.raises(AttributeError):
        Structure(foo=1)


def test_default(data):
    assert data.random == 'foo'
