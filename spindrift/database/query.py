'''
The MIT License (MIT)

https://github.com/robertchase/spindrift/blob/master/LICENSE.txt
'''
from ergaleia.import_by_path import import_by_path


class QueryTable:

    def __init__(self, cls, alias):
        self.cls = cls
        self.alias = alias
        self.column_count = len(self.fields)

    @property
    def fields(self):
        return self.cls._fields.db_read

    @property
    def foreign(self):
        return self.cls._fields.foreign


class Query(object):

    def __init__(self, table):
        self._tables = [QueryTable(table, table.TABLENAME)]
        self._join = '`' + table.TABLENAME + '`'

        self._where = None
        self._order = None

    @property
    def _classes(self):
        return [table.cls for table in self._tables]

    def where(self, where=None):
        self._where = where
        return self

    def order(self, order):
        self._order = order
        return self

    def join(self, table, alias=None, table2=None, outer=None):
        """Add a table to the query (equi join)

            Parameters:
                table  - DAO of the table to add to the query
                alias  - name of joined table (1)
                table2 - DAO of table to join (2)
                outer  - OUTER join indicator
                         LEFT or RIGHT

           Notes:
               1. Any joined DAO is accesible as an attribute of the DAO used
                  to create the Query object. The default attribute name is
                  the lower case classname of the DAO. Specifying 'alias' will
                  override this default.

                  Example of join result structure:

                      This query:

                        Root.query().join(Node).execute(...)

                      will result in a set of Root instances, each joined
                      to a Node instance. Each Node instance is added as
                      an attribute of a Root instance. Therefore:

                        root = result[0]
                        node = root.node

                  In the case of multiple join clauses, each joined instance
                  will be added to the DAO used to create the Query object.

                  The 'alias' parameter can be used to prevent collision with
                  an existing DAO attribute, or to allow the same DAO to be
                  joined more than once.

               2. If multiple tables match...
        """
        table = import_by_path(table)
        if table2:
            table2 = import_by_path(table2)
        table, field, table2, field2 = self._normalize(table, table2)
        if alias is None:
            alias = table.__name__.lower()

        self._tables.append(QueryTable(table, alias))

        if outer is None:
            join = ' JOIN '
        elif outer.lower() == 'right':
            join = ' RIGHT OUTER JOIN '
        elif outer.lower() == 'left':
            join = ' LEFT OUTER JOIN '
        else:
            raise ValueError("invalid outer join value: '{}'".format(outer))

        self._join += '{} `{}` AS `{}` ON `{}`.`{}` = `{}`.`{}`'.format(
            join,
            table.TABLENAME, alias,
            alias, table._fields[field].name,
            table2.alias, table2.cls._fields[field2].name,
        )

        return self

    def _find_foreign_key_reference(self, table, table2):
        try:
            foreign = table._fields.foreign
        except AttributeError:
            raise TypeError('table must be a DAO')
        if len(foreign) == 0:
            return None
        classes = (table2,) if table2 else self._classes
        refs = [f for f in foreign.values() if f.cls in classes]
        if len(refs) == 0:
            return None
        if len(refs) > 1:
            raise TypeError(
                "'{}' has multiple foreign keys that match".format(
                    table.__name__
                )
            )
        return refs[0]

    def _find_primary_key_reference(self, table, table2):
        tables = (QueryTable(table2),) if table2 else self._tables
        refs = [
            (t.cls, f.field_name) for t in tables
            for f in t.foreign.values()
            if f.cls == table
        ]
        if len(refs) == 0:
            return None
        if len(refs) > 1:
            raise TypeError(
                "'{}' has multiple foreign keys that match".format(
                    table.__name__
                )
            )
        return refs[0]

    def _normalize(self, table, table2):
        ref = self._find_foreign_key_reference(table, table2)
        if ref:
            return table, ref.field_name, ref.cls, ref.cls._fields.pk

        import pdb; pdb.set_trace()
        ref = self._find_primary_key_reference(table, table2)
        if ref:
            cls, field = ref
            return table, table._fields.pk, cls, field

        if field is None:
            field, table2, field2 = self._normalize_field(
                table, field, table2, field2)
        elif table2 is None:
            try:
                fld = table._fields[field]
            except AttributeError:
                raise TypeError('table must be a DAO')
            if not fld.foreign:
                raise ValueError('table2 and field2 must be specified')
            table2 = fld.foreign.cls
        if field2 is None:
            field2 = table2._fields.pk
        table2 = [tbl for tbl in self._tables if tbl.cls == table2][0]
        return table, field, table2, field2

    def _build(self, one, limit, offset, for_update):
        if one and limit:
            raise Exception('one and limit parameters are mutually exclusive')
        if one:
            limit = 1

        stmt = 'SELECT '
        stmt += ','.join(
            fld.as_select(table.alias)
            for table in self._tables
            for fld in table.fields
        )
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
            if hasattr(callback, '_run_sync'):
                return callback._run_sync(
                    self.execute, arg=arg, one=one, limit=limit, offset=offset,
                    for_update=for_update, before_execute=before_execute,
                    after_execute=after_execute, cursor=callback,
                )
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
                for table in self._tables:
                    val = row[:table.column_count]
                    o = table.cls(**dict(val))
                    if tables is None:
                        primary_table = o
                        o._tables = tables = {}
                    else:
                        tables[table.alias] = o
                    row = row[table.column_count:]
                rows.append(primary_table)

            if one:
                rows = rows[0] if len(rows) else None
            callback(0, rows)

        cursor.execute(on_execute, stmt, arg)
