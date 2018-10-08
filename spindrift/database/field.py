'''
The MIT License (MIT)

https://github.com/robertchase/spindrift/blob/master/LICENSE.txt
'''


class Field():
    def __init__(self, coerce=str, default=None, name=None, is_nullable=False,
                 is_primary=False, expression=None, is_readonly=False,
                 is_database=True):
        self.coerce = coerce
        self.default = default
        self.name = name
        self.is_nullable = is_nullable
        self.is_primary = is_primary
        self.expression = expression
        self.is_readonly = is_readonly or expression is not None
        self.is_database = is_database


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
