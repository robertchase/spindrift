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

        It also provides access to a unique connection id, and a json property which
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
        self.response = None
        self.is_done = False
        self._cleanup = []

    def __getattr__(self, name):
        if name in ('id', 'http_headers', 'http_content', 'http_method', 'http_multipart', 'http_resource', 'http_query_string', 'http_query'):
            return getattr(self.handler, name)
        super(RESTRequest, self).__getattribute__(name)

    def __setattr__(self, name, value):
        if name == 'cleanup':
            self._cleanup.append(value)
        else:
            super(RESTRequest, self).__setattr__(name, value)

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
        if not self.is_done:
            self.is_done = True
            close = self.handler.http_headers.get('connection') == 'close'
            self.is_delayed = True  # prevent second response on handler return
            self.handler._rest_send(code, message, content, content_type, headers, close)
            for cleanup in self._cleanup[::-1]:
                cleanup()

    def call(self, fn, args=None, kwargs=None, on_success=None, on_success_code=None, on_error=None, on_none=None, on_none_404=False):
        """ Call an async function.

        Allows for flexible handling of the return states of async function calls.

        Parameters:
            fn - callable async function (See Note 1)

            args - None, scalar, tuple or list
                Positional argments to be passed to fn.

            kwargs - None or dict
                Keyword argments to be passed to fn.

            on_success - callable
                called if specified and rc == 0 and
                if none of on_success_code, on_none and on_none_404 apply
                    on_success(request, result)

            on_success_code - int
                if specified and rc == 0 and
                if neither of on_none or on_none_404 apply
                    callback(int)

            on_error - callable
                called if specified and rc != 0
                    on_error(request, result)

            on_none - callable
                called if specified and rc == 0 and result is None and
                if on_none_404 does not apply
                    on_none(request, None)

            on_none_404 - boolean
                if specified and rc == 0 and result is None:
                    callback(404)

        Notes:

            1.  An async function is structured like this:

                    fn(callback, *args, **kwargs)

                When the function is complete, it calls callback with two parameters:

                    rc - 0 for success, non-zero for error
                    result - function response on success, message on error

        Example:

            def on_load(request, result):
                pass

            request.call(
                load,
                args=id,
                on_success=on_load,
                on_none_404=True,
            )

            This will call the load function, followed by on_load if the load
            function completes sucessfully. If load produces a None result,
            then the request will be responded to with a 404 Not Found.
        """

        def cb(rc, result):
            if rc == 0:
                _callback(self, result, on_success, on_success_code, on_none, on_none_404)
            else:
                _callback_error(self, result, on_error)

        if args is None:
            args = ()
        elif not isinstance(args, (list, tuple)):
            args = (args,)
        if kwargs is None:
            kwargs = {}

        self.delay()

        self.handler.on_request_call(self, fn, args, kwargs)
        fn(cb, *args, **kwargs)

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


def _callback(request, result, on_success, on_success_code, on_none, on_none_404):
    if result is None and on_none_404:
        request.respond(404)
    elif result is None and on_none:
        try:
            on_none(request, None)
        except Exception:
            log.exception('running on_none callback')
            request.respond(500)
    elif on_success_code:
        request.respond(on_success_code)
    elif on_success:
        try:
            on_success(request, result)
        except Exception:
            log.exception('running on_success callback')
            request.respond(500)
    else:
        request.respond(200, request.response or result)


def _callback_error(request, result, on_error):
    if on_error:
        try:
            on_error(request, result)
        except Exception:
            log.exception('running on_error callback: %s', result)
            request.respond(500)
    else:
        log.warning('cid=%s, error: %s', request.id, result)
        request.respond(500)
