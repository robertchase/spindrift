'''
The MIT License (MIT)

https://github.com/robertchase/spindrift/blob/master/LICENSE.txt
'''
from ergaleia.import_by_path import import_by_path


class Field:
    def __init__(self, coerce=None, default=None, column=None,
                 is_nullable=False, is_primary=False, expression=None,
                 is_readonly=False, is_database=True, foreign=None):
        self.coerce = coerce if coerce else lambda x: x
        self.default = default
        self.alias = None
        self.column = column
        self.is_nullable = is_nullable
        self.is_primary = is_primary
        self.expression = expression
        self.is_readonly = is_readonly or expression is not None
        self.is_database = is_database
        self.foreign = foreign

    @property
    def name(self):
        return self.alias if self.alias else self.column

    @property
    def fullname(self):
        return '`{}`.`{}`'.format(self.dao.TABLENAME, self.name)

    @property
    def as_select(self):
        if self.expression:
            return '{} AS {}'.format(self.expression, self.name)
        table = self.dao.TABLENAME
        if self.alias:
            return '`{}`.`{}` AS `{}`'.format(table, self.column, self.alias)
        else:
            return '`{}`.`{}`'.format(table, self.column)


class Foreign:
    def __init__(self, cls, attribute_name=None):
        self._cls = cls
        self.field_name = None
        if attribute_name is None:
            attribute_name = cls.split('.')[-1].lower()
        self.attribute_name = attribute_name

    @property
    def cls(self):
        self._cls = import_by_path(self._cls)
        return self._cls

    def __call__(self, instance):
        def _foreign(callback, cursor=None):
            id = getattr(instance, self.field_name)
            return self.cls.load(callback, id, cursor=cursor)
        return _foreign


class Children:

    def __init__(self, cls, field_name=None):
        self._cls = cls
        self.field_name = field_name

    @property
    def cls(self):
        self._cls = import_by_path(self._cls)
        return self._cls

    def __call__(self, instance):
        if self.field_name is None:
            for nam, key in self.cls._fields.foreign.items():
                if isinstance(instance, key.cls):
                    self.field_name = key.field_name
                    break
            if self.field_name is None:
                raise AttributeError('No foreign key match found')

        def _children(callback, cursor=None):
            return self.cls.query().where(
                '`{}`=%s'.format(self.field_name)).execute(
                    callback, getattr(instance, instance._fields.pk),
                    cursor=cursor
            )
        return _children


def coerce_bool(value):
    if isinstance(value, str) and value.lower() == 'true':
        return True
    if value in (True, 1, '1'):
        return True
    if isinstance(value, str) and value.lower() == 'false':
        return False
    if value in (False, 0, '0'):
        return False
    raise ValueError("invalid literal for coerce_bool(): '{}'".format(value))


def coerce_int(value):
    v_int = int(value)
    f_int = float(value)
    if v_int == f_int:
        return v_int
    raise ValueError("invalid number for coerce_int(): '{}'".format(value))


class FieldCache:

    def __init__(self):
        self.all_fields = {}
        self.foreign = {}
        self.lookup = {}
        self.db_read = []
        self.db_insert = []
        self.db_update = []

    def __getitem__(self, name):
        fld = self.all_fields.get(name)
        if fld is None:
            raise AttributeError("invalid Field name: '{}'".format(name))
        return fld

    def parse(self, cls):
        reserved = cls._callables()
        fields = self.parse_fields(cls, reserved)
        self.parse_children(cls, reserved)
        self.parse_pk(fields, reserved)

        self.db_read = [fld for fld in fields if fld.is_database]
        self.db_insert = [fld for fld in self.db_read if not fld.expression]
        self.db_update = [fld for fld in self.db_insert if not fld.is_primary]

        return self

    def parse_fields(self, cls, reserved):
        fields = []
        for nam in dir(cls):
            attr = getattr(cls, nam)
            if not isinstance(attr, Field):
                continue
            if nam in reserved:
                raise AttributeError(
                    "Field name '{}' overrides a DAO function".format(nam)
                )
            if attr.column and attr.column != nam:
                attr.alias = nam
            elif attr.expression:
                attr.alias = nam
            else:
                attr.column = nam

            foreign = getattr(attr, 'foreign')
            if foreign:
                if not isinstance(foreign, Foreign):
                    foreign = Foreign(foreign)
                foreign.field_name = nam
                self.foreign[foreign.attribute_name] = foreign
                self.lookup[foreign.attribute_name] = foreign

            attr.dao = cls
            fields.append(attr)
            self.all_fields[attr.name] = attr
            delattr(cls, nam)

        return fields

    def parse_children(self, cls, reserved):

        for nam in dir(cls):
            attr = getattr(cls, nam)
            if not isinstance(attr, Children):
                continue
            if nam in reserved:
                raise AttributeError(
                    "Children name '{}' overrides a DAO function".format(nam)
                )
            self.lookup[nam] = attr
            delattr(cls, nam)

    def parse_pk(self, fields, reserved):

        pk = [fld.name for fld in fields if fld.is_primary]
        if not pk:
            self.pk = None
        elif len(pk) != 1:
            raise Exception('only one field can be is_primary=True')
        elif pk[0] in reserved:
            raise AttributeError(
                "Primary key '{}' overrides a DAO function".format(pk[0])
            )
        else:
            self.pk = pk[0]
