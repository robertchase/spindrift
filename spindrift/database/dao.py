''' The MIT License (MIT)

https://github.com/robertchase/spindrift/blob/master/LICENSE.txt
'''
from spindrift.database.field import Field, Foreign
from spindrift.database.query import Query


class _fields:
    def __init__(self, cls):
        self.all_fields = {}
        fields = []
        for nam in dir(cls):
            attr = getattr(cls, nam)
            if not isinstance(attr, Field):
                continue
            if attr.column and attr.column != nam:
                attr.alias = nam
            elif attr.expression:
                attr.alias = nam
            else:
                attr.column = nam
            attr.dao = cls
            fields.append(attr)
            self.all_fields[attr.name] = attr
            delattr(cls, nam)

        pk = [fld.name for fld in fields if fld.is_primary]
        if not pk:
            self.pk = None
        elif len(pk) != 1:
            raise Exception('only one field can be is_primary=True')
        else:
            self.pk = pk[0]

        self.db_read = [fld for fld in fields if fld.is_database]
        self.db_insert = [fld for fld in self.db_read if not fld.expression]
        self.db_update = [fld for fld in self.db_insert if not fld.is_primary]

        self.foreign = {}
        for nam in dir(cls):
            attr = getattr(cls, nam)
            if not isinstance(attr, Foreign):
                continue
            self.foreign[nam] = attr
            delattr(cls, nam)


class DAO():
    """Database Access Object
    """

    TABLENAME = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not hasattr(cls, '_fields'):
            if cls.TABLENAME is None:
                raise AttributeError('TABLENAME not defined')
            cls._fields = _fields(cls)

    def __init__(self, **kwargs):
        for nam, fld in self._all_fields.items():
            self.__dict__[nam] = fld.default
        for nam, val in kwargs.items():
            setattr(self, nam, val)
        self._cache_field_values()

    def __getattr__(self, name):
        if name[0] == '_':
            return getattr(self._fields, name[1:])
        foreign = self._fields.foreign.get(name)
        if foreign:
            return foreign(self)
        raise AttributeError("DAO '{}' does not have attribute '{}'".format(
            self.__class__.__name__, name
        ))

    def __setattr__(self, name, value):
        if name.startswith('_'):
            super().__setattr__(name, value)
        else:
            fld = self.field(name)
            if not (value is None and fld.is_nullable):
                value = fld.coerce(value)
            super().__setattr__(name, value)

    def before_init(self, kwargs):
        pass

    def on_new(self, kwargs):
        pass

    def on_init(self, kwargs):
        pass

    def on_load(self, kwargs):
        pass

    def after_init(self):
        pass

    def before_save(self):
        pass

    def before_insert(self):
        pass

    def after_insert(self):
        pass

    def after_save(self):
        pass

    def field(self, name):
        """Get a Field by DAO attribute name.
        """
        fld = self._all_fields.get(name)
        if not fld:
            raise AttributeError("invalid Field name: '{}'".format(name))
        return fld

    @classmethod
    def load(cls, callback, key, cursor=None):
        """Load a database row by primary key.
        """
        cls.query().by_pk().execute(
            callback, key, one=True, cursor=cursor
        )

    @classmethod
    def query(cls):
        """Create a query object for this DAO.
        """
        return Query(cls)

    def save(self, callback, insert=False, cursor=None,
             start_transaction=False, commit=False):
        """Save database object by id

           Parameters:
               callback - callback_fn(rc, result)
               insert - bool
                        if True save object with non-None id with INSERT
                        instead of UPDATE
               cursor - database cursor
               start_transaction - start transaction before performing save
                                   (See Note 3)
               commit - commit transaction after performing save (See Note 3)

           Callback result:
               self

           Notes:

               1. Objects with a None value for _pk are INSERTED. After the
                  INSERT, the _pk attribute is set to the auto-generated
                  primary key.

               2. On UPDATE, only changed fields, if any, are SET.

               3. If start_transaction and commit are not specified, then the
                  save will be automatically wrapped in a transaction
                  (start_transaction, save, commit).
        """
        if not cursor:
            raise Exception('cursor not specified')
        self.before_save()

        def on_save(rc, result):
            if rc == 0:
                self.after_save()
                callback(0, self)
            else:
                callback(rc, result)

        self._save(on_save, insert, cursor, start_transaction, commit)

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
            self.id = id
        self.save(callback, insert=True, cursor=cursor)

    def delete(self, callback, cursor=None):
        """Delete matching row from database by primary key.

           Parameters:
               callback - callback_fn(rc, result)
               cursor - database cursor

           Callback result:
              None
        """
        if not cursor:
            raise Exception('cursor not specified')
        pk = self._pk
        query = 'DELETE from `{}` where `{}`=%s'.format(
            self.TABLENAME, pk
        )

        def on_delete(rc, result):
            if rc == 0:
                result = None
            callback(rc, result)

        cursor.execute(on_delete, query, getattr(self, pk))

    def _save(self, callback, insert, cursor, start_transaction, commit):
        pk = self._pk
        if insert or pk is None or getattr(self, pk) is None:
            new = True
            self.before_insert()
            fields = self._db_insert if insert else self._db_update
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
            fields = self.fields_to_update
            self._db_update = [] if fields is None else fields
            if fields is None:
                self._executed_stmt = self._stmt = None
                callback(0, self)
                return
            stmt = ' '.join((
                'UPDATE ',
                '`' + self.TABLENAME + '`',
                'SET',
                ','.join(['`{}`=%s'.format(fld.column) for fld in fields]),
                'WHERE id=%s',
            ))
            args = [getattr(self, fld.name) for fld in fields]
            args.append(self.id)

        def on_save(rc, result):
            self._executed_stmt = cursor._executed
            if rc != 0:
                callback(rc, result)
                return
            self._cache_field_values()
            if new:
                if not insert and pk:
                    setattr(self, pk, cursor.lastrowid)
                self.after_insert()
            callback(0, self)

        self._stmt = stmt
        self._executed_stmt = None
        if start_transaction is False and commit is False:
            cursor.transaction()
        cursor.execute(
            on_save,
            stmt,
            args,
            start_transaction=start_transaction,
            commit=commit,
        )

    def _cache_field_values(self):
        self._orig = {fld.name: getattr(self, fld.name) for
                      fld in self._db_update}

    @property
    def _fields_to_update(self):
        f = [
            fld
            for fld in self._db_update
            if getattr(self, fld.name) != self._orig.get(fld.name)
        ]
        if len(f) == 0:
            return None
        return f
