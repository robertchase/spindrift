import json
import time
import traceback

from spindrift.http import HTTPHandler
from spindrift.import_utils import import_by_pathname
from spindrift.rest.handler import RESTHandler, RESTContext


import logging
log = logging.getLogger(__name__)


class OutboundContext(object):

    def __init__(self, callback, micro, config, url, method, host, path, headers, body, is_json, is_debug, api_key, wrapper, timer, **kwargs):
        self.callback = callback
        self.micro = micro
        self.config = config
        self.url = url + path
        self.method = method
        self.host = host
        self.path = path
        self.headers = headers
        self.body = body
        self.is_json = is_json
        self.is_debug = is_debug
        self.api_key = api_key
        self.wrapper = wrapper
        self.timer = timer
        self.kwargs = kwargs


class OutboundHandler(HTTPHandler):

    def on_init(self):
        self.is_done = False
        self.setup()
        self.context.timer.set_action(self.on_timeout)
        self.context.timer.start()
        if self.context.is_debug:
            log.debug('starting outbound connection, oid=%s: %s %s', self.id, self.context.method, self.context.url)

    def setup(self):
        context = self.context

        # coerce remaining kwargs into body, if body not defined
        if context.body is None:
            if len(context.kwargs) == 0:
                context.body = ''
            else:
                context.body = context.kwargs

        # jsonify body, if it makes sense
        if isinstance(context.body, (dict, list, tuple, float, bool, int)):
            try:
                context.body = json.dumps(context.kwargs)
            except Exception:
                context.body = str(context.kwargs)
            else:
                if context.headers is None:
                    context.headers = {}
                context.headers['Content-Type'] = 'application/json; charset=utf-8'

        # setup api key
        if context.api_key:
            if context.headers is None:
                context.headers = {}
            context.headers['X-Auth-API-Key'] = context.api_key

        # create arguments for send
        context.send = {'method': context.method, 'host': context.host, 'resource': context.path, 'headers': context.headers, 'content': context.body}

    def done(self, result, rc=1):
        if self.is_done:
            return
        self.is_done = True
        self.context.timer.cancel()
        self.context.callback(rc, result)
        self.close('transaction complete')

    def on_open(self):
        if self.context.is_debug:
            log.debug('open oid=%s: %s', self.id, self.full_address)

    def on_close(self, reason):
        if self.context.is_debug:
            now = time.perf_counter()
            msg = 'close oid=%s, reason=%s, opn=%.4f,' % (
                self.id,
                reason,
                (self.t_open - self.t_init) if self.t_open else 0,
            )
            if self.is_ssl:
                msg += ' rdy=%.4f,' % (
                    (self.t_ready - self.t_init) if self.t_ready else 0,
                )
            msg += ' dat=%.4f, tot=%.4f, rx=%d, tx=%d' % (
                (self.t_http_data - self.t_init) if self.t_http_data else 0,
                now - self.t_init,
                self.rx_count,
                self.tx_count,
            )
            if self.is_ssl:
                msg += ', ssl handshake=%s' % (
                    'success' if self.t_ready else 'fail',
                )
            log.debug(msg)
        self.done(reason)

    def on_failed_handshake(self, reason):
        log.warning('ssl error cid=%s: %s', self.id, reason)

    def on_ready(self):
        self.context.timer.re_start()
        self.send(**self.context.send)

    def on_data(self, data):
        self.context.timer.re_start()
        super(OutboundHandler, self).on_data(data)

    def on_http_data(self):
        result = self.http_content
        if self.http_status_code >= 200 and self.http_status_code <= 299:
            rc = 0
            if self.context.is_json and len(result):
                try:
                    result = json.loads(result)
                except Exception as e:
                    rc = 1
                    result = str(e)
        else:
            rc = 1
            if result == '':
                result = self.http_status_message

        if rc == 0 and self.context.wrapper:
            wrap = import_by_pathname(self.context.wrapper)
            result = wrap(result)

        self.done(result, rc)

    def on_timeout(self):
        self.close('timeout')


class InboundContext(RESTContext):

    def __init__(self, mapper, micro, api_key=None):
        super(InboundContext, self).__init__(mapper)
        self.micro = micro
        self.api_key = api_key


class InboundHandler(RESTHandler):

    def on_open(self):
        log.info('open: cid=%d, %s', self.id, self.full_address)

    def on_close(self, reason):
        log.info('close: cid=%s, reason=%s', self.id, reason)

    def check_api_key(self):
        api_key = self.context.api_key
        if api_key:
            if api_key == self.http_headers.get('x-auth-api-key'):
                return True
            log.warning('api key failure cid=%s', self.id)
            return False
        return True

    def on_http_headers(self):
        if not self.check_api_key():
            self._rest_send(401)
            self.close('api key mismatch')

    def on_rest_data(self, *groups):
        log.info('request cid=%d, method=%s, resource=%s, query=%s, groups=%s', self.id, self.http_method, self.http_resource, self.http_query_string, groups)

    def on_rest_request(self, request):
        request.micro = self.context.micro
        return request

    def on_rest_send(self, code, message, content, headers):
        log.debug('response cid=%d, code=%d, message=%s, headers=%s', self.id, code, message, headers)

    def on_rest_no_match(self):
        log.warning('no match cid=%d, method=%s, resource=%s', self.id, self.http_method, self.http_resource)

    def on_http_error(self, message):
        log.warning('http error cid=%d: %s', self.id, message)

    def on_rest_exception(self, exception_type, value, trace):
        log.exception('exception encountered:')
        return traceback.format_exc(trace)
