'''
The MIT License (MIT)

https://github.com/robertchase/spindrift/blob/master/LICENSE.txt
'''


class Cursor(object):

    def __init__(self, protocol):
        self.protocol = protocol

        self._transaction_depth = 0
        self._start_transaction = False
        self._transaction_commit = False
        self._transaction_rollback = False

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

    def start_transaction(self):
        self._transaction_depth += 1
        if self._transaction_depth == 1:
            self._start_transaction = True
        return self

    def commit(self):
        if not self.commit_enabled:
            return self
        if self._transaction_depth == 0:
            return self
        self._transaction_depth -= 1
        if self._transaction_depth == 0:
            self._transaction_commit = True
        return self

    def rollback(self):
        if self._transaction_depth == 0:
            return
        self._transaction_depth = 0
        self._transaction_rollback = True
        return self

    def transaction(self):
        return self.start_transaction().commit()

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

    def select(self, *args, **kwargs):
        """Run an arbitrary SELECT statment

           select(callback, query, args)

               callback - callback taking (rc, result)
               query    - select statement
               args     - substitution parameters for select

           result - list of result objects where each column
                    is available as an attribute of an object

           Notes:
               1. result object attribute names are the
                  name assigned by 'AS' or the column name.
               2. if the databse connection is operating in
                  sync mode, then the callback parameter is not
                  supplied.
        """
        if hasattr(self, '_run_sync'):
            return self._run_sync(
                self._select, *args, **kwargs
            )
        self._select(*args, **kwargs)

    def _select(self, callback, query, args=None):

        class Record:
            def __init__(self, **kwargs):
                self.__init__.update(kwargs)

        self.execute(callback, query, args, cls=Record)

    def execute(self, callback, query, args=None,
                start_transaction=False, commit=False, cls=None):
        """ Execute a query """
        self._before_executed = query
        if args is not None:
            query = query % self._escape_args(args)
        self._executed = query

        if start_transaction:
            self.start_transaction()
        if commit:
            self.commit()

        if self._start_transaction:
            self._start_transaction = False
            start = True
        else:
            start = False

        if self._transaction_commit:
            self._transaction_commit = False
            end = 'COMMIT'
        elif self._transaction_rollback:
            self._transaction_rollback = False
            end = 'ROLLBACK'
        else:
            end = None

        def _callback(rc, result):
            self.is_running = False
            callback(rc, result)

        self.is_running = True
        self.protocol.query(
            _callback, query, cls=cls,
            start_transaction=start, end_transaction=end
        )
