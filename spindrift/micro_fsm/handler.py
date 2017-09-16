'''
The MIT License (MIT)

https://github.com/robertchase/spindrift/blob/master/LICENSE.txt
'''
import logging
import time
import traceback

from spindrift.rest.connect import ConnectHandler
from spindrift.rest.handler import RESTHandler
import spindrift.mysql.connection as mysql_connection


log = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


class OutboundHandler(ConnectHandler):

    def after_init(self):
        kwargs = self.context.kwargs
        for k in kwargs.keys():
            if k not in ('is_verbose', 'trace'):
                raise TypeError("connect() got an unexpected keyword argument '%s'", k)
        if kwargs.get('is_verbose', False):
            log.info('starting outbound connection, oid=%s: %s %s', self.id, self.context.method, self.context.url)

    def on_open(self):
        if self.context.is_verbose:
            log.info('open oid=%s: %s', self.id, self.full_address())

    def on_close(self, reason):
        kwargs = self.context.kwargs
        if kwargs.get('is_verbose', False):
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
            log.info(msg)
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

    def on_open(self):
        log.info('open: cid=%d, %s', self.id, self.full_address)

    def on_close(self, reason):
        log.info('close: cid=%s, reason=%s, t=%.4f, rx=%d, tx=%d', getattr(self, 'id', '.'), reason, time.perf_counter() - self.t_init, self.rx_count, self.tx_count)

    def on_rest_data(self, request, *groups):
        log.info('request cid=%d, method=%s, resource=%s, query=%s, groups=%s', self.id, self.http_method, self.http_resource, self.http_query_string, groups)

    def on_rest_send(self, code, message, content, headers):
        log.info('response cid=%d, code=%d, message=%s, headers=%s', self.id, code, message, headers)

    def on_rest_no_match(self):
        log.warning('no match cid=%d, method=%s, resource=%s', self.id, self.http_method, self.http_resource)

    def on_http_error(self):
        log.warning('http error cid=%d: %s', self.id, self.error)

    def on_rest_exception(self, exception_type, value, trace):
        log.exception('exception encountered:')
        return traceback.format_exc(trace)


class MysqlHandler(mysql_connection.MysqlHandler):

    def on_init(self):
        super(MysqlHandler, self).on_init()
        context = self.context
        self.timer = context.timer.add(self.on_timeout, context.timeout * 1000).start()
        self.cid = 0

    def on_open(self):
        log.debug('database open: cid=%s did=%d', self.cid, self.id)

    def on_timeout(self):
        log.warning('database timeout: cid=%s did=%d', self.cid, self.id)
        self.close('timeout')

    def on_close(self, reason):
        self.timer.cancel()
        log.debug('database close: cid=%s did=%s, reason=%s, t=%.4f, rx=%d, tx=%d', self.cid, self.id, reason, time.perf_counter() - self.t_init, self.rx_count, self.tx_count)
        super(MysqlHandler, self).on_close(reason)

    def on_fail(self, message):
        log.warning('database connection failed, cid=%s did=%s: %s', self.cid, self.id, message)

    def on_transaction_start(self):
        log.debug('database TRANSACTION START: cid=%s did=%d', self.cid, self.id)

    def on_transaction_end(self, end_type):
        log.debug('database transaction %s: cid=%s did=%d', end_type, self.cid, self.id)

    def on_query_start(self):
        self.t_query = time.perf_counter()
        log.debug('database query start: cid=%s did=%d: %s', self.cid, self.id, self.raw_query)

    def on_query_end(self):
        t = time.perf_counter() - self.t_query
        if t > self.context.long_query:
            log.warning('mysql long query: cid=%s did=%s, t=%.4f: %s', self.cid, self.id, t, self.raw_query)
        log.debug('database query end: cid=%s did=%s, t=%.4f', self.cid, self.id, t)
