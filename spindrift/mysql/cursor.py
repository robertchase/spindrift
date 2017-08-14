class Cursor(object):

    def __init__(self, protocol):
        self.protocol = protocol

    def close(self):
        self.protocol = None

    def _escape_args(self, args):
        if isinstance(args, (tuple, list)):
            return tuple(self.protocol.escape(arg) for arg in args)
        elif isinstance(args, dict):
            return dict((key, self.protocol.escape(val)) for (key, val) in args.items())
        else:
            return self.protocol.escape(args)

    def execute(self, callback, query, args=None, cls=None):
        """Execute a query

        :param str query: Query to execute.

        :param args: parameters used with query. (optional)
        :type args: tuple, list or dict

        :param cls: class to instantiate with each query row

        If args is a list or tuple, %s can be used as a placeholder in the query.
        If args is a dict, %(name)s can be used as a placeholder in the query.
        """
        self._before_executed = query
        if args is not None:
            query = query % self._escape_args(args)
        self._executed = query

        self.protocol.query(callback, query, cls)
