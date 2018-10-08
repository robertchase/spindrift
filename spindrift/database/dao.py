''' The MIT License (MIT)

https://github.com/robertchase/spindrift/blob/master/LICENSE.txt
'''
from spindrift.database.field import Field
from spindrift.database.query import Query


class DAO():
    """Database Access Object
    """

    tablename = None

    def __init__(self, **kwargs):
        if self.tablename is None:
            raise AttributeError('tablename not defined')
        self._bind()
        for nam, fld in self._fields.items():
            self.__dict__[nam] = fld.default
        for nam, val in kwargs.items():
            setattr(self, nam, val)

    _fields = {}
    _db_fields = []
    _pk = []
    _non_pk_fields = []

    @classmethod
    def _bind(cls):
        """Bind Fields to DAO

           Save table class and attribute name into each Field. If Field
           already has a name, then don't override it.

           Save each Field in the _fields class attribute.
           Cache _db_fields, _pk and _non_pk_fields.
        """
        if not cls._fields:
            for nam in dir(cls):
                fld = getattr(cls, nam)
                if isinstance(fld, Field):
                    fld._table = cls
                    if fld.name is None:
                        fld.name = nam

                    cls._fields[nam] = fld
                    if fld.is_primary:
                        cls._pk.append(fld)
                    if fld.is_database:
                        cls._db_fields.append(fld)
                        if not fld.is_primary:
                            cls._non_pk_fields.append(fld)

    @classmethod
    def _field(cls, name):
        fld = cls._fields.get(name)
        if not isinstance(fld, Field):
            raise AttributeError("invalid Field name: '{}'".format(name))
        return fld

    def __setattr__(self, name, value):
        fld = self._field(name)
        self.__dict__[name] = fld.coerce(value)

    @classmethod
    def load(cls, callback, key, cursor=None):
        cls.query().by_pk().execute(
            callback, key, one=True, cursor=cursor
        )

    @classmethod
    def query(cls):
        return Query(cls)
