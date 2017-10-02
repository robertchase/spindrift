'''
The MIT License (MIT)

https://github.com/robertchase/spindrift/blob/master/LICENSE.txt
'''
from datetime import datetime, date
from itertools import chain
import json

from spindrift.dao.db import DB
from spindrift.dao.query import Query


class DAO(object):
    """ Database Access Object

        A DAO defines the interface between a database table and a python object
        allowing INSERT, UPDATE, DELETE and QUERY operations.

        Database fields are mapped to a python object and available as
        attributes. Load and save operations are under explicit control of the
        calling program.

        The primary use case is load/save by primary key. The name of the
        primary key is assumed to be 'id' and foreign key references are assumed
        to be <foreign table name>_id. These assumptions are not required but
        make default actions much easier.

        All database operations are asynchronous and require a callback function
        at invocation. A callback function takes two parameters:

            callback(rc, result)

        where rc == 0 on success, else failure, and result is the operation's
        result on success, or an error message on failure.

        Example:

            class Foo(DAO):

                TABLE = 'foo'
                FIELDS = (
                    'id',
                    'name',
                )

            def on_load(rc, result):
                if rc != 0:
                    raise Exception(result)
                print(result.name)

            # load (QUERY by id) a Foo where id==10.
            Foo.load(on_load, 10)
    """

    DATABASE = ''           # database name
    # TABLE = ''            # required table name
    # FIELDS = ()           # required tuple of field names
    CALCULATED_FIELDS = {}  # read-only fields or calculated values
    #                         name: 'valid SQL expression'
    PROPERTIES = ()         # non-database attributes
    NULLABLE = ()           # fields that can be None for save (INSERT/UPDATE)
    DEFAULT = {}            # default values for null fields
    #                         name: default_value
    JSON_FIELDS = ()        # values which are json dumps/loads on save/load
    FOREIGN = {}            # name: 'class path'
    CHILDREN = {}           # name: 'class path'

    def __init__(self, **kwargs):
        self.before_init(kwargs)
        self._tables = {}
        self._children = {}
        self._foreign(kwargs)
        self._validate(kwargs)
        self._normalize(kwargs)
        self.on_init(kwargs)
        self._orig = {}
        if 'id' in kwargs:
            self.on_load(kwargs)
            self._cache_fields(data=kwargs)
            self._jsonify(kwargs)
        else:
            self.on_new(kwargs)
            self._cache_fields(data=kwargs, jsonify=True)
        self.__dict__.update(kwargs)
        self.after_init()

    @classmethod
    def load(cls, callback, id, cursor=None):
        """ Load database object by id

            Parameters:
                callback - callback_fn(rc, result)
                id - primary key
                cursor - databse cursor (if None, new cursor will be created)

            Callback result:
                DAO or None
        """
        return cls.query().by_id().execute(
            callback, id, one=True, cursor=cursor
        )

    def save(self, callback, insert=False, cursor=None,
             start_transaction=False, commit=False):
        """ Save database object by id
.
            Parameters:
                callback - callback_fn(rc, result)
                insert - bool
                         if True save object with non-None id with INSERT
                         instead of UPDATE
                cursor - database cursor (if None, new cursor will be created)
                start_transaction - start transaction before performing save
                                    (See Note 3)
                commit - commit transaction after performing save (See Note 3)

            Callback result:
                self

            Notes:

                1. Objects with a None value for 'id' are INSERTED. After the
                   INSERT, the id attribute is set to the auto-generated
                   primary key.

                2. On UPDATE, only changed fields, if any, are SET.

                3. If start_transaction and commit are not specified, then the
                   save will be automatically wrapped in a transaction
                   (start_transaction, save, commit).
        """
        cache = {}
        for n in self.JSON_FIELDS:
            v = cache[n] = getattr(self, n)
            if v is not None:
                setattr(self, n, json.dumps(self.on_json_save(n, v)))
        self.before_save()

        def on_save(rc, result):
            self.__dict__.update(cache)
            if rc == 0:
                self.after_save()
            callback(rc, self)

        if not cursor:
            cursor = DB.cursor
        self._save(on_save, insert, cursor, start_transaction, commit)

    def insert(self, callback, id=None, cursor=None):
        """ Force insert

            Insert usually happens automatically when id is NOT specified; this
            is for the unusual case where you want to specifiy the primary key
            yourself.

            Parameters:
                callback - callback_fn(rc, result)
                id - primary key to use for insert (else 'id' attribute on self)
                cursor - database cursor (if None, new cursor will be created)

            Callback result:
                self
        """
        if id is not None:
            self.id = id
        self.save(callback, insert=True, cursor=cursor)

    @classmethod
    def list(cls, callback, where=None, args=None, cursor=None):
        """ Query for a set of objects from underlying table

            Parameters:
                callback - callback_fn(rc, result)
                where - optional where clause to restrict list
                args - optional substitution values for where clause
                cursor - database cursor (if None, new cursor will be created)

            Callback result:
                List of objects of type cls
        """
        args = tuple() if not args else args
        return cls.query().where(where).execute(
            callback, arg=args, cursor=cursor
        )

    @classmethod
    def count(cls, callback, where=None, arg=None, cursor=None):
        """ Count set of objects in underlying table

            Parameters:
                callback - callback_fn(rc, result)
                where - optional where clause to restrict count
                args - optional substitution values for where clause
                cursor - database cursor (if None, new cursor will be created)

            Callback result:
               count (int)
        """
        query = 'SELECT COUNT(*) FROM `%s`' % cls.TABLE
        if where:
            query += ' WHERE ' + where

        def on_count(rc, result):
            if rc == 0:
                result = result[0][0]
            callback(rc, result)

        if not cursor:
            cursor = DB.cursor
        cursor.execute(on_count, query, arg)

    def delete(self, callback, cursor=None):
        """ Delete matching row from table

            Parameters:
                callback - callback_fn(rc, result)
                cursor - database cursor (if None, new cursor will be created)

            Callback result:
               None
        """
        query = 'DELETE from %s where `id`=%%s' % self.FULL_TABLE_NAME()

        def on_delete(rc, result):
            if rc == 0:
                result = None
            callback(rc, result)

        if not cursor:
            cursor = DB.cursor
        cursor.execute(on_delete, query, self.id, cursor=cursor)

    def children(self, callback, cls, cursor=None):
        """ Return members of cls with a foreign_key reference to self.

            Parameters:
                callback - callback_fn(rc, result)
                cls - subclass of DAO
                cursor - database cursor (if None, new cursor will be created)

            Callback result:
                list of children

            Notes:
                1. the query is constructed as
                   'WHERE <cls.TABLE>.<self.TABLE>_id = <self.id>'

                2. If self has not been saved, children cannot be determined
                   from the database. This will cause an error.
        """
        if self.is_new:
            return callback(1, "an unsaved DAO can't have children")
        child = cls.TABLE
        cls.query().where('%s.%s_id = %%s' % (child, self.TABLE)).execute(
            callback, self.id, cursor=cursor
        )

    def foreign(self, callback, cls, cursor=None):
        """ Get the instance of cls to which self has a foreign_key reference.

            Parameters:
                callback - callback_fn(rc, result)
                cls - subclass of DAO
                cursor - database cursor (if None, new cursor will be created)

            Callback result:
                DAO or foreign object or None

            Notes:
                1. The query is constructed as
                   'WHERE <cls.TABLE>.id = <self.<cls.TABLE>_id>'
        """
        foreign = cls.TABLE
        foreign_id = getattr(self, '%s_id' % foreign)
        if not foreign_id:
            return callback(0, None)
        cls.query().where('%s.id = %%s' % foreign).execute(
            callback, foreign_id, one=True, cursor=cursor
        )

    @classmethod
    def query(cls):
        """ Return a spindrift.dao.query object for this class

            This can be used to construct a query using methods on the query
            class.
        """
        return Query(cls)

    # --- the following callbacks can be useful in extending a DAO subclass

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

    def on_json_save(self, name, obj):
        return obj

    def before_save(self):
        pass

    def before_insert(self):
        pass

    def after_insert(self):
        pass

    def after_save(self):
        pass

    def json(self):
        return self.on_json({
            n: self._json(getattr(self, n))
            for n in
            chain(self.FIELDS, self.CALCULATED_FIELDS.keys())
            if hasattr(self, n)
        })

    def on_json(self, json):
        return json

    # ---

    def _save(self, callback, insert, cursor, start_transaction, commit):
        if insert or not hasattr(self, 'id'):
            new = True
            self.before_insert()
            fields = self._non_pk_fields if not insert else self.FIELDS
            fields = [
                f
                for f in fields
                if not (f in self.NULLABLE and self.__dict__[f] is None)
            ]
            stmt = ' '.join((
                'INSERT INTO',
                self.FULL_TABLE_NAME(),
                ' (',
                ','.join('`' + f + '`' for f in fields),
                ') VALUES (',
                ','.join('%s' for n in range(len(fields))),
                ')',
            ))
            args = [self.__dict__[f] for f in fields]
        else:
            if 'id' not in self.FIELDS:
                raise Exception(
                    'DAO UPDATE requires that an "id" field be defined'
                )
            new = False
            fields = self._update_fields
            self._updated_fields = [] if fields is None else fields
            if fields is None:
                self._executed_stmt = self._stmt = None
                return callback(0, self)
            stmt = ' '.join((
                'UPDATE ',
                self.FULL_TABLE_NAME(),
                'SET',
                ','.join(['`%s`=%%s' % n for n in fields]),
                'WHERE id=%s',
            ))
            args = [self.__dict__[f] for f in fields]
            args.append(self.id)

        def on_save(rc, result):
            self._executed_stmt = cursor._executed
            if rc != 0:
                return callback(rc, result)
            self._cache_fields()
            if new:
                if not insert and 'id' in self.FIELDS:
                    setattr(self, 'id', cursor.lastrowid)
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

    @property
    def is_new(self):
        return not hasattr(self, 'id')

    @classmethod
    def FULL_TABLE_NAME(cls):
        table = '`%s`' % cls.TABLE
        if cls.DATABASE:
            table = '`%s`.%s' % (DB.database_map(cls.DATABASE), table)
        return table

    @property
    def _non_pk_fields(self):
        return [f for f in self.FIELDS if f not in 'id']

    def _foreign(self, kwargs):
        ''' identify and translate foreign key relations

            kwargs that match table names specified in FOREIGN are translated
            from objects to ids using a "table_name + '_id' = object.id"
            pattern.
        '''
        for table in self.FOREIGN.keys():
            t = kwargs.get(table)
            if t:
                kwargs[table + '_id'] = t.id
                del kwargs[table]

    def _validate(self, kwargs):
        ''' make sure field names are valid '''
        for f in kwargs:
            if f not in self.FIELDS:
                if f not in self.PROPERTIES:
                    if f not in self.CALCULATED_FIELDS:
                        raise TypeError("Unexpected parameter: %s" % f)

    def _normalize(self, kwargs):
        ''' establish default or empty values for all fields '''
        for f in chain(self.FIELDS, self.CALCULATED_FIELDS, self.PROPERTIES):
            if f != 'id':
                if f not in kwargs:
                    if f in self.DEFAULT:
                        kwargs[f] = self.DEFAULT[f]
                    else:
                        kwargs[f] = None

    def _jsonify(self, kwargs):
        for f in self.JSON_FIELDS:
            if kwargs[f]:
                kwargs[f] = json.loads(kwargs[f])

    @staticmethod
    def _import(target):
        modnam, clsnam = target.rsplit('.', 1)
        mod = __import__(modnam)
        for part in modnam.split('.')[1:]:
            mod = getattr(mod, part)
        return getattr(mod, clsnam)

    def __getattr__(self, name):
        if name in self._tables:
            result = self._tables[name]
        else:
            result = super(DAO, self).__getattribute__(name)
        return result

    def __getitem__(self, name):
        ''' allow access to other tables using DAO['other_table'] syntax '''
        return self.__getattr__(name)

    def __setattr__(self, name, value):
        if name.startswith('_') or name in chain(self.FIELDS, self.PROPERTIES):
            self.__dict__[name] = value
        else:
            raise AttributeError("%s has no attribute '%s'" % (
                self.__class__.__name__, name)
            )

    def _json(self, value):
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        return value

    def _cache_fields(self, data=None, jsonify=False):
        ''' cache current fields to support updating changed fields only

            data    - dict of data values (else self.__dict__)
            jsonify - json.dumps JSON_FIELDS in data

            cache is not constructed if self._orig is None (set in __init__)
        '''
        if self._orig is not None:
            if data is None:
                data = self.__dict__
            self._orig = {f: data[f] for f in self._non_pk_fields}
            if jsonify:
                for n in self.JSON_FIELDS:
                    v = self._orig.get(n)
                    self._orig[n] = json.dumps(self.on_json_save(n, v))

    @property
    def _update_fields(self):
        if self._orig is None:
            return self._non_pk_fields
        f = [
            f
            for f in self._non_pk_fields
            if getattr(self, f) != self._orig.get(f)
        ]
        if len(f) == 0:
            return None
        return f
