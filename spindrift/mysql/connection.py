import time

from spindrift.mysql.cursor import Cursor
from spindrift.mysql.protocol import Protocol
import spindrift.network as network


class MysqlContext(object):

    def __init__(self, user=None, pswd=None, db=None, host=None, port=3306,
                 names=False,  # return result as tuple of (column_names, result_set)
                 trace=False   # trace FSM to stdout
                 ):
        self.user = user
        self.pswd = '' if pswd is None else pswd
        self.db = db
        self.host = host
        self.port = port
        self.names = names
        self.trace = self.trace if trace else None

    @staticmethod
    def trace(s, e, d, i):
        print('s=%s,e=%s,is_default=%s,is_internal=%s' % (s, e, d, i))


class MysqlHandler(network.Handler):

    def on_init(self):
        self.protocol = Protocol(self)
        self._cursor = Cursor(self.protocol)

    def cursor(self):
        return self._cursor

    def on_close(self, reason):
        print(300, 'close', reason)

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
        print('connected, t=%s' % (time.perf_counter() - self.t_init))

    def on_data(self, data):
        self.protocol.handle(data)
