'''
The MIT License (MIT)

https://github.com/robertchase/spindrift/blob/master/LICENSE.txt
'''
import re

from ergaleia.import_by_path import import_by_path

import logging
log = logging.getLogger(__name__)


class RESTMapper(object):
    ''' A Mapper between REST resource+method and a rest handler function
    '''

    def __init__(self):
        self._mapping = []

    def add(self, pattern, get=None, post=None, put=None, delete=None):
        '''
            Add a mapping between a resource and one or more functions.

            The pattern is a regex string which can include groups. If
            groups are included in the regex, they will be passed as
            parameters to the matching function.

            The match method will evaluate each mapping in the order
            that they are added. The first match wins.

            For example:

                add('/foo/(\d+)/bar', get=my_func)

                will match:

                    GET /foo/123/bar HTTP/1.1

                resulting in the following tuple from match:

                    (my_func, (123,))
        '''
        self._mapping.append(RESTMapping(pattern, get, post, put, delete))

    def match(self, resource, method):
        '''
            Match a resource + method to a RESTMapping

            The resource parameter is the resource string from the
            http status line, and the method parameter is the method from
            the http status line. The user shouldn't call this method, it
            is called by the on_http_status method of the RESTHandler.

            Step through the mappings in the order they were defined
            and look for a match on the regex which also has a method
            defined.
        '''
        for mapping in self._mapping:
            m = mapping.pattern.match(resource)
            if m:
                handler = mapping.method.get(method.lower())
                if handler:
                    return handler, m.groups()
        return None, None


class RESTMapping(object):
    ''' container for one mapping definition '''

    def __init__(self, pattern, get, post, put, delete):
        self.pattern = re.compile(pattern)
        self.method = {
            'get': import_by_path(get),
            'post': import_by_path(post),
            'put': import_by_path(put),
            'delete': import_by_path(delete),
        }
