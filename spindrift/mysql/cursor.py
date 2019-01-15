'''
The MIT License (MIT)

https://github.com/robertchase/spindrift/blob/master/LICENSE.txt
'''


class Cursor(object):

    def __init__(self, protocol):
        self.protocol = protocol

        self._transaction_depth = 0

        self.is_running = False

    def __setattr__(self, name, value):
        if name == 'cid':
            self.protocol.connection.cid = value
        else:
            super(Cursor, self).__setattr__(name, value)

    def close(self):
        self.protocol.close()

    @property
    def is_open(self):
        return self.protocol.is_open

    @property
    def commit_enabled(self):
        return self.protocol.context.commit_enabled

    def _transaction(self, callback, command):
        if not self.commit_enabled:
            return callback(0, None)
        self.execute(callback, command)

    def start_transaction(self, callback=None, **kwargs):
        if not callback:
            if hasattr(self, '_run_sync'):
                return self._run_sync(
                    self.start_transaction, cursor=self,
                )
            raise Exception('callback not specified')
        self._transaction_depth += 1
        if self._transaction_depth != 1:
            return callback(0, None)
        self._transaction(callback, 'START TRANSACTION')

    def commit(self, callback=None, **kwargs):
        if not callback:
            if hasattr(self, '_run_sync'):
                return self._run_sync(
                    self.commit, cursor=self,
                )
            raise Exception('callback not specified')
        if self._transaction_depth == 0:
            return callback(0, None)
        self._transaction_depth -= 1
        if self._transaction_depth != 0:
            return callback(0, None)
        self._transaction(callback, 'COMMIT')

    def rollback(self, callback=None, **kwargs):
        if not callback:
            if hasattr(self, '_run_sync'):
                return self._run_sync(
                    self.rollback, cursor=self,
                )
            raise Exception('callback not specified')
        if self._transaction_depth == 0:
            return callback(0, None)
        self._transaction_depth = 0
        self._transaction(callback, 'ROLLBACK')

    @property
    def lastrowid(self):
        return self.protocol.lastrowid

    @property
    def rows_affected(self):
        return self.protocol.rows_affected

    def _escape_args(self, args):
        if isinstance(args, (tuple, list)):
            return tuple(self.protocol.escape(arg) for arg in args)
        elif isinstance(args, dict):
            return dict((key, self.protocol.escape(val))
                        for (key, val) in args.items())
        else:
            return self.protocol.escape(args)

    def execute(self, callback, query, args=None, cls=None):
        """ Execute a query """
        self.statement_before = query
        if args is not None:
            query = query % self._escape_args(args)
        self.statement = query

        def _callback(rc, result):
            self.is_running = False
            callback(rc, result)

        self.is_running = True
        self.protocol.query(_callback, query, cls=cls)
