'''
The MIT License (MIT)

https://github.com/robertchase/spindrift/blob/master/LICENSE.txt
'''
import json
import sys

import spindrift.http as http
import spindrift.rest.request as rest_request

import logging
log = logging.getLogger(__name__)


class RESTContext(object):

    def __init__(self, mapper):
        self.mapper = mapper


class RESTHandler(http.HTTPHandler):
    '''
        Identify and execute REST handler functions.

        Incoming connections are parsed as HTTP documents and handled by functions
        which match on resource (URI path component) and method (GET, PUT, POST, DELETE).

        Callback methods:
            on_rest_data(self, *groups)
            on_rest_exception(self, exc_type, exc_value, exc_traceback)
            on_rest_send(self, code, message, content, headers)
    '''

    def _map(self, resource, method):
        mapper = self.context.mapper
        return mapper.match(resource, method)

    def on_http_status(self, method, resource):
        rest_match = self._map(resource, method)
        if rest_match:
            self._rest_handler = rest_match.handler
            self._groups = rest_match.groups
            self._coercer = rest_match.coercer
        else:
            self.on_rest_no_match()
            self._rest_send(404, 'Not Found', close=True)

    def on_http_data(self):
        try:
            self.on_rest_data(self._groups)
            request = rest_request.RESTRequest(self)
            request = self.on_rest_request(request)
            try:
                args, kwargs = self._coercer(
                    self._groups, request.json
                )
            except Exception as e:
                log.warning(e)
                return request.respond(400)
            result = self._rest_handler(request, *args, **kwargs)
            if request.is_done:  # already responded
                pass
            elif not request.is_delayed:
                request.respond(result)
        except Exception:
            content = self.on_rest_exception(*sys.exc_info())
            kwargs = dict(code=501, message='Internal Server Error')
            if content:
                kwargs['content'] = str(content)
            self._rest_send(**kwargs, close=True)

    def on_rest_data(self, groups):
        ''' called before rest_handler execution '''
        pass

    def on_rest_request(self, request):
        ''' called after rest_request creation '''
        return request

    def on_request_call(self, request, fn, args, kwargs):
        ''' chance to amend kwargs on request.call '''
        pass

    def on_rest_no_match(self):
        ''' called when resource+method does not match anything in the mapper '''
        pass

    def on_rest_exception(self, exception_type, exception_value, exception_traceback):
        ''' handle Exception raised during REST processing

        If a REST handler raises an Exception, this method is called with the sys.exc_info
        tuple to allow for logging or any other special handling.

        If a value is returned, it will be sent as the content in the
        "501 Internal Server Error" response.

        To return a traceback string in the 501 message:
            import traceback
            return traceback.format_exc(exception_traceback)
        '''
        return None

    def _rest_send(self, code, message=None, content='', content_type=None, headers=None, close=False):

        if isinstance(content, (dict, list, tuple)):
            try:
                content = json.dumps(content)
                content_type = 'application/json; charset=utf-8'
            except Exception:
                content = str(content)

        if content_type:
            if not headers:
                headers = {}
            headers['Content-Type'] = content_type

        if not message:
            message = {
                200: 'OK',
                201: 'Created',
                204: 'No Content',
                302: 'Found',
                400: 'Bad Request',
                401: 'Unauthorized',
                403: 'Forbidden',
                404: 'Not Found',
                500: 'Internal Server Error',
            }.get(code, '')

        args = dict(code=code, message=message, close=close)
        if content:
            args['content'] = content
        if headers:
            args['headers'] = headers
        self.on_rest_send(code, message, content, headers)
        self.http_send_server(**args)

    def on_rest_send(self, code, message, content, headers):
        pass
