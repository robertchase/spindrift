'''
The MIT License (MIT)

https://github.com/robertchase/spindrift/blob/master/LICENSE.txt
'''
import spindrift.mysql.connection as connection
from spindrift.network import Network


class DB(object):

    def __init__(
                self,
                network=None,
                user=None,
                pswd=None,
                db=None,
                host=None,
                port=3306,
                fsm_trace=None,    # callback for fsm events
                sql_trace=None,    # callback for sql commands
                autocommit=False,  # autocommit (True/False)
                isolation=None,    # session isolation level ("read committed", etc)
                handler=None,      # alternate handler for mysql connection
                                   # spindrift.mysq.connection.MysqlHandler
                commit=True,       # False to disallow COMMIT
                sync=False,        # operate in synchronous mode
            ):
        self.network = network if network else Network()
        self.host = host
        self.port = port
        self.is_sync = sync
        self.context = connection.MysqlContext(
            user=user,
            pswd=pswd,
            db=db,
            sql_trace=sql_trace,
            fsm_trace=fsm_trace,
            autocommit=autocommit,
            isolation=isolation,
            handler=handler or connection.MysqlHandler,
            commit=commit,
            column=True,
        )

    @property
    def connection(self):
        return self.network.add_connection(
            self.host,
            self.port,
            self.context.handler,
            context=self.context,
        )


    @property
    def cursor(self):
        if not self.is_sync:
            return self.connection.cursor

        def run_sync(fn, *args, **kwargs):
            async = None

            def cb(rc, result):
                nonlocal async
                if rc != 0:
                    raise Exception(result)
                async = result

            fn(cb, *args, **kwargs)
            cursor = kwargs.get('cursor')
            while cursor.is_running:
                self.network.service()
            return async

        connection = self.connection
        while not connection.is_ready:  # finish mysql handshake
            self.network.service()
        cursor = connection.cursor
        cursor._run_sync = run_sync
        return cursor
