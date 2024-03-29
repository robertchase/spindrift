'''
The MIT License (MIT)

https://github.com/robertchase/spindrift/blob/master/LICENSE.txt
'''
import gzip
import time
import json
import urllib.parse as urlparse

from spindrift.network import Handler

import logging
log = logging.getLogger(__name__)


class HTTPHandler(Handler):

    def _on_init(self):
        """Handler for an HTTP connection.

               available variables (on_http_data)

                   http_message - entire message
                   http_headers - dictionary of headers
                   http_content - content
                   t_http_data - time when http data fully arrives

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

               on_http_status(self, method, resource) - (server) when status
                   line is available
               on_http_send(self, headers, content) - useful for debugging
               on_http_data(self) - when data is available
               on_http_error(self, message)
        """
        self.t_http_data = 0
        self._data = bytearray()
        self._setup()

        self.http_max_content_length = None
        self.http_max_line_length = 10000
        self.http_max_header_count = 100

        self._http_close_on_complete = False

    @property
    def http_message(self):
        if len(self._data) == 0:
            return self._http_message
        return self._http_message[:-len(self._data)]

    @property
    def charset(self):
        h = self.http_headers.get('content-type')
        if h:
            charset = [c.split('=')[1].strip() for c in h.split(';')
                       if 'charset' in c]
            if len(charset):
                return charset[0]
        return None

    def on_http_send(self, headers, content):
        pass

    def on_http_status(self, method, resource):
        pass

    def on_http_data(self):
        pass

    def on_http_error(self, message):
        pass

    def _multipart(self):
        cache = self._data
        self.http_headers['content-type'], boundary = \
            self.http_headers['content-type'].split('; boundary=')
        # split, remove \r\n and ignore first & last; stuff into _data for _line
        for self._data in [p[2:] for p in
                           self.http_content.split('--' + boundary)][1:-1]:
            headers = dict(l.split(': ', 1) for l in iter(self._line, ''))
            if 'Content-Disposition' in headers:
                headers['Content-Disposition'], rem = \
                    headers['Content-Disposition'].split('; ', 1)
                disposition = dict(part.split('=', 1) for part in
                                   rem.split('; '))
            self.http_multipart.append(HTTPPart(headers, disposition,
                                                self._data))
        self._data = cache

    def _on_http_data(self):
        if self.http_headers.get('content-encoding') == 'gzip':
            try:
                self.http_content = gzip.decompress(self.http_content)
            except Exception:
                return self._on_http_error('Malformed gzip data')
        if self.http_headers.get('content-type', '').startswith('multipart'):
            try:
                self._multipart()
            except Exception:
                return self._on_http_error('Malformed multipart message')
        if self.charset:
            self.http_content = self.http_content.decode(self.charset)
        self.t_http_data = time.perf_counter()
        if self.is_inbound:
            self._state = self._init
            self.quiesce()
        self.on_http_data()

    def on_send_complete(self):
        if self._http_close_on_complete:
            self.close()
        elif self.is_inbound:
            self.unquiesce()
            self.on_data(b'')

    def _send(self, headers, content):
        self.on_http_send(headers, content)
        data = headers + content if content else headers
        super(HTTPHandler, self).send(data)

    def _http_send(self, status, headers, content,
                   content_type='text/html', charset='utf-8',
                   close=False, compress=False, host=None):

        if not headers:
            headers = {}

        header_keys = [k.lower() for k in headers.keys()]

        if 'content-type' not in header_keys:
            if content_type == 'json':
                content = json.dumps(content)
                content_type = 'application/json'
            elif content_type == 'form':
                content_type = 'application/x-www-form-urlencoded'
                content = urlparse.urlencode(content)
            headers['Content-Type'] = content_type

        if charset:
            content = content.encode(charset)
            headers['Content-Type'] += '; charset=%s' % charset

        if compress:
            if self.is_outbound:
                headers['Accept-Encoding'] = 'gzip'
            else:
                content = gzip.compress(content)
                headers['Content-Encoding'] = 'gzip'

        if 'date' not in header_keys:
            headers['Date'] = time.strftime(
                "%a, %d %b %Y %H:%M:%S %Z", time.localtime())

        if 'content-length' not in header_keys:
            headers['Content-Length'] = len(content)

        if close:
            headers['Connection'] = 'close'

        if self.is_outbound and 'host' not in (k.lower() for k in headers):
            host = host if host else self.host if self.host else \
                '%s:%s' % self.peer_address
            headers['Host'] = host

        headers = '%s\r\n%s\r\n\r\n' % (
            status,
            '\r\n'.join(['%s: %s' % (k, v) for k, v in headers.items()]),
        )
        headers = headers.encode('ascii')

        self._send(headers, content)

    def http_send(self, method='GET', host=None, resource='/', headers=None,
                  content='', content_type='text/html', charset='utf-8',
                  close=False, gzip=False):

        self._http_method = method
        status = '%s %s HTTP/1.1' % (method, resource)

        self._http_send(status, headers, content, content_type, charset,
                        close, gzip, host)

    def http_send_server(self, content='', code=200, message='OK',
                         content_type='text/html', charset='utf-8',
                         headers=None, gzip=False, close=False):

        if close or self.http_headers.get('connection') == 'close':
            self._http_close_on_complete = True

        status = 'HTTP/1.1 %d %s' % (code, message)

        self._http_send(status, headers, content, content_type, charset,
                        close, gzip)

    def _setup(self):
        self.http_headers = {}
        self._http_message = bytearray()
        self.http_content = bytearray()
        self.http_status_code = None
        self.http_status_message = None
        self.http_method = None
        self.http_multipart = []
        self.http_resource = None
        self.http_query_string = None
        self.http_query = {}
        self._state = self._status

    def on_http_headers(self):
        """a chance to terminate connection if headers don't check out"""
        pass

    def on_data(self, data):
        self._http_message.extend(data)
        self._data.extend(data)
        while self.is_open and not self.is_quiesced and self._state():
            pass

    def _on_http_error(self, message):
        self._http_close_on_complete = True
        self.on_http_error(message)
        return False

    def _line(self):
        test = self._data.split(b'\n', 1)
        if len(test) == 1:
            if len(self._data) > self.http_max_line_length:
                return self._on_http_error(
                    'too much data without a line termination (a)')
            return None
        line, self._data = test
        if len(line):
            if line.endswith(b'\r'):
                line = line[:-1]
            if len(line) > self.http_max_line_length:
                return self._on_http_error(
                    'too much data without a line termination (b)')
        return line.decode('utf-8')

    def _init(self):
        self._setup()
        return True

    def _status(self):
        line = self._line()
        if line is False or line is None:
            return False
        toks = line.split()
        if len(toks) < 2:
            return self._on_http_error('Invalid status line: too few tokens')

        # HTTP/1.[0|1] 200 OK
        if toks[0] in ('HTTP/1.0', 'HTTP/1.1'):
            if len(toks) < 3:
                self.http_status_message = ''
            else:
                self.http_status_message = ' '.join(toks[2:])
            try:
                self.http_status_code = toks[1]
                self.http_status_code = int(self.http_status_code)
            except ValueError:
                return self._on_http_error(
                    'Invalid status line: non-integer status code')

        # GET /resource HTTP/1.[0|1]
        else:
            if len(toks) < 3:
                return self._on_http_error(
                    'Invalid status line: too few tokens')
            if toks[2] not in ('HTTP/1.0', 'HTTP/1.1'):
                return self._on_http_error(
                    'Invalid status line: not HTTP/1.0 or HTTP/1.1')
            self.http_method = toks[0]

            res = urlparse.urlparse(toks[1])
            self.http_resource = res.path
            self.http_query = {}
            self.http_query_string = ''
            if res.query:
                self.http_query_string = res.query
                for n, v in urlparse.parse_qs(res.query).items():
                    self.http_query[n] = v[0] if len(v) == 1 else v

        if self.is_inbound:
            self.on_http_status(self.http_method, self.http_resource)

        self._state = self._header
        return True

    def _header(self):
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

        # this gets set if the send method is called
        if getattr(self, '_http_method', None) == 'HEAD':
            self._length = 0
            self._state = self._content

        elif 'transfer-encoding' in self.http_headers:
            if self.http_headers['transfer-encoding'] != 'chunked':
                return self._on_http_error(
                    'Unsupported Transfer-Encoding value')
            self._state = self._chunked_length

        else:
            if 'content-length' in self.http_headers:
                try:
                    self._length = int(self.http_headers['content-length'])
                except ValueError:
                    return self._on_http_error('Invalid content length')
                if self.http_max_content_length:
                    if self._length > self.http_max_content_length:
                        self.http_send_server(
                            code=413, message='Request Entity Too Large'
                        )
                        return self._on_http_error(
                            'Content-Length exceeds maximum length')
                self._state = self._content
            else:
                if self.is_inbound:  # server can't wait for close
                    self._length = 0
                    self._state = self._content
                    self._http_close_on_complete = True
                else:
                    self._on_close = self._on_end_at_close
                    self._state = self._nop

        self.on_http_headers()

        return self.is_open

    def _nop(self):
        return False

    def _on_end_at_close(self):
        self.http_content = self._data
        self._on_http_data()

    def _content(self):
        if len(self._data) >= self._length:
            self.http_content = self._data[:self._length]
            self._data = self._data[self._length:]
            self._on_http_data()
            return True
        return False

    def _chunked_length(self):
        line = self._line()
        if line is None:
            return False
        line = line.split(';', 1)[0]
        try:
            self._length = int(line, 16)
        except ValueError:
            return self._on_http_error(
                'Invalid transfer-encoding chunk length: %s' % line)
        if self._length == 0:
            self._state = self._footer
            return True
        if self.http_max_content_length:
            if (len(self._data) + self._length) > self.http_max_content_length:
                self.http_send_server(
                    code=413, message='Request Entity Too Large'
                )
                return self._on_http_error(
                    'Content-Length exceeds maximum length')
        self._state = self._chunked_content
        return True

    def _chunked_content(self):
        if len(self._data) >= self._length:
            self.http_content.extend(self._data[:self._length])
            self._data = self._data[self._length:]
            self._state = self._chunked_content_end
            return True
        return False

    def _chunked_content_end(self):
        line = self._line()
        if line is None:
            return False
        if line == '':
            self._state = self._chunked_length
            return True
        return self._on_http_error('Extra data at end of chunk')

    def _footer(self):
        line = self._line()
        if line is None:
            return False

        if len(line) == 0:
            self._on_http_data()
            return True

        test = line.split(':', 1)
        if len(test) != 2:
            return self._on_http_error('Invalid footer: missing colon')
        if len(self.http_headers) == self.http_max_header_count:
            return self._on_http_error('Too many header records defined')
        name, value = test
        self.http_headers[name.strip()] = value.strip()
        return True


class HTTPPart(object):

    def __init__(self, headers, disposition, content):
        """Container for one part of a multipart message.

           The disposition is a dict with the k:v pairs from the
           'Content-Disposition' header, where things like filename are
           stored.
        """
        self.headers = headers
        self.disposition = disposition
        self.content = content
