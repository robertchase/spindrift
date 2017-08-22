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

            call(self, fn, args=None, kwargs=None, on_success=None, on_error=None,
                    on_none=None, on_none_404=False) - call an asnyc function providing
                    callbacks for various cases.

                    fn - a function taking a callback_fn as the first argument followed by
                    *args and **kwargs. a callback_fn takes two arguments: rc and result.
                    if rc == 0, the async function completed sucessfully and the result is
                    the appropriate return from the async function; if rc != 0, the async
                    function did not finsh successfully, and result contains a message.

                    args - arguments to fn or None. if scalar, a list is implied.

                    kwargs - keyword args to fn or None.

                    on_none_404, if specified as True, automatically calls
                    request.respond(404) if rc == 0 and result is None. the rest handler
                    is finished.

                    on_none, if specified, is called if rc == 0 and result is None and
                    on_none_404 is not specified.
                        called with (request, result)

                    on_success, if specified, is called if rc == 0 and result is not None,
                    or rc == 0 and on_none_404 and on_none are not specified.
                        called with (request, result)

                    if rc == 0 and none of (on_success, on_none or on_none_404) is specified,
                    then request.respond(200, result) is called. if request.response it not
                    None, then request.response is sent instead of result. the rest handler
                    is finished.

                    on_error, if specified, is called if rc != 0.
                        called with (1, result)

                    if rc != 0 and on_error is not specified, then a warning is logged with
                    result and request.respond(500) is called.
    '''
    def __init__(self, handler):
        self.handler = handler
        self.is_delayed = False
        self.response = None

    def __getattr__(self, name):
        if name in ('id', 'http_headers', 'http_content', 'http_method', 'http_multipart', 'http_resource', 'http_query_string', 'http_query'):
            return getattr(self.handler, name)
        super(RESTRequest, self).__getattribute__(name)

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

    def call(self, fn, args=None, kwargs=None, on_success=None, on_error=None, on_none=None, on_none_404=False):
        """
        Call an async function.

        This function allows flexible handling of the return states of async function
        calls.

        Parameters
        ----------
        fn - callable async function
            fn takes a callback_fn along with args & kwargs. A callback function takes
            two parameters (rc, result), where rc == 0 if the call to fn is successful,
            and rc != 0 if the call to fn failed. The result parameter is the return
            value from fn, or a message if rc != 0.

        args - None, scalar, tuple or list
            Positional argments to be passed to fn.

        kwargs - None or dict
            Keyword argments to be passed to fn.

        on_success - callable

        on_error - callable

        on_none - callable

        on_none_404 - boolean

        Returns
        -------
        None
        """

        def cb(rc, result):
            _callback(self, rc, result, on_success, on_error, on_none, on_none_404)

        if args is None:
            args = ()
        elif not isinstance(args, (list, tuple)):
            args = (args,)
        if kwargs is None:
            kwargs = {}

        self.delay()

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


def _callback(request, rc, result, on_success, on_error, on_none, on_none_404):
    if rc == 0:
        if result is None and on_none_404:
            request.respond(404)
        elif result is None and on_none:
            try:
                on_none(request)
            except Exception:
                log.exception('running on_none callback')
                request.respond(500)
        elif on_success:
            try:
                on_success(request, result)
            except Exception:
                log.exception('running on_success callback')
                request.respond(500)
        else:
            request.respond(200, request.response or result)
    else:
        if on_error:
            try:
                on_error(request, result)
            except Exception:
                log.exception('running on_error callback: %s', result)
                request.respond(500)
        else:
            log.warning('cid=%s, error: %s', request.id, result)
            request.respond(500)
