'''
The MIT License (MIT)

Copyright (c) 2013-2015 Robert H Chase

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
'''
import spindrift.mysql.connection as connection


class _DB(object):

    def __init__(self):
        self.context = None

    def setup(
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
        )

    @property
    def connection(self):
        if self.context is None:
            raise Exception('database connection is not configured')
        return self.network.add_connection(
            self.host,
            self.port,
            self.context.handler,
            context=self.context,
        )

    @property
    def cursor(self):
        return self.connection.cursor


DB = _DB()
