import errno
import os
import selectors
import socket
import ssl
import time

import logging
log = logging.getLogger(__name__)


class Handler(object):

    def __init__(self, sock, network, context=None, is_outbound=False, ssl_ctx=None):
        self._sock = sock
        self._network = network
        self._ssl_ctx = ssl_ctx

        self._sending = b''
        self._is_registered = False
        self._mask = 0
        self._is_quiesced = False

        self.id = network.next_id
        self.context = context
        self.is_outbound = is_outbound
        self.is_closed = False
        self.recv_len = 1024

        self.rx_count = 0
        self.tx_count = 0

        self.t_init = time.perf_counter()
        self.t_connect = 0
        self.t_ready = 0
        self.t_close = 0

        self.on_init()

    def on_init(self):
        pass

    def on_accept(self):
        ''' called on server connection; return False to immediately close the socket '''
        return True

    def on_failed_handshake(self, reason):
        ''' called when ssl handshake fails '''
        log.warning('cid=%s: %s', self.id, reason)

    def on_fail(self, message):
        ''' called when connection fails '''
        pass

    def on_handshake(self, cert):
        ''' called after ssl handshake (before on_ready); return False to close connection '''
        return True

    def on_open(self):
        ''' called after tcp handshake '''
        pass

    def on_ready(self):
        ''' called when socket is done with tcp and ssl (if applicable) handshaking '''
        pass

    def on_data(self, data):
        ''' called when some data has been read from the socket '''
        pass

    def on_close(self, reason):
        pass

    def send(self, data):
        if self._is_sending:
            self._sending += data
        else:
            self._do_write(data)

    def quiesce(self):
        ''' stop receiving data '''
        self._is_quiesced = True
        if self._mask == selectors.EVENT_READ:
            self._unregister()

    def unquiesce(self):
        ''' start receiving data again '''
        self._is_quiesced = False
        if self._mask == 0:
            self._register(selectors.EVENT_READ, self._do_read)

    def close(self, reason=None):
        if self.is_closed:
            return
        self.t_close = time.perf_counter()
        self.is_closed = True
        self._sock.close()
        self._unregister()
        self._on_close()  # for libraries
        self.on_close(reason)

    def _on_close(self):
        pass

    def on_send_error(self, message):
        log.debug(message)  # unusual but not fatal

    def on_recv_error(self, message):
        log.debug(message)  # unusual but not fatal

    @property
    def peer_address(self):
        try:
            return self._sock.getpeername()
        except socket.error:
            return ('Closing', 0)

    @property
    def _is_sending(self):
        ''' True if currently buffering data to send '''
        return len(self._sending) != 0

    @property
    def _is_pending(self):
        ''' True if ssl is currently buffering recv'd data - don't check if currently quiesced '''
        return not self._is_quiesced and self._ssl_ctx is not None and self._sock.pending()

    def _register(self, mask, callback=None):

        # special handling for quiesce: don't allow EVENT_READ to be selected
        if self._is_quiesced and mask == selectors.EVENT_READ:
            self._unregister()
            return

        self._mask = mask
        if self._is_registered:
            self._network.register_modify(self._sock, mask, callback)
        else:
            self._network.register(self._sock, mask, callback)
            self._is_registered = True

    def _unregister(self):
        if self._is_registered:
            self._network.unregister(self._sock)
            self._is_registered = False
            self._mask = 0

    def _on_delayed_connect(self):
        '''
           we come here after connection is complete. we have to check for
           errors, because "complete" doesn't always mean that is worked. if
           everything looks good, we pass control to _on_connect.
        '''
        try:
            rc = self._sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
            if rc != 0:
                error = os.strerror(rc)
        except Exception as e:
            error = str(e)
            rc = 1
        if rc == 0:
            self._on_connect()
        else:
            self.on_fail(error)
            self.close('failed to connect')

    def _on_connect(self):
        '''
            TCP handshake complete (inbound and outbound)

            we either start waiting for data to arrive (EVENT_READ) or prepare the
            socket for SSL handshake and go through all that.
        '''
        self.t_connect = time.perf_counter()
        self.on_open()
        self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)  # bye bye NAGLE
        if self._ssl_ctx:
            try:
                self._sock = self._ssl_ctx.wrap_socket(self._sock, do_handshake_on_connect=False)
            except Exception as e:
                self.close(str(e))
            else:
                self._do_handshake()
        else:
            self._register(selectors.EVENT_READ, self._do_read)
            self._on_ready()

    def _do_handshake(self):
        try:
            self._sock.do_handshake()
        except ssl.SSLWantReadError:
            self._register(selectors.EVENT_READ, self._do_handshake)
        except ssl.SSLWantWriteError:
            self._register(selectors.EVENT_WRITE, self._do_handshake)
        except Exception as e:
            self.on_failed_handshake(str(e))
            self.close('failed ssl handshake')
        else:
            self.peer_cert = self._sock.getpeercert()
            if not self.on_handshake(self.peer_cert):
                self.close('failed ssl certificate check')
                return
            self._on_ready()

    def _on_ready(self):
        self.t_ready = time.perf_counter()
        self._register(selectors.EVENT_READ, self._do_read)
        self.on_ready()

    def _do_read(self):
        try:
            data = self._sock.recv(self.recv_len)
        except ssl.SSLWantReadError:
            self._register(selectors.EVENT_READ, self._do_read)
        except ssl.SSLWantWriteError:
            self._register(selectors.EVENT_WRITE, self._do_read)
        except socket.error as e:
            errnum, errmsg = e
            if errnum == errno.ENOENT:
                self.on_recv_error(errmsg)  # apparently this can happen. http://www.programcreek.com/python/example/374/errno.ENOENT says it comes from the SSL library.
            else:
                self.close('recv error on socket: %s' % errmsg)
        except Exception as e:
            self.close('recv error on socket: %s' % str(e))
        else:
            if len(data) == 0:
                self.close('remote close')
            else:
                self.rx_count += len(data)
                self.on_data(data)
                if self._is_pending:
                    self._network.set_pending(self._do_read)  # give buffered ssl data another chance

    def _do_write(self, data=None):
        data = data if data is not None else self._sending
        if not data:
            self.close('logic error in handler')
            return
        try:
            l = self._sock.send(data)
        except ssl.SSLWantReadError:
            self._register(selectors.EVENT_READ, self._do_write)
        except ssl.SSLWantWriteError:
            self._register(selectors.EVENT_WRITE, self._do_write)
        except socket.error as e:
            errnum, errmsg = e
            if errnum in (errno.EINTR, errno.EWOULDBLOCK):
                self.on_send_error(errmsg)  # not fatal
                self._sending = data
                self._register(selectors.EVENT_WRITE, self._do_write)
            else:
                self.close('send error on socket: %s' % errmsg)
        except Exception as e:
            self.close('send error on socket: %s' % str(e))
        else:
            self.tx_count += l
            if l == len(data):
                self._sending = b''
                self._register(selectors.EVENT_READ, self._do_read)
            else:
                '''
                    we couldn't send all the data. buffer the remainder in self._sending and start
                    waiting for the socket to be writable again (EVENT_WRITE).
                '''
                self._sending = data[l:]
                self._register(selectors.EVENT_WRITE, self._do_write)


