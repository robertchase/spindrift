'''
The MIT License (MIT)

https://github.com/robertchase/spindrift/blob/master/LICENSE.txt
'''
import json
from socket import gethostbyname
import time
import urllib.parse as urllib

from spindrift.http import HTTPHandler


import logging
log = logging.getLogger(__name__)


def connect(
            network,
            timer,
            callback,
            url,
            query=None,
            method='GET',
            body=None,
            headers=None,
            is_json=True,
            is_form=False,
            timeout=5.0,
            wrapper=None,
            evaluate=None,
            handler=None,
            debug=False,
            trace=False,
            **kwargs
        ):
    """ Make an async rest connection, executing callback on completion

        Parameters:

            network  - instance of spindrift.network.Network
            timer    - instance of spindrift.timer.Timer
            callback - a callable expecting (rc, result), where rc=0 on success
            url      - full url of the resource being referenced
                       can include query string
            query    - optional query string
                       if dict, urlencoded to string
            method   - http method (default=GET)
            body     - http content (default=None)
            headers  - http headers as dict (default=None)
            is_json  - if True, successful result is json.loads-ed
                       (default=True)
            is_form  - send content as applicaton/x-www-form-urlencoded
            timeout  - tolerable period of network inactivity in seconds
                       (default=5.0)
                       on timeout, callback is invoked with (1, 'timeout')
            wrapper  - callable for wrapping successful result
                       called with result before callback
                       (default=None)
            handler  - handler class for connection (default=None)
                       subclass of ConnectHandler
            evaluate - callable for http response evaluation (default=None)
                       returns result or raises Exception
                       (see ConnectHandler.evaluate)
            debug    - log debug messages on start/open/close
            trace    - log debug sent and recv'd http data
            kwargs   - additional keyword args that might be useful in a
                       ConnectHandler subclass

        Notes:

            1. If body is a dict and method is GET, then the contents of dict
               are added to the query string and body is cleared.
    """
    if query is not None:
        if isinstance(query, dict):
            query = urllib.urlencode(query)
        url = '{}?{}'.format(url, query)
    p = URLParser(url)
    return connect_parsed(network, timer, callback, url, p.host, p.address,
                          p.port, p.path, p.query, p.is_ssl, method, headers,
                          body, is_json, is_form, timeout, wrapper, handler,
                          evaluate, debug, trace, **kwargs)


def connect_parsed(
            network,
            timer,
            callback,
            url,
            host,
            address,
            port,
            path,
            query,
            is_ssl,
            method,
            headers,
            body,
            is_json,
            is_form,
            timeout,
            wrapper,
            handler,
            evaluate,
            debug,
            trace,
            **kwargs
        ):
    c = ConnectContext(callback, timer, url, method, path, query, host,
                       headers, body, is_json, is_form, timeout, wrapper,
                       evaluate, debug, trace, kwargs)
    return network.add_connection(address, port, handler or ConnectHandler, c,
                                  is_ssl=is_ssl)


class ConnectContext(object):

    def __init__(
                self,
                callback,
                timer,
                url,
                method,
                path,
                query,
                host,
                headers,
                body,
                is_json,
                is_form,
                timeout,
                wrapper,
                evaluate,
                is_debug,
                is_trace,
                kwargs
            ):
        self.callback = callback
        self.timer = timer
        self.url = url
        self.method = method
        self.path = path
        self.query = query
        self.host = host
        self.headers = headers
        self.body = body
        self.content_type = 'form' if is_form else 'text/html'
        self.is_json = is_json
        self.timeout = timeout
        self.wrapper = wrapper
        self.evaluate = evaluate
        self.is_debug = is_debug
        self.is_trace = is_trace
        self.kwargs = kwargs


class ConnectHandler(HTTPHandler):
    """ Manage outgoing http request as defined by context
    """

    def on_init(self):
        self.is_done = False
        self.is_success = False
        self.is_timeout = False
        self.setup()
        self.check_kwargs()
        self.timer = self.context.timer.add(
            self.on_timeout, self.context.timeout * 1000
        ).start()
        self.after_init()

    def check_kwargs(self):
        kwargs = self.context.kwargs
        if len(kwargs) > 0:
            raise TypeError(
                'connect() received unexpected keyword argument(s): %s' %
                str(tuple(kwargs.keys()))
            )

    def after_init(self):
        if self.context.is_debug:
            log.debug(
                'starting outbound connection, oid=%s: %s %s',
                self.id,
                self.context.method,
                self.context.url,
            )

    def setup(self):
        context = self.context

        if isinstance(context.body, dict) and context.method == 'GET':
            query = urllib.parse_qs(context.query)
            query.update(context.body)
            context.query = urllib.urlencode(context.body)
            context.body = None

        if context.path == '':
            context.path = '/'

        if context.query:
            context.path = context.path + '?' + context.query

        if isinstance(context.body, (dict, list, tuple, float, bool, int)):
            try:
                json.dumps(context.body)
            except Exception:
                context.body = str(context.body)
            else:
                context.content_type = 'json'

        if context.body is None:
            context.body = ''

    def done(self, result, rc=0):
        if self.is_done:
            return
        self.is_done = True
        if not self.is_success:
            rc = 1
        self.timer.cancel()
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
        '''
            send http request to peer using values from context
        '''
        self.timer.re_start()
        context = self.context
        self.http_send(
            method=context.method,
            host=context.host,
            resource=context.path,
            headers=context.headers,
            content=context.body,
            content_type=context.content_type,
            close=True,
        )

    def on_data(self, data):
        self.timer.re_start()
        super(ConnectHandler, self).on_data(data)

    def evaluate(self):
        """ evaluate http response document

            examines http status code, raising an Exception if not in
            the 200-299 range.

            Return:

                if method is HEAD, http_headers
                otherwise http_content

            Notes:

                1. can be overridden by a subclass, or by specifying the
                   evaluate argument to the connect function.
        """
        if self.context.method == 'HEAD':
            result = self.http_headers
        else:
            result = self.http_content
        status = self.http_status_code
        if status < 200 or status > 299:
            raise Exception(result or self.http_status_message)
        return result

    def on_http_data(self):

        if self.context.is_trace:
            log.debug('recv: %s', self.http_message)

        try:
            evaluate = self.context.evaluate or self.__class__.evaluate
            result = evaluate(self)
        except Exception as e:
            return self.done(str(e), 1)

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
        self.is_success = True

        self.done(result)

    def on_fail(self, message):
        self.done(message, 1)

    def on_http_error(self, message):
        self.done(message, 0)

    def on_timeout(self):
        self.is_timeout = True
        self.done('timeout', 1)

    def on_http_send(self, headers, content):
        if self.context.is_trace:
            log.debug('send: %s', headers)
            if len(content):
                log.debug('send: %s', content)


def run(network, timer, command, sleep=100, max_iterations=100):
    """ service network and timer until command.is_done is True """
    while not command.is_done:
        network.service(timeout=sleep/1000.0, max_iterations=max_iterations)
        timer.service()


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
