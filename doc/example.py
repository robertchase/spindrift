from spindrift.database.dao import DAO
from spindrift.database.db import DB
from spindrift.database.field import Field


db = DB(user='test', db='spindrift', host='mysql', commit=False, sync=True)
cursor = db.cursor


class Root(DAO):

    TABLENAME = 'root'

    id = Field(int, is_primary=True)
    name = Field(str)
    color = Field(('red', 'blue', 'yellow'), is_nullable=True)


class Node(DAO):

    TABLENAME = 'node'

    id = Field(int, is_primary=True)
    root_id = Field(int, foreign=Root)
    name = Field(str)
