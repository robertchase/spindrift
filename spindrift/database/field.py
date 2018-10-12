'''
The MIT License (MIT)

https://github.com/robertchase/spindrift/blob/master/LICENSE.txt
'''


class Field:
    def __init__(self, coerce=None, default=None, column=None,
                 is_nullable=False, is_primary=False, expression=None,
                 is_readonly=False, is_database=True):
        self.coerce = coerce if coerce else lambda x: x
        self.default = default
        self.alias = None
        self.column = column
        self.is_nullable = is_nullable
        self.is_primary = is_primary
        self.expression = expression
        self.is_readonly = is_readonly or expression is not None
        self.is_database = is_database

    @property
    def name(self):
        return self.alias if self.alias else self.column

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

    def __init__(self, cls, field_name):
        self.cls = cls
        self.field_name = field_name

    def __call__(self, instance):
        def _foreign(callback, cursor):
            return instance._pk, self.field_name
            # self.cls.load(callback, getattr(self.instance, self._field_name),
            #               cursor=cursor)
        return _foreign


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
