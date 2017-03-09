import json
import time

from spindrift.http import HTTPHandler


import logging
log = logging.getLogger(__name__)


class OutboundContext(object):

    def __init__(self, callback, url, method, host, path, headers, body, is_json, is_debug, timer):
        self.callback = callback
        self.url = url + path
        self.method = method
        body = body if len(body) else ''
        self.send = {'method': method, 'host': host, 'resource': path, 'headers': headers, 'content': body}
        self.is_json = is_json
        self.is_debug = is_debug
        self.timer = timer


class OutboundHandler(HTTPHandler):

    def on_init(self):
        self.is_done = False
        self.context.timer.set_action(self.on_timeout)
        self.context.timer.start()
        if self.context.is_debug:
            log.debug('starting outbound connection, oid=%s: %s %s', self.id, self.context.method, self.context.url)

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
        self.done(result, rc)

    def on_timeout(self):
        self.close('timeout')
