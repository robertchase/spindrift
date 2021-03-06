''' The MIT License (MIT)

https://github.com/robertchase/spindrift/blob/master/LICENSE.txt
'''
from spindrift.database.field import FieldCache
from spindrift.database.query import Query


class DAO():
    """Database Access Object
    """

    TABLENAME = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not hasattr(cls, '_fields'):
            if cls.TABLENAME is None:
                raise AttributeError('TABLENAME not defined')
            cls._fields = FieldCache.parse(cls)

    def __init__(self, **kwargs):
        kwargs = self._transform_foreign(kwargs)
        for nam, fld in self._fields.all_fields.items():
            self.__dict__[nam] = fld.default
        for nam, val in kwargs.items():
            setattr(self, nam, val)
        self._cache_field_values()

    def __repr__(self):
        flds = {nam: getattr(self, nam) for nam in self._fields.all_fields}
        flds.update({nam: val
                    for nam, val in self.__dict__.get('_tables', {}).items()})
        return '<{}>:{}'.format(self.__class__.__name__, flds)

    def __getattr__(self, name):
        joined = self.__dict__.get('_tables', {})
        if name in joined:
            return joined.get(name)
        lookup = self._fields.lookup.get(name)
        if lookup:
            return lookup(self)
        raise AttributeError("'{}' is not a '{}' attribute".format(
            name, self.__class__.__name__
        ))

    def __getitem__(self, name):
        return getattr(self, name)

    def __setattr__(self, name, value):
        if name.startswith('_'):
            super().__setattr__(name, value)
        else:
            fld = self._fields[name]
            if value is None and not fld.is_nullable:
                raise TypeError("'{}' cannot be None".format(name))
            if not (value is None and fld.is_nullable):
                value = fld.coerce(value)
            super().__setattr__(name, value)

    @classmethod
    def select(cls, callback, query, args=None, cursor=None):
        """Run an arbitrary SELECT statement

           The objects returned in the result do not have any of the
           functionality of a DAO. Columns are accessed as attributes
           by name using dot or bracket notation.

           Parameters:
               callback - callback_fn(rc, result)
               query    - query string (with %s substitutions)
               args     - substitution parameters
                          (None, scalar or tuple)
               cursor   - database cursor

           Callback result:
               ((column names), (result objects))

           Notes:
               1. a column name is either the value specified in the
                  query 'AS' clause, or the value used to indicate the
                  select_expr
        """
        if not cursor:
            if hasattr(callback, '_run_sync'):
                return callback._run_sync(
                    cls.select, query, args=args, cursor=callback,
                )
            raise Exception('cursor not specified')

        class Row:

            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

            def __getitem__(self, name):
                return self.__dict__[name]

            def __repr__(self):
                return str(self.__dict__)

        cursor.execute(callback, query, args=args, cls=Row)

    @classmethod
    def load(cls, callback, key, cursor=None):
        """Load a database row by primary key.
        """
        if not cursor:
            if hasattr(callback, '_run_sync'):
                return callback._run_sync(
                    cls.load, key, cursor=callback
                )
            raise Exception('cursor not specified')

        where = '`{}`=%s'.format(cls._fields.pk)
        cls.query.where(where).execute(callback, key, one=True, cursor=cursor)

    class _classproperty(object):
        """Hack for property-like access to query method

           https://stackoverflow.com/questions/5189699/how-to-make-a-class-property
        """
        def __init__(self, fn):
            self.fn = fn

        def __get__(self, theinstance, theclass):
            return self.fn(theclass)

    @_classproperty
    def query(cls):
        """Create a query object for this DAO.
        """
        return Query(cls)

    def save(self, callback, insert=False, cursor=None):
        """Save database object by primary key

           Parameters:
               callback - callback_fn(rc, result)
               insert - bool
                        if True save object with non-None primary key with
                        INSERT instead of UPDATE
               cursor - database cursor

           Callback result:
               self

           Notes:

               1. Objects with a None primary key are INSERTED. After the
                  INSERT, the primary key attribute is set to the
                  auto-generated primary key.

               2. On UPDATE, only changed fields, if any, are SET.

               3. This call will not change expression Fields.
        """
        if not cursor:
            if hasattr(callback, '_run_sync'):
                return callback._run_sync(
                    self.save, insert=insert, cursor=callback,
                )
            raise Exception('cursor not specified')

        pk = self._fields.pk
        self._updated = []
        if insert or pk is None or getattr(self, pk) is None:
            new = True
            db_insert = self._fields.db_insert
            fields = db_insert if insert else self._fields.db_update
            fields = [
                f.name
                for f in fields
                if not (f.is_nullable and getattr(self, f.name) is None)
            ]
            stmt = ' '.join((
                'INSERT INTO',
                '`' + self.TABLENAME + '`',
                ' (',
                ','.join('`' + f + '`' for f in fields),
                ') VALUES (',
                ','.join('%s' for n in range(len(fields))),
                ')',
            ))
            args = [getattr(self, f) for f in fields]
        else:
            if not pk:
                raise Exception(
                    'DAO UPDATE requires that a primary key field be defined'
                )
            new = False
            fields = self._fields_to_update
            if fields is None:
                cursor.statement = None
                callback(0, self)
                return
            stmt = ' '.join((
                'UPDATE ',
                '`' + self.TABLENAME + '`',
                'SET',
                ','.join(['`{}`=%s'.format(fld.column) for fld in fields]),
                'WHERE `{}`=%s'.format(pk),
            ))
            args = [getattr(self, fld.name) for fld in fields]
            args.append(getattr(self, pk))

        def on_save(rc, result):
            if rc != 0:
                callback(rc, result)
                return
            self._cache_field_values()
            if new:
                if not insert and pk:
                    setattr(self, pk, cursor.lastrowid)
            else:
                self._updated = [field.name for field in fields]
            callback(0, self)

        cursor.execute(on_save, stmt, args)

    def insert(self, callback, id=None, cursor=None):
        """Force insert of database object.

           Insert usually happens automatically when id is NOT specified; this
           is for the unusual case where you want to specifiy the primary key
           yourself.

           Parameters:
               callback - callback_fn(rc, result)
               id - primary key to use for insert (else 'id' attribute on self)
               cursor - database cursor

           Callback result:
               self
        """
        if id is not None:
            pk = self._fields.pk
            setattr(self, pk, id)
        return self.save(callback, insert=True, cursor=cursor)

    def delete(self, callback, cursor=None):
        """Delete matching row from database by primary key.

           Parameters:
               callback - callback_fn(rc, result)
               cursor - database cursor

           Callback result:
              None
        """
        if not cursor:
            if hasattr(callback, '_run_sync'):
                return callback._run_sync(
                    self.delete, cursor=callback,
                )
            raise Exception('cursor not specified')
        pk = self._fields.pk
        query = 'DELETE from `{}` where `{}`=%s'.format(
            self.TABLENAME, pk
        )

        def on_delete(rc, result):
            if rc == 0:
                result = None
            callback(rc, result)

        cursor.execute(on_delete, query, getattr(self, pk))

    @classmethod
    def list(cls, callback, where=None, order=None, offset=None, limit=None,
             args=None, cursor=None):
        """Query for a set of objects from underlying table

           Parameters:
               callback - callback_fn(rc, result)
               where - optional where clause to restrict list
               order - optional order clause to sort list
               offset - offset into selected list
               limit - number of instances to return
               args - optional substitution values for where clause
               cursor - database cursor

           Callback result:
               List of objects of type cls
        """
        args = tuple() if not args else args
        return cls.query.where(where).order(order).execute(
            callback, args=args, offset=offset, limit=limit, cursor=cursor
        )

    @classmethod
    def count(cls, callback, where=None, args=None, cursor=None):
        """Count a set of objects in underlying table

           Parameters:
               callback - callback_fn(rc, result)
               where - optional where clause to restrict count
               args - optional substitution values for where clause
               cursor - database cursor

           Callback result:
              count (int)
        """
        if not cursor:
            if hasattr(callback, '_run_sync'):
                return callback._run_sync(
                    cls.count, where=where, args=args, cursor=callback,
                )
            raise Exception('cursor not specified')
        query = 'SELECT COUNT(*) FROM `{}`'.format(cls.TABLENAME)
        if where:
            query += ' WHERE ' + where

        def on_count(rc, result):
            if rc == 0:
                columns, values = result
                value = values[0][0]
            callback(rc, value)

        cursor.execute(on_count, query, args)

    # ---

    @classmethod
    def _callables(cls):
        return [nam for nam in dir(DAO) if
                nam != 'query' and
                not nam.startswith('_') and
                callable(getattr(DAO, nam))]

    def _transform_foreign(self, kwargs):
        transform = {}
        for nam, val in kwargs.items():
            foreign = self._fields.foreign.get(nam)
            if foreign:
                fk = foreign.field_name
                fv = getattr(val, val._fields.pk)
                transform[fk] = fv
            else:
                transform[nam] = val
        return transform

    def _cache_field_values(self):
        self._orig = {fld.name: getattr(self, fld.name) for
                      fld in self._fields.db_update}

    @property
    def _fields_to_update(self):
        f = [
            fld
            for fld in self._fields.db_update
            if getattr(self, fld.name) != self._orig[fld.name]
        ]
        if len(f) == 0:
            return None
        return f


def gather(items, attribute):
    """Gather children DAOs into a list under a shared parent.

        A+1       A+[1,3,5]
        B+C       B+[C, x]
        A+3  -->
        A+5
        B+x

        A shared parent (A or B in the example) is identified by
        primary key.

        1, 3, 5, C and x are joined DAOs named by 'attribute'.  These
        are gathered into a list.

       Arguments:

        items - list of DAOs
        attribute - name of joined child
    """
    if not items:
        return None
    group = {}
    for item in items:
        child = getattr(item, attribute)
        pk = getattr(item, item._fields.pk)
        if pk not in group:
            group[pk] = item
            joined = item.__dict__.get('_tables', {})
            joined[attribute] = []
        parent = group[pk]
        if child:
            getattr(parent, attribute).append(child)
    return [v for v in group.values()]
