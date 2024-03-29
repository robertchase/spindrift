'''
The MIT License (MIT)

https://github.com/robertchase/spindrift/blob/master/LICENSE.txt
'''
import errno
import os
import selectors
import socket
import ssl
import time

import logging
log = logging.getLogger(__name__)


class Network(object):

    def __init__(self):
        self._id = 0
        self._selector = selectors.DefaultSelector()
        self._is_open = True

    @property
    def is_open(self):
        return self._is_open

    def add_server(self, port, handler, context=None, is_ssl=False, ssl_certfile=None, ssl_keyfile=None, ssl_password=None):
        ''' Add a Server (listening) socket

            Required Arguments:
                port - listening port
                handler - Handler class/subclass assigned to each incoming connection

            Optional Arguments:
                context - arbitrary context assigned to each incoming connection
                is_ssl - if True, incoming connections must be ssl
                ssl_certificate - used to set up server side of ssl connection
                ssl_keyfile - used to set up server side of ssl connection
                ssl_password - used to set up server side of ssl connection

            Return:
                Listener - normally, this is ignored

            Notes:

            1. When a new connection arrives (before ssl handshake) the on_accept
               method is called on the socket's Handler. If this method returns
               False, the socket is immediately closed. Default is True.

               see: test/test_accept.py

            2. A Server will continue to be checked for new connections at each
               call to Network.service until Listener.close or Network.close is
               called.

            3. The same context is shared with every incoming connection handler.
               Save connection-specific data in the handler, and not in the
               context, so that simultaneous connections do not interfere with
               each other.

               see: test/test_context.py

            4. If you want to stand up an ssl server, make sure you understand what
               is going on. Read the python ssl documentation and heed the myriad
               warnings.

               see: test/test_ssl.py for a self-signed server configuration
        '''
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('', port))
        s.setblocking(False)
        s.listen(100)
        if is_ssl:
            ssl_ctx = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
            if ssl_certfile:
                ssl_ctx.load_cert_chain(ssl_certfile, ssl_keyfile, ssl_password)
        listener = Listener(s, self, context=context, handler=handler, ssl_ctx=ssl_ctx if is_ssl else None)
        self._register(s, selectors.EVENT_READ, listener._do_accept)
        return listener

    def add_connection(self, host, port, handler, context=None, is_ssl=False):
        ''' Add a Client (outbound) socket

        Required Arguments:
            host - name or ip address of server
            port - server port to connect to
            handler Handler class/subclass assigned to the connection

        Optional Arguments:
            context - arbitrary context assigned to the connection
            is_ssl - if True, connection will be ssl
        '''

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setblocking(False)
        if is_ssl:
            ssl_ctx = ssl.create_default_context()
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
        h = handler(s, self, context=context, is_outbound=True, host=host, ssl_ctx=ssl_ctx if is_ssl else None)
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
                h.on_fail(e.strerror)
                h.close('host=%s, port=%s, error=%s' % (host, port, e.strerror))
        else:
            h._on_connect(self)
        return h

    def service(self, timeout=.1, max_iterations=100):
        processed = False
        while True:
            if not self._service(timeout):
                return processed
            processed = True
            max_iterations -= 1
            if max_iterations == 0:
                return
            timeout = 0

    def close(self):
        ''' close any registered sockets

            In a long-running server, this doesn't matter that much, but for bursty
            activity, like unit tests, it is important to close sockets so they are
            quickly available for reuse. It is also important to un-register the
            sockets in case the the selector object continues to be used.

            This method will not see quiesced or otherwise unregistered connections;
            this is not a problem, since listening sockets are the more important
            quick-resuse case, and they are always registered.

            This is unlikely to be used except in unit tests and, if one is being
            polite, at program termination.
        '''
        if not self.is_open:
            return
        self._is_open = False
        r = []
        for k in self._selector.get_map().values():
            s = k.fileobj
            try:
                s.close()
            except Exception:
                pass
            else:
                r.append(s)
        for s in r:
            try:
                self._selector.unregister(s)
            except Exception:
                pass

    @property
    def _next_id(self):
        self._id += 1
        return self._id

    def _register(self, sock, event, data):
        self._selector.register(sock, event, data)

    def _register_modify(self, sock, event, data):
        self._selector.modify(sock, event, data)

    def _unregister(self, sock):
        try:
            self._selector.unregister(sock)
        except ValueError:
            pass

    def _set_pending(self, callback):
        '''
            an ssl-wrapped socket buffers data. the underlying socket may have nothing to
            read, but the ssl buffer may still contain data to be processed. a handler
            registers here if it still has some ssl-buffered data after having processed
            recv'd data.  it'll get another chance to process at the end of the _service
            loop.

            see Handler._do_read.
        '''
        self._pending.append(callback)

    def _handle_pending(self):
        p, self._pending = self._pending, []
        for callback in p:
            callback()  # any of these might add themselves back to _pending

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


