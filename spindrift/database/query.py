'''
The MIT License (MIT)

https://github.com/robertchase/spindrift/blob/master/LICENSE.txt
'''


class Query(object):

    def __init__(self, table):
        self._classes = [table]
        self._columns = table._fields.db_read.copy()
        self._count = [len(self._columns)]
        self._join = '`' + table.TABLENAME + '`'

        self._where = None
        self._order = None

    def where(self, where=None):
        self._where = where
        return self

    def order(self, order):
        self._order = order
        return self

    def by_pk(self):
        cls = self._classes[0]
        self.where('`{}`.`{}`=%s'.format(cls.TABLENAME, cls._fields.pk))
        return self

    def join(self, table, field, join_table, join_field, outer=None):
        """Add a table to the query (equi join)

            Parameters:
                table      - DAO of the table to add to the query
                field      - name of join field in table
                join_table - DAO of table to join
                join_field - name of join field in join_table
                outer      - OUTER join indicator
                             LEFT or RIGHT

            Example:
                User.query().join(Address, 'user_id', User, 'id')
        """
        self._classes.append(table)
        flds = table._fields.db_read
        self._columns.extend(flds)
        self._count.append(len(flds))

        if outer is None:
            join = ' JOIN '
        elif outer.lower() == 'right':
            join = ' RIGHT OUTER JOIN '
        elif outer.lower() == 'left':
            join = ' LEFT OUTER JOIN '
        else:
            raise ValueError("invalid outer join value: '{}'".format(outer))

        self._join += '{} `{}` ON {} = {}'.format(
            join, table.TABLENAME,
            table._fields[field].fullname,
            join_table._fields[join_field].fullname,
        )

        return self

    def _build(self, one, limit, offset, for_update):
        if one and limit:
            raise Exception('one and limit parameters are mutually exclusive')
        if one:
            limit = 1

        stmt = 'SELECT '
        stmt += ','.join(fld.as_select for fld in self._columns)
        stmt += ' FROM ' + self._join
        if self._where:
            stmt += ' WHERE ' + self._where
        if self._order:
            stmt += ' ORDER BY ' + self._order
        if limit:
            stmt += ' LIMIT %d' % int(limit)
        if offset:
            stmt += ' OFFSET %d' % int(offset)
        if for_update:
            stmt += ' FOR UPDATE'
        return stmt

    def execute(self, callback, arg=None,
                one=False, limit=None, offset=None, for_update=False,
                before_execute=None, after_execute=None,
                cursor=None):
        if not cursor:
            raise Exception('cursor not specified')
        stmt = self._build(one, limit, offset, for_update)
        if before_execute:
            before_execute(self)

        def on_execute(rc, result):
            if rc != 0:
                return callback(rc, result)

            columns, values = result
            if after_execute:
                after_execute(self)
            rows = []
            for rs in values:
                tables = None
                row = [t for t in zip(columns, rs)]
                for c, count in zip(self._classes, self._count):
                    val, row = row[:count], row[count:]
                    o = c(**dict(val))
                    if tables is None:
                        primary_table = o
                        o._tables = tables = {}
                    else:
                        tables[c.TABLENAME] = o
                rows.append(primary_table)

            if one:
                rows = rows[0] if len(rows) else None
            callback(0, rows)

        cursor.execute(on_execute, stmt, arg)
