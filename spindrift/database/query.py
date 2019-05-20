'''
The MIT License (MIT)

https://github.com/robertchase/spindrift/blob/master/LICENSE.txt
'''
from ergaleia.import_by_path import import_by_path


class QueryTable:

    def __init__(self, cls, alias=None):
        self.cls = cls
        self.alias = alias or cls.__name__.lower()
        self.column_count = len(self.fields)

    @property
    def fields(self):
        return self.cls._fields.db_read

    @property
    def foreign(self):
        return self.cls._fields.foreign


class Query(object):

    def __init__(self, table):
        t = QueryTable(table)
        self._tables = [t]
        self._join = '`{}` AS `{}`'.format(table.TABLENAME, t.alias)

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

    def join(self, table, table2=None, alias=None, outer=None):
        """Add a table to the query

           The table will be joined to another table in the query using
           foreign or primary key matches.

            Parameters:
                table  - DAO of the table to add to the query (1)(4)
                table2 - name, alias or DAO of table to join (2)
                alias  - name of joined table (3)
                outer  - OUTER join indicator
                         LEFT or RIGHT

           Notes:
               1. The table can be specified as a DAO or as a dot separated
                  path to a DAO for import. First, foreign keys in 'table'
                  will be checked for a single matching primary key in one
                  of the tables that is already part of the query. If no
                  match is found, the primary key of 'table' will be matched
                  in the same way.
               2. If multiple matches occur when trying to join 'table',
                  the ambiguity can be removed by specifying which existing
                  table to match. Foreign keys from 'table' will be checked
                  first, followed by the primary key.
               3. The 'alias' parameter can be used to prevent collision with
                  an existing DAO attribute, or to allow the same DAO to be
                  joined more than once.
               4. Any joined DAO is accesible as an attribute of the DAO used
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
        """
        try:
            table = import_by_path(table)
        except ValueError:
            raise TypeError("invalid path to table: '{}'".format(table))
        except ModuleNotFoundError:
            raise TypeError("unable to load '{}'".format(table))
        if alias is None:
            alias = table.__name__.lower()
        if alias in [t.alias for t in self._tables]:
            raise ValueError("duplicate table '{}'".format(alias))

        table, field, table2, field2 = self._normalize(table, table2)
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
        tables = (table2,) if table2 else self._tables
        refs = [
            (t, f) for f in foreign.values()
            for t in tables
            if f.cls == t.cls
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

    def _find_primary_key_reference(self, table, table2):
        tables = (table2,) if table2 else self._tables
        refs = [
            (t, f.field_name) for t in tables
            for f in t.foreign.values()
            if f.cls == table
        ]
        if len(refs) == 0:
            return None
        if len(refs) > 1:
            raise TypeError(
                "'{}' matches mutiple foreign keys".format(
                    table.__name__
                )
            )
        return refs[0]

    def _normalize(self, table, table2):

        if table2:
            if table2 in self._tables:
                # lookup by alias
                table2 = self._tables[table2]
            else:
                # lookup by class
                table2 = import_by_path(table2)
                match = [t for t in self._tables if t.cls == table2]
                if not match:
                    raise TypeError(
                        "'{}' does not match any tables".format(
                            table2.__name__
                        )
                    )
                elif len(match) > 1:
                    raise TypeError(
                        "'{}' matches multiple tables".format(table2.__name__)
                    )
                table2 = match[0]

        ref = self._find_foreign_key_reference(table, table2)
        if ref:
            t, field = ref
            return table, field.field_name, t, t.cls._fields.pk

        ref = self._find_primary_key_reference(table, table2)
        if ref:
            t, field = ref
            return table, table._fields.pk, t, field

        raise TypeError(
            "no primary or foreign key matches found for '{}'".format(
                table.__name__
            )
        )

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
                cursor=None):
        if not cursor:
            if hasattr(callback, '_run_sync'):
                return callback._run_sync(
                    self.execute, arg=arg, one=one, limit=limit, offset=offset,
                    for_update=for_update, cursor=callback,
                )
            raise Exception('cursor not specified')
        stmt = self._build(one, limit, offset, for_update)

        def on_execute(rc, result):
            if rc != 0:
                return callback(rc, result)

            columns, values = result
            rows = []
            for rs in values:
                tables = None
                row = [t for t in zip(columns, rs)]
                for table in self._tables:
                    val = dict(row[:table.column_count])
                    if all(v is None for v in val.values()):
                        o = None
                    else:
                        o = table.cls(**val)
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
