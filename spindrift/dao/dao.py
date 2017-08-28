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
from datetime import datetime, date
from itertools import chain
import json

from spindrift.dao.db import DB
from spindrift.dao.query import Query


class DAO(object):

    DATABASE = ''
    # TABLE = ''
    # FIELDS = ()
    CALCULATED_FIELDS = {}
    PROPERTIES = ()
    NULLABLE = ()
    DEFAULT = {}
    JSON_FIELDS = ()
    FOREIGN = {}  # name: 'class path'
    CHILDREN = {}  # name: 'class path'

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
    def FULL_TABLE_NAME(cls):
        table = '`%s`' % cls.TABLE
        if cls.DATABASE:
            table = '`%s`.%s' % (DB.database_map(cls.DATABASE), table)
        return table

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

    @property
    def _non_pk_fields(self):
        return [f for f in self.FIELDS if f not in 'id']

    def _foreign(self, kwargs):
        ''' identify and translate foreign key relations

            kwargs that match table names specified in FOREIGN are translated from
            objects to ids using a "table_name + '_id' = object.id" pattern.

            foreign objects are cached in self with the join method.
        '''
        for table in self.FOREIGN.keys():
            t = kwargs.get(table)
            if t:
                kwargs[table + '_id'] = t.id
                del kwargs[table]
                self.join(t)

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
            result = self._tables[name]  # cached foreign or Query.join added object
        elif name in self.FOREIGN:
            result = self.foreign(self._import(self.FOREIGN[name]))  # foreign lookup
        elif name in self._children:
            result = self._children[name]  # cached children
        elif name in self.CHILDREN:
            result = self.children(self._import(self.CHILDREN[name]))  # children lookup
        else:
            result = super(DAO, self).__getattribute__(name)
        return result

    def __getitem__(self, name):
        ''' allow access to other tables using DAO['other_table'] syntax '''
        return self.__getattr__(name)

    def __setattr__(self, name, value):
        if name.startswith('_') or name in self.FIELDS or name in self.PROPERTIES:
            self.__dict__[name] = value
        else:
            object.__setattr__(self, name, value)

    def _json(self, value):
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        return value

    def json(self):
        return self.on_json({n: self._json(getattr(self, n)) for n in chain(self.FIELDS, self.CALCULATED_FIELDS.keys()) if hasattr(self, n)})

    def on_json(self, json):
        return json

    def insert(self, id=None):
        ''' insert usually happens automatically when id is NOT specified; this is for the unusual case where you want to specifiy the primary key yourself '''
        if id is not None:
            self.id = id
        return self.save(insert=True)

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
        f = [f for f in self._non_pk_fields if getattr(self, f) != self._orig.get(f)]
        if len(f) == 0:
            return None
        return f

    def save(self, callback, insert=False, cursor=None, start_transaction=False, commit=False):
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
            callback(rc, result)

        if not cursor:
            cursor = DB.cursor
        self._save(on_save, insert, cursor, start_transaction, commit)

    def _save(self, callback, insert, cursor, start_transaction, commit):
        if insert or not hasattr(self, 'id'):
            new = True
            self.before_insert()
            fields = self._non_pk_fields if not insert else self.FIELDS
            fields = [f for f in fields if not (f in self.NULLABLE and self.__dict__[f] is None)]
            stmt = 'INSERT INTO ' + self.FULL_TABLE_NAME() + ' (' + ','.join('`' + f + '`' for f in fields) + ') VALUES (' + ','.join('%s' for n in range(len(fields))) + ')'
            args = [self.__dict__[f] for f in fields]
        else:
            if 'id' not in self.FIELDS:
                raise Exception('DAO UPDATE requires that an "id" field be defined')
            new = False
            fields = self._update_fields
            self._updated_fields = [] if fields is None else fields
            if fields is None:
                self._executed_stmt = self._stmt = None
                return callback(0, self)
            stmt = 'UPDATE ' + self.FULL_TABLE_NAME() + ' SET ' + ','.join(['`%s`=%%s' % n for n in fields]) + ' WHERE id=%s'
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
        cursor.execute(on_save, stmt, args, start_transaction=start_transaction, commit=commit)

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

    def delete(self):
        with DB as cur:
            cur.execute('DELETE from %s where `id`=%%s' % self.FULL_TABLE_NAME(), self.id)

    def children(self, cls):
        '''
            return the members of cls with a foreign_key reference to self.

            the query is constructed as 'WHERE <cls.TABLE>.<self.TABLE>_id = <self.id>'

            a lazy cache is maintained (query is done at most one time).
        '''
        if self.is_new:
            return []  # can't have children if we haven't been saved yet
        child = cls.TABLE
        if child not in self._children:
            self._children[child] = [c for c in cls.query().where('%s.%s_id = %%s' % (child, self.TABLE)).execute(self.id)]
        return self._children[child]

    def foreign(self, cls):
        '''
            return the instance of cls to which self has a foreign_key reference.

            the query is constructed as 'WHERE <cls.TABLE>.id = <self.<cls.TABLE>_id>'

            a lazy cache is maintained (query is done at most one time) using the join method.
        '''
        foreign = cls.TABLE
        if foreign not in self._tables:
            foreign_id = getattr(self, '%s_id' % foreign)
            if not foreign_id:
                return None
            self.join(cls.query().where('%s.id = %%s' % foreign).execute(foreign_id, one=True))
        return self._tables[foreign]

    @property
    def is_new(self):
        return not hasattr(self, 'id')

    @classmethod
    def load(cls, callback, id, cursor=None):
        return cls.query().by_id().execute(callback, id, one=True, cursor=cursor)

    @classmethod
    def list(cls, where=None, args=None):
        args = tuple() if not args else args
        return cls.query().where(where).execute(arg=args, generator=True)

    @classmethod
    def query(cls):
        return Query(cls)

    def join(self, obj):
        '''add a DAO to the list of tables to which this object is joined

        Allows the DAO.table_name or DAO[table_name] syntax to work for
        the specified object.

        Parameters:
            obj - object to 'join' to self, if None then pass

        Returns:
            self
        '''
        if obj:
            self._tables[obj.TABLE] = obj
            obj._tables = self._tables
        return self

    @classmethod
    def count(cls, where=None, arg=None):
        query = 'SELECT COUNT(*) FROM `%s`' % cls.TABLE
        if where:
            query += ' WHERE ' + where
        with DB as cur:
            cur.execute(query, arg)
            cnt = cur.fetchone()[0]
        return cnt
