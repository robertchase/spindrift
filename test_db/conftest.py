import pytest

from spindrift.database.db import DB
from spindrift.network import Network


@pytest.fixture
def network():
    n = Network()
    yield n
    n.close()


def fsm_trace(state, event, is_default, is_internal):
    print('fsm_trace', state, event)


def sql_trace(stmt):
    print('sql_trace', stmt)


@pytest.fixture
def db_cursor(network):
    db = DB(
        network,
        user='test',
        db='spindrift',
        host='mysql',
        # fsm_trace=fsm_trace,
        # sql_trace=sql_trace,
        commit=False,
    )
    cursor = db.cursor
    return cursor


@pytest.fixture
def db(db_cursor, network):

    class _db(object):

        def __init__(self):
            self.is_done = False

        @property
        def cursor(self):
            return db_cursor

        def run(self):
            while db_cursor.is_running:
                network.service()

    d = _db()
    yield d
    assert d.is_done  # set is_done at last step of test (ensures full test)
