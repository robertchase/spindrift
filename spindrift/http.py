from network import Handler

from io import StringIO
import time
from urllib.parse import urlparse
import gzip

import logging
log = logging.getLogger(__name__)


class HTTPHandler(Handler):

    def on_init(self):
        '''
            Handler for an HTTP connection.

                available variables (on_http_data)

                    http_headers - dictionary of headers
                    http_content - content

                    client:
                        http_status_code - integer code from status line
                        http_status_message - message from status line

                    server:
                        http_method - method from status line
                        http_multipart - list of HTTPPart objects
                        http_resource - resource from status line
                        http_query_string - unmodified query string
                        http_query - dict of query string
                        charset - encoding from Content-Type header or None

                        if charset:
                            http_content: decoded http_content

                on_http_status(self, method, resource):bool - (server) when status line is available, return False to stop processing
                on_http_send(self, headers, content) - useful for debugging
                on_http_data(self) - when data is available
                on_http_error(self, message)
        '''
        self._data = b''
        self._setup()

        self.http_max_content_length = None
        self.http_max_line_length = 10000
        self.http_max_header_count = 100

        self._http_close_on_complete = False

    @property
    def charset(self):
        h = self.http_headers.get('Content-Type')
        if h:
            charset = [c.split('=')[1].strip() for c in h.split(';') if 'charset' in c]
            if len(charset):
                return charset[0]
        return None

    def on_http_send(self, headers, content):
        pass

    def on_http_status(self, method, resource):
        return True

    def on_http_data(self):
        pass

    def on_http_error(self, message):
        pass

    def _multipart(self):
        cache = self._data
        try:
            self.http_headers['Content-Type'], boundary = self.http_headers['Content-Type'].split('; boundary=')
            for self._data in [p[2:] for p in self.http_content.split('--' + boundary)][1:-1]:  # split, remove \r\n and ignore first & last; stuff into _data for _line
                headers = dict(l.split(': ', 1) for l in iter(self._line, ''))
                if 'Content-Disposition' in headers:
                    headers['Content-Disposition'], rem = headers['Content-Disposition'].split('; ', 1)
                    disposition = dict(part.split('=', 1) for part in rem.split('; '))
                self.http_multipart.append(HTTPPart(headers, disposition, self._data))
        except Exception:
            self.__error('Malformed multipart message')
        self._data = cache

    def _on_http_data(self):
        if self.http_headers.get('Content-Encoding') == 'gzip':
            self.http_content = gzip.GzipFile(fileobj=StringIO(self.http_content)).read()
        if self.http_headers.get('Content-Type', '').startswith('multipart'):
            self._multipart()
        if self.charset:
            self.http_content = self.http_content.decode(self.charset)
        self.on_http_data()

    def on_send_complete(self):
        if self.__http_close_on_complete:
            self.close()

    def __send(self, headers, content):
        self.on_http_send(headers, content)
        data = headers + content if content else headers
        data = data.encode('utf-8')
        super(HTTPHandler, self).send(data)

    def send(self, method='GET', host=None, resource='/', headers=None, content='', close=False, compress=False):

        self._http_method = method

        if not headers:
            headers = {}

        if 'Date' not in headers:
            headers['Date'] = time.strftime(
                "%a, %d %b %Y %H:%M:%S %Z", time.localtime())

        if 'Content-Length' not in headers:
            headers['Content-Length'] = len(content)

        if close:
            headers['Connection'] = 'close'

        if compress:
            headers['Accept-Encoding'] = 'gzip'

        if 'host' not in (k.lower() for k in headers):
            headers['Host'] = host if host else '%s:%s' % self.peer_address

        headers = '%s %s HTTP/1.1\r\n%s\r\n\r\n' % (
            method, resource, '\r\n'.join(['%s: %s' % (k, v) for k, v in headers.items()])
        )

        self.__send(headers, content)

    def send_server(self, content='', code=200, message='OK', headers=None, close=False):

        self.__http_close_on_complete = True if close else self.http_headers.get('Connection') == 'close'

        if headers is None:
            headers = {}

        if 'Date' not in headers:
            headers['Date'] = time.strftime(
                "%a, %d %b %Y %H:%M:%S %Z", time.localtime())

        if 'Content-Length' not in headers:
            headers['Content-Length'] = len(content)

        headers = 'HTTP/1.1 %d %s\r\n%s\r\n\r\n' % (
            code, message,
            '\r\n'.join(['%s: %s' % (k, v) for k, v in headers.items()]))

        self.__send(headers, content)

    def _setup(self):
        self.http_headers = {}
        self.http_content = ''
        self.http_status_code = None
        self.http_status_message = None
        self.http_method = None
        self.http_multipart = []
        self.http_resource = None
        self.http_query_string = None
        self.http_query = {}
        self.__state = self.__status

    def on_http_headers(self):
        ''' a chance to terminate connection if headers don't check out

            to indicate a problem:
                return 1, 'error message'
        '''
        return 0, None

    def on_data(self, data):
        self._data += data
        while self.__state():
            pass

    def _on_http_error(self, message):
        self.on_http_error(message)
        self.close('http error')
        return False

    def __error(self, message):
        self.error = message
        self.on_http_error()
        self.close()
        return False

    def _line(self):
        test = self._data.split(b'\n', 1)
        if len(test) == 1:
            if len(self._data) > self.http_max_line_length:
                return self._on_http_error('too much data without a line termination (a)')
            return None
        line, self._data = test
        if len(line):
            if line.endswith(b'\r'):
                line = line[:-1]
            if len(line) > self.http_max_line_length:
                return self._on_http_error('too much data without a line termination (b)')
        return line.decode('utf-8')

    def __status(self):
        line = self._line()
        if line is False or line is None:
            return False
        toks = line.split()
        if len(toks) < 3:
            return self._on_http_error('Invalid status line: too few tokens')

        # HTTP/1.[0|1] 200 OK
        if toks[0] in ('HTTP/1.0', 'HTTP/1.1'):
            try:
                self.http_status_code = toks[1]
                self.http_status_code = int(self.http_status_code)
            except ValueError:
                return self._on_http_error('Invalid status line: non-integer status code')
            self.http_status_message = ' '.join(toks[2:])

        # GET /resource HTTP/1.[0|1]
        else:
            if toks[2] not in ('HTTP/1.0', 'HTTP/1.1'):
                return self._on_http_error('Invalid status line: not HTTP/1.0 or HTTP/1.1')
            self.http_method = toks[0]

            res = urlparse.urlparse(toks[1])
            self.http_resource = res.path
            self.http_query = {}
            self.http_query_string = ''
            if res.query:
                self.http_query_string = res.query
                for n, v in urlparse.parse_qsl(res.query):
                    self.http_query[n] = v

        if not self.is_outbound:
            if not self.on_http_status(self.http_method, self.http_resource):
                return False

        self.__state = self.__header
        return True

    def __header(self):
        line = self._line()
        if line is None:
            return False

        if len(line) == 0:
            return self._end_header()

        else:
            if len(self.http_headers) == self.http_max_header_count:
                return self._on_http_error('Too many header records defined')
            test = line.split(':', 1)
            if len(test) != 2:
                return self._on_http_error('Invalid header: missing colon')
            name, value = test
            self.http_headers[name.strip().lower()] = value.strip()

        return True

    def _end_header(self):

        if getattr(self, '_http_method', None) == 'HEAD':  # this gets set if the send method is called
            self.__length = 0
            self.__state = self.__content

        elif 'transfer-encoding' in self.http_headers:
            if self.http_headers['transfer-encoding'] != 'chunked':
                return self._on_http_error('Unsupported Transfer-Encoding value')
            self.__state = self.__chunked_length

        else:
            if 'content-length' in self.http_headers:
                try:
                    self.__length = int(self.http_headers['content-length'])
                except ValueError:
                    return self._on_http_error('Invalid content length')
                if self.http_max_content_length:
                    if self.__length > self.http_max_content_length:
                        self.send_server(code=413, message='Request Entity Too Large')
                        return self._on_http_error('Content-Length exceeds maximum length')
                self.__state = self.__content
            else:
                if self.http_method:  # this means we are a server (sneaky code)
                    self.__length = 0
                    self.__content()
                else:
                    self._on_close = self.__on_identity_close
                    self.__state = self.__identity

        rc, result = self.on_http_headers()
        if rc != 0:
            return self.__error(result)

        return True

    def __identity(self):
        return False

    def __on_identity_close(self):
        self.http_content = self._data
        self._on_http_data()

    def __content(self):
        if len(self._data) >= self.__length:
            self.http_content = self._data[:self.__length]
            self._on_http_data()
            self._data = self._data[self.__length:]
            self._setup()
            return True
        return False

    def __chunked_length(self):
        line = self._line()
        if line is None:
            return False
        line = line.split(';', 1)[0]
        try:
            self.__length = int(line, 16)
        except ValueError:
            return self.__error('Invalid transfer-encoding chunk length: %s' % line)
        if self.__length == 0:
            self.__state = self.__footer
            return True
        if self.http_max_content_length:
            if (len(self._data) + self.__length) > self.http_max_content_length:
                self.send_server(code=413, message='Request Entity Too Large')
                return self.__error('Content-Length exceeds maximum length')
        self.__state = self.__chunked_content
        return True

    def __chunked_content(self):
        if len(self._data) >= self.__length:
            self.http_content += self._data[:self.__length]
            self._data = self._data[self.__length:]
            self.__state = self.__chunked_content_end
            return True
        return False

    def __chunked_content_end(self):
        line = self._line()
        if line is None:
            return False
        if line == '':
            self.__state = self.__chunked_length
            return True
        return self.__error('Extra data at end of chunk')

    def __footer(self):
        line = self._line()
        if line is None:
            return False

        if len(line) == 0:
            self._on_http_data()
            self._setup()
            return True

        test = line.split(':', 1)
        if len(test) != 2:
            return self.__error('Invalid footer: missing colon')
        if len(self.http_headers) == self.http_max_header_count:
            return self.__error('Too many header records defined')
        name, value = test
        self.http_headers[name.strip()] = value.strip()
        return True


