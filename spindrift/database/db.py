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
                autocommit=True,   # autocommit (True/False)
                isolation=None,    # session isolation level ("read committed", etc)
                handler=None,      # alternate handler for mysql connection
                                   # spindrift.mysq.connection.MysqlHandler
                commit=True,       # False to disallow COMMIT
                                   #   (turns off autocommit)
                sync=False,        # operate in synchronous mode
            ):
        self.network = network if network else Network()
        self.host = host
        self.port = port
        self.is_sync = sync
        if commit is False:
            autocommit = False
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
        for n in range(10):  # wait for connection to complete
            if connection.is_ready:
                break
            self.network.service()
        if not connection.is_ready:
            raise Exception('could not connect to database')

        cursor = connection.cursor
        cursor._run_sync = run_sync
        return cursor
