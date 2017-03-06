import json

from spindrift.http import HTTPHandler


import logging
log = logging.getLogger(__name__)


class OutboundContext(object):

    def __init__(self, callback, method, host, path, headers=None, is_json=True, body=''):
        self.is_done = False
        self.callback = callback
        self.method = method
        self.host = host
        self.path = path
        self.headers = headers
        self.body = body if len(body) else ''
        self.is_json = is_json


class OutboundHandler(HTTPHandler):

    def done(self, result, rc=1):
        if not self.context.is_done:
            self.context.is_done = True
            self.context.callback(rc, result)
            self.close()

    def on_close(self, reason):
        self.done(reason)

    def on_ready(self):
        ctx = self.context
        self.send(method=ctx.method, host=ctx.host, resource=ctx.path, headers=ctx.headers, content=ctx.body)

    def on_http_data(self):
        self.context.is_done = True
        result = self.http_content
        if self.http_status_code >= 200 and self.http_status_code <= 299:
            rc = 0
            if self.context.is_json and len(result):
                result = json.loads(result)
        else:
            rc = 1
        self.done(result, rc)

    def on_timeout(self):
        self.close('timeout')
