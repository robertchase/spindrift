'''
The MIT License (MIT)

Copyright (c) 2013-2017 Robert H Chase

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
'''
import json
from socket import gethostbyname
import urllib.parse as urllib

from spindrift.http import HTTPHandler


import logging
log = logging.getLogger(__name__)


def connect(network, timer, callback, url, method='GET', body=None, headers=None, is_json=True, timeout=5.0, wrapper=None, handler=None, **kwargs):
    '''
        Make an async rest connection, executing callback on completion

        Parameters:

            network - instance of spindrift.network.Network
            timer - instance of spindrift.timer.Timer
            callback - a callable expecting (rc, result), where rc=0 on success
            url - full url of the resource being referenced
            method - http method (default=GET)
            body - http content (default=None)
            headers - http headers as dict (default=None)
            is_json - if True, successful result is json.loads-ed (default=True)
            timeout - tolerable period of network inactivity in seconds (default=5.0)
                      on timeout, callback is invoked with (1, 'timeout')
            wrapper - if successful, wrap result in wrapper before callback (default=None)
            handler - handler class for connection (default=None)
                      subclass of ConnectHandler
            kwargs - additional keyword args that might be useful in a ConnectHandler subclass

        Notes:

            1. If body is a dict and method is GET, then the contents of dict are added
               to the query string and body is cleared.
    '''
    p = URLParser(url)
    return connect_parsed(network, timer, callback, url, p.host, p.address, p.port, p.path, p.query, p.is_ssl, method, headers, body, is_json, timeout, wrapper, handler, **kwargs)


def connect_parsed(network, timer, callback, url, host, address, port, path, query, is_ssl, method, headers, body, is_json, timeout, wrapper, handler, **kwargs):
    c = ConnectContext(callback, timer, url, method, path, query, host, headers, body, is_json, timeout, wrapper, kwargs)
    return network.add_connection(address, port, handler or ConnectHandler, c, is_ssl=is_ssl)


class ConnectContext(object):

    def __init__(self, callback, timer, url, method, path, query, host, headers, body, is_json, timeout, wrapper, kwargs):
        self.callback = callback
        self.timer = timer
        self.url = url
        self.method = method
        self.path = path
        self.query = query
        self.host = host
        self.headers = headers
        self.body = body
        self.is_json = is_json
        self.is_debug = False
        self.timeout = timeout
        self.wrapper = wrapper
        self.kwargs = kwargs


class ConnectHandler(HTTPHandler):
    """ Manage outgoing http request as defined by context
    """

    def on_init(self):
        self.is_done = False
        self.is_timeout = False
        self.setup()
        self.after_init()

    def after_init(self):
        kwargs = self.context.kwargs
        if len(kwargs) > 0:
            raise TypeError('connect() received unexpected keyword argument(s): %s' % str(tuple(kwargs.keys())))

    def setup(self):
        context = self.context

        if context.headers and context.headers.get('Content-Type') == 'application/x-www-form-urlencoded' and isinstance(context.body, dict):
            context.body = urllib.urlencode(context.body)

        if context.method == 'GET' and isinstance(context.body, dict):
            query = urllib.parse_qs(context.query)
            query.update(context.body)
            context.query = urllib.urlencode(context.body)
            context.body = None

        if context.path == '':
            context.path = '/'

        context.path = context.path + ('?%s' % context.query if context.query else '')

        if isinstance(context.body, (dict, list, tuple, float, bool, int)):
            try:
                context.body = json.dumps(context.body)
            except Exception:
                context.body = str(context.body)
            else:
                if context.headers is None:
                    context.headers = {}
                context.headers['Content-Type'] = 'application/json; charset=utf-8'

        if context.body is None:
            context.body = ''
        self.timer = self.context.timer.add(self.on_timeout, self.context.timeout * 1000).start()

    def done(self, result, rc=0):
        if self.is_done:
            return
        self.is_done = True
        self.timer.cancel()
        self.context.callback(rc, result)
        self.close('transaction complete')

    def on_close(self, reason):
        self.done(None)

    def on_failed_handshake(self, reason):
        log.warning('ssl error cid=%s: %s', self.id, reason)

    def on_ready(self):
        '''
            send http request to peer using values from context
        '''
        self.timer.re_start()
        context = self.context
        self.send(
            method=context.method,
            host=context.host,
            resource=context.path,
            headers=context.headers,
            content=context.body,
            close=True,
        )

    def on_data(self, data):
        self.timer.re_start()
        super(ConnectHandler, self).on_data(data)

    def evaluate(self):
        status = self.http_status_code
        result = self.http_headers if self.context.method == 'HEAD' else self.http_content
        if status < 200 or status >= 300:
            return self.done(self.http_status_message if result == '' else result, 1)
        return result

    def on_http_data(self):
        result = self.evaluate()
        if self.is_done:
            return

        if self.context.is_json and result is not None and len(result):
            try:
                result = json.loads(result)
            except Exception as e:
                return self.done(str(e), 1)

        if self.context.wrapper and result is not None:
            try:
                result = self.context.wrapper(result)
            except Exception as e:
                self.done(str(e), 1)

        self.done(result)

    def on_fail(self):
        self.done(self.close_reason, 1)

    def on_http_error(self):
        self.done('http error', 1)

    def on_timeout(self):
        self.is_timeout = True
        self.done('timeout', 1)


class URLParser(object):

    def __init__(self, url):

        u = urllib.urlparse(url)
        self.is_ssl = u.scheme == 'https'
        if ':' in u.netloc:
            self.host, self.port = u.netloc.split(':', 1)
            self.port = int(self.port)
        else:
            self.host = u.netloc
            self.port = 443 if self.is_ssl else 80
        self.address = gethostbyname(self.host)
        self.resource = u.path + ('?%s' % u.query if u.query else '')
        self.path = u.path
        self.query = u.query
