import inspect
import logging
import time
import traceback

from spindrift.rest.connect import ConnectHandler
from spindrift.rest.handler import RESTHandler


log = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


class OutboundHandler(ConnectHandler):

    def after_init(self):
        kwargs = self.context.kwargs
        for k in kwargs.keys():
            if k not in ('is_debug', 'trace'):
                raise TypeError("connect() got an unexpected keyword argument '%s'", k)
        if kwargs.get('is_debug', False):
            log.debug('starting outbound connection, oid=%s: %s %s', self.id, self.context.method, self.context.url)

    def on_open(self):
        if self.context.is_debug:
            log.debug('open oid=%s: %s', self.id, self.full_address())

    def on_close(self, reason):
        kwargs = self.context.kwargs
        if kwargs.get('is_debug', False):
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
        super(OutboundHandler, self).on_close(None)

    def on_http_send(self, headers, content):
        kwargs = self.context.kwargs
        if kwargs.get('trace', False):
            log.debug('>>> %s %s' % (headers, content))

    def on_data(self, data):
        kwargs = self.context.kwargs
        if kwargs.get('trace', False):
            log.debug('<<< %s', data)
        self.timer.re_start()
        super(OutboundHandler, self).on_data(data)


class InboundHandler(RESTHandler):

    def on_request_call(self, request, fn, args, kwargs):
        """ inspect for 'cursor' in fn's parameters, and add if necessary and available """
        if hasattr(request, 'cursor') and 'cursor' not in kwargs:
            if 'cursor' in inspect.signature(fn).parameters:
                kwargs['cursor'] = request.cursor

    def on_open(self):
        log.info('open: cid=%d, %s', self.id, self.full_address)

    def on_close(self, reason):
        log.info('close: cid=%s, reason=%s, t=%.4f, rx=%d, tx=%d', getattr(self, 'id', '.'), reason, time.perf_counter() - self.t_init, self.rx_count, self.tx_count)

    def on_rest_data(self, request, *groups):
        log.info('request cid=%d, method=%s, resource=%s, query=%s, groups=%s', self.id, self.http_method, self.http_resource, self.http_query_string, groups)

    def on_rest_send(self, code, message, content, headers):
        log.debug('response cid=%d, code=%d, message=%s, headers=%s', self.id, code, message, headers)

    def on_rest_no_match(self):
        log.warning('no match cid=%d, method=%s, resource=%s', self.id, self.http_method, self.http_resource)

    def on_http_error(self):
        log.warning('http error cid=%d: %s', self.id, self.error)

    def on_rest_exception(self, exception_type, value, trace):
        log.exception('exception encountered:')
        return traceback.format_exc(trace)
