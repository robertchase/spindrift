class Cursor(object):

    def __init__(self, protocol):
        self.protocol = protocol

        self._transaction_depth = 0
        self._start_transaction = False
        self._transaction_commit = False
        self._transaction_rollback = False

    def close(self):
        self.protocol.close()

    @property
    def is_open(self):
        return self.protocol.is_open

    def start_transaction(self):
        self._transaction_depth += 1
        if self._transaction_depth == 1:
            self._start_transaction = True
        return self

    def commit(self):
        if self._transaction_depth == 0:
            return
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
            return dict((key, self.protocol.escape(val)) for (key, val) in args.items())
        else:
            return self.protocol.escape(args)

    def execute(self, callback, query, args=None, start_transaction=False, commit=False, cls=None):
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

        self.protocol.query(callback, query, cls=cls, start_transaction=start, end_transaction=end)
