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
from spindrift.dao.db import DB


class Query(object):

    def __init__(self, table_class):
        self._classes = [table_class]
        self._join = table_class.FULL_TABLE_NAME()

        self._columns = ['%s.`%s`' % (table_class.FULL_TABLE_NAME(), c) for c in table_class.FIELDS]
        self._columns.extend('%s AS %s' % (c, n) for n, c in table_class.CALCULATED_FIELDS.items())

        self._column_names = [f for f in table_class.FIELDS]
        self._column_names.extend(table_class.CALCULATED_FIELDS.keys())

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

    def join(self, table_class1, column1=None, table_class2=None, column2='id', outer=False):
        ''' add a table to the query

        Parameters:
            table_class1 - DAO class of the table to add to the query
            column1 - join column on table1, default = table2.name + '_id'
            table_class2 - DAO class of existing table to join, default is most recently added to query
            column2 - join column of table2, default = 'id'
            outer - OUTER join indicator, if True or 'LEFT' then LEFT OUTER JOIN, if 'RIGHT' then RIGHT OUTER JOIN; default = False

        Hint: joining from parent to children is the default direction
        '''
        if not table_class2:
            table_class2 = self._classes[-1]
        if not column1:
            column1 = '%s_id' % table_class2.TABLE
        self._classes.append(table_class1)
        if outer:
            direction = 'LEFT' if outer is True else outer
            self._join += ' %s OUTER' % direction
        self._join += ' JOIN %s ON %s.`%s` = %s.`%s`' % (table_class1.FULL_TABLE_NAME(), table_class1.FULL_TABLE_NAME(), column1, table_class2.FULL_TABLE_NAME(), column2)

        self._columns.extend('%s.`%s`' % (table_class1.FULL_TABLE_NAME(), c) for c in table_class1.FIELDS)
        self._columns.extend('%s AS %s' % (c, n) for n, c in table_class1.CALCULATED_FIELDS.items())

        self._column_names.extend(table_class1.FIELDS)
        self._column_names.extend(table_class1.CALCULATED_FIELDS.keys())

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

    def execute(self, callback, arg=None, one=False, limit=None, offset=None, for_update=False, before_execute=None, after_execute=None, cursor=None):
        self._stmt = self._build(one, limit, offset, for_update)
        self._executed_stmt = None
        if before_execute:
            before_execute(self)

        def on_execute(rc, result):
            if rc != 0:
                return callback(rc, result)

            self._executed_stmt = cursor._executed
            if after_execute:
                after_execute(self)
            rows = []
            for rs in result:
                tables = None
                row = [t for t in zip(self._column_names, rs)]
                for c in self._classes:
                    count = len(c.FIELDS) + len(c.CALCULATED_FIELDS)
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

        if not cursor:
            cursor = DB.cursor
        cursor.execute(on_execute, self._stmt, arg)
