'''
The MIT License (MIT)

https://github.com/robertchase/spindrift/blob/master/LICENSE.txt
'''


def un_comment(s, comment='#'):
    """ uncomment a string

        truncate s at first occurrence of a non-escaped comment character

        remove escapes from escaped comment characters

        don't use when speed is important
    """
    escape = '\\'
    is_escape = False
    result = ''
    for c in s:
        if c == comment:
            if is_escape:
                is_escape = False
            else:
                return result
        if is_escape:
            result += escape
        if c == escape:
            is_escape = True
        else:
            is_escape = False
            result += c
    return result


class Atom(object):

    ESCAPE = '\\'

    def __init__(self, c):
        self.c = c

    @property
    def is_string(self):
        return self.c in ('"', "'")

    @property
    def is_escape(self):
        return self.c == self.ESCAPE

    @property
    def is_equal(self):
        return self.c == '='

    @property
    def is_space(self):
        return self.c.isspace()


class Token(object):
    def __init__(self):
        self.value = ''
        self.is_key = False
        self.string_delim = None
        self.is_escape = False

    def __repr__(self):
        t = 's' if self.is_string else 'k' if self.is_key else 't'
        return '{}[{}]'.format(t, self.value)

    @property
    def is_new(self):
        return len(self.value) == 0

    @property
    def is_string(self):
        return self.string_delim is not None

    @property
    def is_escaped_string(self):
        return self.is_string and self.is_escape

    def add(self, atom):
        if self.is_new:
            return self._new(atom)
        if self.is_escaped_string:
            return self._escaped_string(atom)
        if self.is_string:
            return self._string(atom)
        return self._normal(atom)

    def _new(self, atom):
        if atom.is_space:
            return
        if atom.is_string:
            self.string_delim = atom.c
            return
        if atom.is_equal:
            return 'equal'
        self.value += atom.c

    def _escaped_string(self, atom):
        if atom.c != self.string_delim:
            self.value += atom.ESCAPE
        self.value += atom.c
        self.is_escape = False

    def _string(self, atom):
        if atom.is_escape:
            self.is_escape = True
            return
        if atom.c == self.string_delim:
            return 'done'
        self.value += atom.c

    def _normal(self, atom):
        if atom.is_space:
            return 'done'
        if atom.is_equal:
            return 'equal'
        if atom.is_escape or atom.is_string:
            return 'invalid'
        self.value += atom.c


class ToArgsException(Exception):
    pass


class InvalidStartCharacter(ToArgsException):
    pass


class ConsecutiveEqual(ToArgsException):
    pass


class UnexpectedCharacter(ToArgsException):
    pass


class ExpectingKey(ToArgsException):
    pass


class DuplicateKey(ToArgsException):
    pass


class ConsecutiveKeys(ToArgsException):
    pass


class IncompleteKeyValue(ToArgsException):
    pass


def to_tokens(s):
    tokens = []
    token = Token()
    for a in [Atom(c) for c in s]:

        result = token.add(a)
        if result == 'done':
            if not token.is_new:
                tokens.append(token)
                token = Token()
            continue
        if result == 'equal':
            if token.is_new:
                if len(tokens) == 0:
                    raise InvalidStartCharacter()
                if tokens[-1].is_key:
                    raise ConsecutiveEqual()
                tokens[-1].is_key = True
            else:
                token.is_key = True
                tokens.append(token)
                token = Token()
            continue
        if result == 'invalid':
            raise UnexpectedCharacter(a.c)

    if not token.is_new:
        tokens.append(token)

    return tokens


def to_args(s):
    """ parse a string into args and kwargs

        the input is a blank-delimited set of tokens, which may be grouped
        as strings (tick or double tick delimited) with embedded blanks.
        a non-string equal (=) acts as a delimiter between key-value pairs.

        the initial tokens are treated as args, followed by key-value pairs.

        Example:

            one 'two three' four=5 six='seven eight'

            parses to:

            args = ['one', 'two three']
            kwargs = {'four': '5', 'six': 'seven eight'}

        Return:

            args as list
            kwargs as dict

        Notes:

            1. Does not enforce args and keywords as valid python.

            2. String delimiters can be escaped (\) within strings.

            3. Key-value delimiters (=) can be surrounded by blanks.

            4. Designed for functionality, not speed
    """
    args = []
    kwargs = {}
    state = 'arg'
    for token in to_tokens(s):
        if state == 'arg':
            if token.is_key:
                key = token.value
                state = 'value'
            else:
                args.append(token.value)
        elif state == 'key':
            if not token.is_key:
                raise ExpectingKey(token.value)
            key = token.value
            if key in kwargs:
                raise DuplicateKey(key)
            state = 'value'
        elif state == 'value':
            if token.is_key:
                raise ConsecutiveKeys(token.value)
            kwargs[key] = token.value
            state = 'key'

    if state == 'value':
        raise IncompleteKeyValue(key)

    return args, kwargs
