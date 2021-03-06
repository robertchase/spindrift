'''
The MIT License (MIT)

https://github.com/robertchase/spindrift/blob/master/LICENSE.txt
'''
from spindrift.mysql.cursor import Cursor
from spindrift.mysql.protocol import Protocol
import spindrift.network as network


class MysqlHandler(network.Handler):

    def on_init(self):
        self._protocol = Protocol(self)
        self._cursor = Cursor(self._protocol)
        self.is_ready = False

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

    @property
    def raw_query(self):
        return self.cursor.statement_before

    def on_close(self, reason):
        self._cursor.close()

    def on_connected(self):
        pass

    def on_data(self, data):
        self._protocol.handle(data)

    def on_transaction_start(self):
        pass

    def on_transaction_end(self, end_type):
        pass

    def on_query_start(self):
        pass

    def on_query_end(self):
        pass


class MysqlContext(object):

    def __init__(self, user=None, pswd=None, db=None, host=None, port=3306,
                 column=False,          # return result as tuple of
                                        #   (column_names, result_sets)
                 table=False,           # prepend 'table_name.' to column_names
                 fsm_trace=None,        # trace FSM events fn(state, event,
                                        #   is_default, is_internal)
                 sql_trace=None,        # trace sql commands fn(stmt)
                 autocommit=False,      # autocommit (True/False)
                 isolation=None,        # session isolation level
                 handler=MysqlHandler,  # handler for mysql connection
                 commit=True,           # if False, don't COMMIT (useful for
                                        #   testing)
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
        self.commit_enabled = commit
