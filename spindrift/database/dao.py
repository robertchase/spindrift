''' The MIT License (MIT)

https://github.com/robertchase/spindrift/blob/master/LICENSE.txt
'''
from spindrift.database.field import Field
from spindrift.database.query import Query


class DAO():
    """Database Access Object
    """

    TABLENAME = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not cls._fields:
            if cls.TABLENAME is None:
                raise AttributeError('TABLENAME not defined')
            cls._bind()

    _fields = {}
    _db_fields = []
    _pk = []
    _non_pk_fields = []

    @classmethod
    def _bind(cls):
        for nam in dir(cls):
            fld = getattr(cls, nam)
            if isinstance(fld, Field):
                fld.dao = cls
                if fld.name is None:
                    fld.name = nam
                cls._fields[nam] = fld
                if fld.is_primary:
                    cls._pk.append(fld)
                if fld.is_database:
                    cls._db_fields.append(fld)
                    if not fld.is_primary:
                        cls._non_pk_fields.append(fld)
                delattr(cls, nam)

    def __init__(self, **kwargs):
        for nam, fld in self._fields.items():
            self.__dict__[nam] = fld.default
        for nam, val in kwargs.items():
            setattr(self, nam, val)
        self._cache_fields()

    @classmethod
    def field(cls, name):
        fld = cls._fields.get(name)
        if not isinstance(fld, Field):
            raise AttributeError("invalid Field name: '{}'".format(name))
        return fld

    def __setattr__(self, name, value):
        if name.startswith('_'):
            super().__setattr__(name, value)
        else:
            fld = self.field(name)
            self.__dict__[name] = fld.coerce(value)

    @classmethod
    def load(cls, callback, key, cursor=None):
        cls.query().by_pk().execute(
            callback, key, one=True, cursor=cursor
        )

    @classmethod
    def query(cls):
        return Query(cls)

    def save(self, callback, insert=False, cursor=None,
             start_transaction=False, commit=False):
        """ Save database object by id

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

    def _save(self, callback, insert, cursor, start_transaction, commit):
        pk = self._pk[0].name if self._pk else None
        if insert or pk is None or getattr(self, pk) is None:
            new = True
            self.before_insert()
            fields = self._db_fields if insert else self._non_pk_fields
            fields = [
                f
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
            args = [getattr(self, f.name) for f in fields]
        else:
            if not pk:
                raise Exception(
                    'DAO UPDATE requires that a primary key field be defined'
                )
            new = False
            fields = self.fields_to_update
            self._updated_fields = [] if fields is None else fields
            if fields is None:
                self._executed_stmt = self._stmt = None
                callback(0, self)
                return
            stmt = ' '.join((
                'UPDATE ',
                '`' + self.TABLENAME + '`',
                'SET',
                ','.join(['`{}`=%s'.format(n) for n in fields]),
                'WHERE id=%s',
            ))
            args = [self.__dict__[f] for f in fields]
            args.append(self.id)

        def on_save(rc, result):
            self._executed_stmt = cursor._executed
            if rc != 0:
                callback(rc, result)
                return
            self._cache_fields()
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

    def _cache_fields(self):
        self._orig = {fld.nam: getattr(self, fld.nam) for
                      fld in self._non_pk_fields}

    @property
    def _fields_to_update(self):
        f = [
            fld.nam
            for fld in self._non_pk_fields
            if getattr(self, fld.nam) != self._orig.get(fld.nam)
        ]
        if len(f) == 0:
            return None
        return f
