'''
The MIT License (MIT)

https://github.com/robertchase/spindrift/blob/master/LICENSE.txt
'''
import spindrift.mysql.connection as connection


class DB(object):

    def __init__(
                self,
                network,
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
            ):
        self.network = network
        self.host = host
        self.port = port
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
        return self.connection.cursor
