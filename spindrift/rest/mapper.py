'''
The MIT License (MIT)

https://github.com/robertchase/spindrift/blob/master/LICENSE.txt
'''
from collections import namedtuple
from itertools import zip_longest
import re

from ergaleia.config import _VALIDATE_MAP
from ergaleia.import_by_path import import_by_path

import logging
log = logging.getLogger(__name__)


class ArgumentCountMismatch(Exception):
    pass


class MissingRequiredContent(Exception):
    def __init__(self, key):
        msg = "missing required content: '{}'".format(key)
        super(MissingRequiredContent, self).__init__(msg)


class RESTArg(object):

    def __init__(self, type, name=None, is_required=True):
        self.name = name
        self.is_required = is_required

        if type in _VALIDATE_MAP:
            type = _VALIDATE_MAP[type]
        else:
            try:
                type = import_by_path(type)
            except Exception:
                raise Exception(
                    "unable to import validation function '{}'".format(type)
                )
        self.type = type


class RESTMethod(object):

    def __init__(self, handler, args=None, content=None):
        self.handler = import_by_path(handler)
        self.args = args or []
        self.content = content or []

    def add_arg(self, type):
        self.args.append(RESTArg(type))

    def add_content(self, name, type=None, is_required=True):
        self.content.append(RESTArg(type, name, is_required))

    def coerce(self, arg_data, content_data):
        args = []
        kwargs = {}

        if len(self.args) > len(arg_data):
            raise ArgumentCountMismatch()
        for coercer, arg in zip_longest(self.args, arg_data):
            if coercer:
                arg = coercer.type(arg)
            args.append(arg)

        for coercer in self.content:
            try:
                value = content_data[coercer.name]
            except KeyError:
                if coercer.is_required:
                    raise MissingRequiredContent(coercer.name)
            else:
                if coercer.type:
                    value = coercer.type(value)
                kwargs[coercer.name] = value

        return args, kwargs


RESTMatch = namedtuple('RESTMatch', ('handler', 'groups', 'coercer'))


class RESTMapper(object):
    ''' A Mapper between REST resource+method and a rest handler function
    '''

    def __init__(self):
        self._mapping = []

    def add(self, pattern, methods):
        """ add a mapping between a resource and one or more functions

            Arguments:

                pattern - regex matching resource (Note 1)
                methods - dict of RESTMethod objects (Note 2)

            Notes:
                1.  The pattern is a regex string which can include groups.
                    If groups are included in the regex, they will be passed
                    as arguments to the matching function.

                    The match method will evaluate each mapping in the order
                    that they are added. The first match wins.

                    For example:

                        add('/foo/(\d+)/bar', get=my_func)

                    will match:

                        GET /foo/123/bar HTTP/1.1

                    resulting in the following tuple from match:

                    (my_func, (123,))

                2. The methods dict is a set of RESTMethod objects indexed
                   by HTTP verb (lowercase get, post put, delete).
        """
        self._mapping.append(RESTMapping(pattern, methods))

    def match(self, resource, method):
        """ Match a resource + method to a RESTMethod

            The resource parameter is the resource string from the
            http status line, and the method parameter is the method from
            the http status line. The user shouldn't call this method, it
            is called by the on_http_status method of the RESTHandler.

            Step through the mappings in the order they were defined
            and look for a match on the regex which also has a method
            defined.
        """
        for mapping in self._mapping:
            m = mapping.pattern.match(resource)
            if m:
                rest_method = mapping.method.get(method.lower())
                if rest_method:
                    return RESTMatch(
                        rest_method.handler,
                        m.groups(),
                        rest_method.coerce,
                    )
        return None


class RESTMapping(object):
    ''' container for one mapping definition '''

    def __init__(self, pattern, methods):
        self.pattern = re.compile(pattern)
        self.method = methods