class Listener(object):

    def __init__(self, socket, network, handler, context=None, ssl_ctx=None):
        self.socket = socket
        self.network = network
        self.handler = handler
        self.context = context
        self.ssl_ctx = ssl_ctx

    def _do_accept(self):
        s, address = self.socket.accept()
        s.setblocking(False)
        h = self.handler(s, self.network, context=self.context, ssl_ctx=self.ssl_ctx)
        if h.on_accept():
            h._on_connect()
        else:
            h.close('connection not accepted')


class Network(object):

    def __init__(self):
        self._id = 0
        self._selector = selectors.DefaultSelector()

    @property
    def next_id(self):
        self._id += 1
        return self._id

    def add_server(self, port, handler, context=None, is_ssl=False, ssl_certfile=None, ssl_keyfile=None, ssl_password=None):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('', port))
        s.setblocking(False)
        s.listen(100)
        if is_ssl:
            ssl_ctx = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
            if ssl_certfile:
                ssl_ctx.load_cert_chain(ssl_certfile, ssl_keyfile, ssl_password)
        h = Listener(s, self, context=context, handler=handler, ssl_ctx=ssl_ctx if is_ssl else None)
        self.register(s, selectors.EVENT_READ, h._do_accept)
        return h

    def add_connection(self, host, port, handler, context=None, is_ssl=False):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setblocking(False)
        if is_ssl:
            ssl_ctx = ssl.create_default_context()
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
        h = handler(s, self, context=context, is_outbound=True, ssl_ctx=ssl_ctx if is_ssl else None)
        try:
            s.connect((host, port))
        except OSError as e:
            '''
                if EINPROGRESS, then connection is still underway. this is the socket's way
                of preventing a block on connect. we wait for the socket to go writeable,
                and then continue handling things in the _on_delayed_connect method.
            '''
            if e.errno == errno.EINPROGRESS:
                h._register(selectors.EVENT_WRITE, h._on_delayed_connect)
            else:
                h.close('host=%s, port=%s, error=%s', host, port, e.strerror)
        else:
            h._on_connect(self)
        return h

    def register(self, sock, event, data):
        self._selector.register(sock, event, data)

    def register_modify(self, sock, event, data):
        self._selector.modify(sock, event, data)

    def unregister(self, sock):
        self._selector.unregister(sock)

    def set_pending(self, callback):
        '''
            yeah. weirdness.

            an ssl-wrapped socket buffers data. the underlying socket may have nothing to
            read, but the ssl buffer may still contain data to be processed. a handler
            registers here if it still has some ssl-buffered data after having processed
            recv'd data.  it'll get another chance to process at the end of the _service
            loop.

            see Handler._on_readable.
        '''
        self._pending.append(callback)

    def _handle_pending(self):
        p, self._pending = self._pending, []
        for callback in p:
            callback()

    def _service(self, timeout):
        processed = False
        self._pending = []

        # handle read/write ready events
        for key, mask in self._selector.select(timeout):
            processed = True
            key.data()

        # handle ssl pending reads
        while len(self._pending):
            self._handle_pending()

        return processed

    def service(self, timeout=.1, max_iterations=100):
        while True:
            if not self._service(timeout):
                return
            max_iterations -= 1
            if max_iterations == 0:
                return
            timeout = 0


class MyHandler(Handler):

    def on_fail(self, message):
        log.debug('cid=%s, connection failure: %s', self.id, message)

    def on_failed_handshake(self, reason):
        log.debug('cid=%s, failed handshake: %s', self.id, reason)

    def on_handshake(self, cert):
        log.debug('cid=%s, cert=%s', self.id, cert)
        return True

    def on_ready(self):
        data = b'GET index.html HTTP/1.1\n\rContent-Length:0\n\r\n\r'
        self.send(data)
        log.debug('cid=%s, connected!', self.id)

    def on_data(self, data):
        log.debug('cid=%s, data=%s', self.id, data)

    def on_close(self, reason):
        log.debug('cid=%s, close: %s', self.id, reason)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    n = Network()
    n.add_connection('dummy', 12345, MyHandler)
    # n.add_connection('www.google.com', 443, MyHandler, is_ssl=True)
    while True:
        n.service(.1)
