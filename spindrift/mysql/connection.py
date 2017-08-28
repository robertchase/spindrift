from spindrift.mysql.cursor import Cursor
from spindrift.mysql.protocol import Protocol
import spindrift.network as network


mod = {'_CONNECTIONCOUNT': 0}


class MysqlHandler(network.Handler):

    def on_init(self):
        self._protocol = Protocol(self)
        self._cursor = Cursor(self._protocol)
        self.id = mod['_CONNECTIONCOUNT'] = mod['_CONNECTIONCOUNT'] + 1

    @property
    def cursor(self):
        return self._cursor

    @property
    def user(self):
        return self.context.user

    @property
    def db(self):
        return self.context.db

    @property
    def pswd(self):
        return self.context.pswd

    def on_connected(self):
        pass

    def on_data(self, data):
        self._protocol.handle(data)

    def on_query_start(self, query):
        pass

    def on_query_end(self):
        pass


class MysqlContext(object):

    def __init__(self, user=None, pswd=None, db=None, host=None, port=3306,
                 column=False,          # return result as tuple of (column_names, result_set)
                 table=False,           # prepend 'table_name.' to column_names
                 fsm_trace=None,        # trace FSM events fn(state, event, is_default, is_internal)
                 sql_trace=None,        # trace sql commands fn(sql)
                 autocommit=False,      # autocommit (True/False)
                 isolation=None,        # session isolation level
                 handler=MysqlHandler,  # handler for mysql connection
                 ):
        self.user = user
        self.pswd = '' if pswd is None else pswd
        self.db = db
        self.column = column
        self.table = table
        self.fsm_trace = fsm_trace
        self.sql_trace = sql_trace
        self.autocommit = autocommit
        self.isolation = isolation
        self.handler = handler
