import json
import sys
import types
import urllib.parse as urlparse

import spindrift.http as http

import logging
log = logging.getLogger(__name__)


class RESTRequest(object):

    def __init__(self, handler):
        self.handler = handler
        self.is_delayed = False

    def __getattr__(self, name):
        if name in ('http_headers', 'http_content', 'http_method', 'http_multipart', 'http_resource', 'http_query_string', 'http_query'):
            return getattr(self.handler, name)
        raise AttributeError('no attribute %s' % name)

    @property
    def connection_id(self):
        return self.handler.id

    def delay(self):
        self.is_delayed = True

    def respond(self, *args, **kwargs):
        if len(args) > 0 and not isinstance(args[0], int):
            self._respond(200, *args, **kwargs)
        else:
            self._respond(*args, **kwargs)

    def _respond(self, code=200, content='', headers=None, message=None, content_type=None):
        close = self.handler.http_headers.get('connection') == 'close'
        self.is_delayed = True  # prevent second response on handler return
        self.handler._rest_send(code, message, content, content_type, headers, close)

    @property
    def json(self):
        if not hasattr(self, '_json'):
            if self.http_content and self.http_content.lstrip()[0] in '[{':
                try:
                    self._json = json.loads(self.http_content)
                except Exception:
                    raise Exception('Unable to parse json content')
            elif len(self.http_query) > 0:
                self._json = self.http_query
            else:
                self._json = {n: v for n, v in urlparse.parse_qsl(self.http_content)}
        return self._json


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

    def on_http_status(self, method, resource):
        rest_handler, groups = self.context.match(resource, method)
        if rest_handler:
            self._rest_handler = rest_handler
            self._groups = groups
        else:
            self.on_rest_no_match()
            self._rest_send(404, 'Not Found')
            self.close('matching rest handler not found')

    def on_http_data(self):
        try:
            request = RESTRequest(self)
            self.on_rest_data(request, *self._groups)
            result = self._rest_handler(request, *self._groups)
            if not request.is_delayed:
                request.respond(result)
        except Exception:
            log.exception('eek')
            content = self.on_rest_exception(*sys.exc_info())
            kwargs = dict(code=501, message='Internal Server Error')
            if content:
                kwargs['content'] = str(content)
            self._rest_send(**kwargs)
            self.close('exception encountered')

    def on_rest_data(self, request, *groups):
        ''' called before rest_handler execution '''
        pass

    def on_rest_no_match(self):
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

    def _rest_send(self, code, message, content='', content_type=None, headers=None, close=False):

        if isinstance(content, (dict, list, float, bool, int)):
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
        self.send_server(**args)

    def on_rest_send(self, code, message, content, headers):
        pass
