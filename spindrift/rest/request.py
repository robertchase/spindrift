import json
import urllib.parse as urlparse


import logging
log = logging.getLogger(__name__)


class RESTRequest(object):
    ''' First parameter passed to rest-handler routines

        When a rest.RESTHandler parses a new HTTP document, the document is matched
        to a function using a rest_mapper.RESTMapper. This object is the first argument
        passed to the matched function.

        This object provides access to these attributes on the http document:

            http_headers
            http_content
            http_method
            http_multipart
            http_resource
            http_query_string
            http_query

        It also provides access to a unique connection_id, and a json property which
        is the content as a json document, the query string, or the content as a query
        string, any of which is cast to a dict (or possibly a list, in the first case).

        These methods are available:

            delay - don't respond immediately to the connection peer, but wait for a
                    subsequent call to respond. this is helpful for async calls from
                    the rest handler function.

                    if this is not called, the response from the rest handler function is
                    treated as a response (as thought it were sent as *args to respond).

            respond(code=200, content='', headers=None, message=None, content_type=None) -
                    respond to the connection peer.

                    if content is one of type (dict, list, float, bool, int), then
                    content_type is changed to applicaton/json and the content translated
                    with json.dumps.

                    message will be derived for certain common codes. headers will generally
                    be automatically created by RESTHandler and HTTPHandler.

                    if the first parameter is not an int, then it is assumed that code=200,
                    and the first parameter is really content.
    '''
    def __init__(self, handler):
        self.handler = handler
        self.is_delayed = False

    def __getattr__(self, name):
        if name in ('id', 'http_headers', 'http_content', 'http_method', 'http_multipart', 'http_resource', 'http_query_string', 'http_query'):
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
