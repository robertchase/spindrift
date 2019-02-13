from spindrift.database.dao import DAO
from spindrift.database.field import Field, Children


NODE1 = 'fred'
NODE2 = 'sally'


class Root(DAO):

    TABLENAME = 'parent'

    id = Field(int, is_primary=True)
    foo = Field(int, default=0)
    bar = Field(int, is_nullable=True)
    foo_bar = Field(expression='{table}.`foo` + {table}.`bar`')

    nodes = Children('test_db.models.Node')


class Node(DAO):

    TABLENAME = 'child'

    id = Field(int, is_primary=True)
    parent_id = Field(int, foreign='test_db.models.Root')
    name = Field(str)

    @classmethod
    def by_name(cls, callback, name, cursor=None):
        return cls.query.where('name=%s').execute(
            callback, name, one=True, cursor=cursor
        )


class OddKeysRoot(DAO):

    TABLENAME = 'odd_keys_root'

    my_key = Field(int, is_primary=True)
    name = Field()

    odd_nodes = Children('test_db.models.OddKeysNode')


class OddKeysNode(DAO):

    TABLENAME = 'odd_keys_node'

    and_my_key = Field(int, is_primary=True)
    odd_keys_root_id = Field(int, foreign='test_db.models.OddKeysRoot')
    name = Field()
