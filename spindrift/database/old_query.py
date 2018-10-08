'''
The MIT License (MIT)

https://github.com/robertchase/spindrift/blob/master/LICENSE.txt
'''


class Query(object):

    def __init__(self, table_class):
        self._classes = [table_class]
        self._count = [
            len(table_class.FIELDS) + len(table_class.CALCULATED_FIELDS)
        ]
        self._join = table_class.FULL_TABLE_NAME()

        self._columns = [
            '%s.`%s`' % (table_class.FULL_TABLE_NAME(), c)
            for c in table_class.FIELDS
        ]
        self._columns.extend(
            '%s AS %s' % (c, n)
            for n, c in table_class.CALCULATED_FIELDS.items()
        )

        self._where = None
        self._order = None

    def where(self, where=None):
        self._where = where
        return self

    def order(self, order):
        self._order = order
        return self

    def by_id(self):
        self.where('%s.`id`=%%s' % self._classes[0].FULL_TABLE_NAME())
        return self

    def join(self, table1, column1=None, table2=None, column2='id', outer=False):
        ''' add a table to the query

        Parameters:
            table_1 - DAO class of the table to add to the query
            column1 - join column on table1, default = table2.name + '_id'
            table2 - DAO class of existing table to join
                     default is most recently added to query
            column2 - join column of table2, default = 'id'
            outer - OUTER join indicator
                    if True or 'LEFT' then LEFT OUTER JOIN
                    if 'RIGHT' then RIGHT OUTER JOIN
                    default = False

        Hint: joining from parent to children is the default direction
        '''
        if not table2:
            table2 = self._classes[-1]
        if not column1:
            column1 = '%s_id' % table2.TABLE
        self._classes.append(table1)
        self._count.append(len(table1.FIELDS) + len(table1.CALCULATED_FIELDS))
        if outer:
            direction = 'LEFT' if outer is True else outer
            self._join += ' %s OUTER' % direction
        self._join += ' JOIN %s ON %s.`%s` = %s.`%s`' % (
            table1.FULL_TABLE_NAME(),
            table1.FULL_TABLE_NAME(),
            column1,
            table2.FULL_TABLE_NAME(),
            column2
        )

        self._columns.extend('%s.`%s`' % (
            table1.FULL_TABLE_NAME(), c)
            for c in table1.FIELDS
        )
        self._columns.extend(
            '%s AS %s' % (c, n)
            for n, c in table1.CALCULATED_FIELDS.items()
        )

        return self

    def _build(self, one, limit, offset, for_update):
        if one and limit:
            raise Exception('one and limit parameters are mutually exclusive')
        if one:
            limit = 1
        stmt = 'SELECT '
        stmt += ','.join(self._columns)
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
        self._stmt = self._build(one, limit, offset, for_update)
        self._executed_stmt = None
        if before_execute:
            before_execute(self)

        def on_execute(rc, result):
            if rc != 0:
                return callback(rc, result)

            columns, values = result
            self._executed_stmt = cursor._executed
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
                        tables[c.TABLE] = o
                rows.append(primary_table)

            if one:
                rows = rows[0] if len(rows) else None
            callback(0, rows)

        cursor.execute(on_execute, self._stmt, arg)