class HTTPPart(object):

    def __init__(self, headers, disposition, content):
        '''
            Container for one part of a multipart message.

            The disposition is a dict with the k:v pairs from the 'Content-Disposition'
            header, where things like filename are stored.
        '''
        self.headers = headers
        self.disposition = disposition
        self.content = content


if __name__ == '__main__':
    from network import Network

    logging.basicConfig(level=logging.DEBUG)

    class MyHandler(HTTPHandler):

        def on_open(self):
            print('open cid=%s' % self.id)

        def on_ready(self):
            self.send(resource='/dummy/ping')

        def on_http_error(self, message):
            print('on_http_error cid=%s: %s' % (self.id, message))

        def on_http_data(self):
            print('on_http_data cid=%s: headers=%s' % (self.id, self.http_headers))
            print('on_http_data cid=%s: content=%s' % (self.id, self.http_content))

            now = time.perf_counter()
            print('stats cid={} c={:.4f}, r={:.4f}, d={:.4f}, e={:.4f}'.format(
                self.id,
                self.t_open - self.t_init,
                self.t_ready - self.t_open,
                now - self.t_ready,
                now - self.t_init,
            ))
            self.close('done')

        def on_close(self, reason):
            print('close cid=%s: %s' % (self.id, reason))

    n = Network()
    # hand = n.add_connection('dummy', 12345, MyHandler)
    hand = n.add_connection('dummy', 12346, MyHandler, is_ssl=True)
    while hand.is_open:
        n.service(.1)