class Handler(object):
    ''' Handle events on a network connection

        This object is instantiated by the Network for each new inbound or outbound connection.
        Each on_* method is called when the connection reaches certain states, or when data
        arrives or is sent from the connection. The most commonly used methods are on_ready,
        which is called when the connection is ready for use, and on_data when the latest
        chunk of data has arrived.

        Create custom behavior by subclassing Handler and providing logic in the appropriate
        on_* methods. The following methods are available:

            on_init - called at object setup
            on_accept - called for inbound server connections
                        return False to reject the connection (default True)
            on_failed_handshake(self, reason) - called for ssl handshake failures
            on_fail(self, message) - called for outbound connection failures
            on_handshake(self, cert) - called after ssl handshake
                                       return False to reject (default True)
            on_open - called after tcp connection (before any ssl negotiation)
            on_ready - called when connection is ready to use
            on_data(self, data) - called when data arrives
            on_close(self, reason) - called on connection close
            on_send_complete - called when send is complete, including library buffered data
                               this does not include TCP buffering

        These on_* methods are not fatal, and rather uncommon. The default action is to
        log.debug the message:

            on_recv_error(self, message) - on socket recv ENOENT
            on_send_error(self, message) - on socket send EINTR or EWOULDBLOCK

        These methods allow actions on the connection:

            send(data) - send data to connection peer
            close(reason) - close the connection
            quiesce - stop receiving data on the connection
            unquiesce - start receiving data on the connection again

        This attribute allows the socket recv length to be changed. The default value
        is usually fine:

            recv_len - read length passed to a socket recv (default 1024)

        The following attributes/properties are available:

            id - unique id assigned by a Network
            context - context object supplied to add_connection or add_server
            is_outbound - True if outbound (Client) connection
            is_inbound - True if inbound (Server) connection
            peer_address - address of peer
            host - host supplied to add_connection
            is_open - True if connection is open (not yet closed)
            is_closed - True if connection is closed
            is_quiesced - True is connection is quiesced
            rx_count - number of bytes read (after handshake)
            tx_count - number of bytes sent (after handshake)
            t_init - time of connection init
            t_open - time when TCP connection is established
            t_ready - time when SSL handshake, is complete
                      if connection is not SSL, then time will be very close to t_open
            t_close - time when connection is closed
    '''

    def __init__(self, sock, network, context=None, is_outbound=False, host=None, ssl_ctx=None):
        self._sock = sock
        self._network = network
        self._ssl_ctx = ssl_ctx

        self._sending = b''
        self._is_registered = False
        self._mask = 0

        self.id = network._next_id
        self.context = context
        self.is_outbound = is_outbound
        self.is_quiesced = False
        self.host = host
        self.is_closed = False
        self.recv_len = 1024

        self.rx_count = 0
        self.tx_count = 0

        self.t_init = time.perf_counter()
        self.t_open = 0
        self.t_ready = 0
        self.t_close = 0

        self._on_init()  # for libraries
        self.on_init()

    def on_init(self):
        pass

    def on_accept(self):
        ''' called on inbound connection; return False to immediately close the socket '''
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

    def on_send_complete(self):
        ''' called when all data has been sent on the socket

            sometimes socket.send is not able to send all of the data, in which
            case it is buffered in the library to be sent later. this method is
            called when socket.send has been called and all data is sent. tcp may
            still be holding the data in its own buffers, but that's not our
            concern.

            this is useful if you want to send some data, and then close.
        '''
        pass

    def quiesce(self):
        ''' stop receiving data '''
        if not self.is_quiesced:
            self.is_quiesced = True
            if self._mask == selectors.EVENT_READ:
                self._unregister()

    def unquiesce(self):
        ''' start receiving data again '''
        if self.is_open and self.is_quiesced:
            self.is_quiesced = False
            if self._mask == 0:
                self._register(selectors.EVENT_READ, self._do_read)

    def close(self, reason=None):
        if not self.is_closed:
            self.t_close = time.perf_counter()
            self.is_closed = True
            self._unregister()
            self._sock.close()
            self._on_close()  # for libraries
            self.on_close(reason)

    def on_send_error(self, message):
        log.debug(message)  # unusual but not fatal

    def on_recv_error(self, message):
        log.debug(message)  # unusual but not fatal

    @property
    def is_open(self):
        return not self.is_closed

    @property
    def is_inbound(self):
        return not self.is_outbound

    @property
    def is_ssl(self):
        return self._ssl_ctx is not None

    @property
    def address(self):
        try:
            return self._sock.getsockname()
        except socket.error:
            return ('Closing', 0)

    @property
    def peer_address(self):
        try:
            return self._sock.getpeername()
        except socket.error:
            return ('Closing', 0)

    @property
    def full_address(self):
        local = '%s:%s' % self.address
        remote = '%s:%s' % self.peer_address
        if self.is_outbound:
            direction = '->'
        else:
            direction = '<-'
        return '%s %s %s' % (local, direction, remote)

    def _on_init(self):
        pass

    @property
    def _is_sending(self):
        ''' True if currently buffering data to send '''
        return len(self._sending) != 0

    @property
    def _is_pending(self):
        ''' True if ssl is currently buffering recv'd data - don't check if currently quiesced '''
        return not self.is_quiesced and self._ssl_ctx is not None and self._sock.pending()

    def _on_close(self):
        ''' http wants this for identity connections '''
        pass

    def _register(self, mask, callback=None):

        # special handling for quiesce: don't allow EVENT_READ to be selected
        if self.is_quiesced and mask == selectors.EVENT_READ:
            self._unregister()
            return

        self._mask = mask
        if self._is_registered:
            self._network._register_modify(self._sock, mask, callback)
        else:
            self._network._register(self._sock, mask, callback)
            self._is_registered = True

    def _unregister(self):
        if self._is_registered:
            self._network._unregister(self._sock)
            self._is_registered = False
            self._mask = 0

    def _on_delayed_connect(self):
        '''
           we come here after connection is complete. we have to check for
           errors, because "complete" doesn't always mean that it worked. if
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

            we either start waiting for data to arrive (on_ready) or prepare the
            socket for SSL handshake and go through all that.
        '''
        self.t_open = time.perf_counter()
        self.on_open()
        self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)  # bye bye NAGLE
        if self._ssl_ctx:
            try:
                self._sock = self._ssl_ctx.wrap_socket(self._sock, server_side=self.is_inbound, do_handshake_on_connect=False)
            except Exception as e:
                self.close(str(e))
            else:
                self._do_handshake()
        else:
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
            errnum, errmsg = e.args
            if errnum == errno.ENOENT:
                self.on_recv_error(errmsg)  # apparently this can happen. http://www.programcreek.com/python/example/374/errno.ENOENT says it comes from the SSL library. # noqa: E501
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
                    self._network._set_pending(self._do_read)  # give buffered ssl data another chance

    def _do_write(self, data=None):
        data = data if data is not None else self._sending
        if not data:
            self.close('logic error in handler')
            return
        try:
            count = self._sock.send(data)
        except ssl.SSLWantReadError:
            self._register(selectors.EVENT_READ, self._do_write)
        except ssl.SSLWantWriteError:
            self._register(selectors.EVENT_WRITE, self._do_write)
        except socket.error as e:
            errnum, errmsg = e.args
            if errnum in (errno.EINTR, errno.EWOULDBLOCK):
                self.on_send_error(errmsg)  # not fatal
                self._sending = data
                self._register(selectors.EVENT_WRITE, self._do_write)
            else:
                self.close('send error on socket: %s' % errmsg)
        except Exception as e:
            self.close('send error on socket: %s' % str(e))
        else:
            self.tx_count += count
            if count == len(data):
                self._sending = b''
                self._register(selectors.EVENT_READ, self._do_read)
                self.on_send_complete()
            else:
                '''
                    we couldn't send all the data. buffer the remainder in self._sending and start
                    waiting for the socket to be writable again (EVENT_WRITE).
                '''
                self._sending = data[count:]
                self._register(selectors.EVENT_WRITE, self._do_write)


class Listener(object):

    def __init__(self, socket, network, handler, context=None, ssl_ctx=None):
        self.socket = socket
        self.network = network
        self.handler = handler
        self.context = context
        self.ssl_ctx = ssl_ctx

    def close(self):
        ''' close a listening socket

            Normally, a listening socket lasts for for duration of a server's life. If
            there is a need to close a listener, this is the way to do it.
        '''
        self.network._unregister(self.socket)
        self.socket.close()

    def _do_accept(self):
        s, address = self.socket.accept()
        s.setblocking(False)
        h = self.handler(s, self.network, context=self.context, ssl_ctx=self.ssl_ctx)
        if h.on_accept():
            h._on_connect()
        else:
            h.close('connection not accepted')
