import os
import socket
from urllib.parse import urlparse

import spindrift.config as config_file
from spindrift.micro.fsm_micro import create as create_machine
import spindrift.micro.handler as handler
from spindrift.network import Network


class Micro(object):

    def __init__(self):
        self.NETWORK = Network()

    def __repr__(self):
        rep = []
        for server in self.servers.values():
            rep.append(str(server))
        for connection in self.connections.values():
            rep.append(str(connection))
        return '\n'.join(rep)

    def load(self, micro='micro', config='config'):
        result = Parser.parse(open(micro).readlines())
        self.servers = result.servers
        self.connections = result.connections
        self.config = result.config

        if os.path.exists(config):
            self.config._load(config)

        for connection in self.connections.values():
            connection.config(self.config)

    def service(self):
        self.NETWORK.service()


MICRO = Micro()


def to_args(line):
    args = []
    kwargs = {}
    for tok in line.split():
        if '=' in tok:
            n, v = tok.split('=', 1)
            kwargs[n] = v
        else:
            args.append(tok)
    return args, kwargs


class Parser(object):

    def __init__(self):
        self.fsm = create_machine(
            add_config=self.act_add_config,
            add_connection=self.act_add_connection,
            add_header=self.act_add_header,
            add_method=self.act_add_method,
            add_route=self.act_add_route,
            add_server=self.act_add_server,
        )
        self.error = None
        self.fsm.state = 'init'
        self.config = config_file.Config()
        self.connections = Connections()
        self.servers = {}

    @classmethod
    def parse(cls, data):
        parser = cls()
        for num, line in enumerate(data, start=1):
            line = line.split('#', 1)[0].strip()
            if len(line):
                line = line.split(' ', 1)
                if len(line) == 1:
                    raise Exception('too few tokens, line=%d' % num)

                parser.event, parser.line = line
                parser.args, parser.kwargs = to_args(parser.line)
                if not parser.fsm.handle(parser.event.lower()):
                    raise Exception("Unexpected directive '%s', line=%d" % (parser.event, num))
                if parser.error:
                    raise Exception('%s, line=%d' % (parser.error, num))

        return parser

    def _add_config(self, name, **kwargs):
        self.config._define(name, **kwargs)

    def act_add_config(self):
        if self.kwargs.get('validate') is not None:
            try:
                self.kwargs['validate'] = {
                    'int': config_file.validate_int,
                    'bool': config_file.validate_bool,
                    'file': config_file.validate_file,
                }[self.kwargs['validate']]
            except KeyError:
                raise Exception("validate must be one of 'int', 'bool', 'file'")
        config = Config(*self.args, **self.kwargs)
        self._add_config(config.name, **config.kwargs)

    def act_add_connection(self):
        connection = Connection(*self.args, **self.kwargs)
        if connection.name in self.connections:
            self.error = 'duplicate CONNECTION name: %s' % connection.name
        else:
            self.connections[connection.name] = connection
            self.connection = connection
            self._add_config('%s.url' % connection.name, value=connection.url)
            self._add_config('%s.is_active' % connection.name, value=True, validator=config_file.validate_bool)
            self._add_config('%s.is_json' % connection.name, value=True, validator=config_file.validate_bool)

    def act_add_header(self):
        self.connection.add_header(Header(*self.args, **self.kwargs))

    def act_add_method(self):
        self.server.add_method(Method(self.event, *self.args, **self.kwargs))

    def act_add_route(self):
        self.server.add_route(Route(*self.args, **self.kwargs))

    def act_add_server(self):
        server = Server(*self.args, **self.kwargs)
        if server.port in self.servers:
            self.error = 'duplicate SERVER port: %s' % server.port
        else:
            self.servers[server.port] = server
            self.server = server
            self._add_config('%s.port' % server.name, value=server.port, validator=config_file.validate_int)
            self._add_config('%s.is_active' % server.name, value=True, validator=config_file.validate_bool)
            self._add_config('%s.ssl.is_active' % server.name, value=False, validator=config_file.validate_bool)
            self._add_config('%s.ssl.keyfile' % server.name, validator=config_file.validate_file)
            self._add_config('%s.ssl.certfile' % server.name, validator=config_file.validate_file)


class Config(object):

    def __init__(self, name, default=None, validate=None, env=None):
        self.name = name
        self.default = default
        self.env = env

    @property
    def kwargs(self):
        return {'value': self.default, 'validator': self.validate, 'env': self.env}


class Server(object):

    def __init__(self, name, port):
        self.name = name
        self.port = int(port)
        self.routes = []

    def __repr__(self):
        return 'Server[name=%s, port=%s, routes=%s]' % (self.name, self.port, self.routes)

    def add_route(self, route):
        self.routes.append(route)
        self.route = route

    def add_method(self, method):
        self.route.methods[method.method.upper()] = method


class Route(object):

    def __init__(self, pattern):
        self.pattern = pattern
        self.methods = {}

    def __repr__(self):
        return 'Route[pattern=%s, methods=%s]' % (self.pattern, self.methods)


class Method(object):

    def __init__(self, method, path):
        self.method = method
        self.path = path

    def __repr__(self):
        return 'Method[method=%s, path=%s]' % (self.method, self.path)


def _method(method, connection, callback, path, headers=None, is_json=True, body=None, **kwargs):
    if body is None:
        body = kwargs
    ctx = handler.OutboundContext(callback, method, connection.hostname, connection.path + path, headers=headers, is_json=is_json, body=body)
    return MICRO.NETWORK.add_connection(connection.host, connection.port, handler.OutboundHandler, ctx, is_ssl=connection.is_ssl)


class Connections(dict):

    def __getattr__(self, name):
        return self[name]


class Connection(object):

    def __init__(self, name, url):
        self.name = name
        self.url = url
        self.headers = []

    def __repr__(self):
        return 'Connection[name=%s, url=%s, headers=%s' % (self.name, self.url, self.headers)

    def add_header(self, header):
        self.headers.append(header)

    def config(self, config):
        config = getattr(config, self.name)
        self.url = getattr(config, 'url')
        self.is_active = getattr(config, 'is_active')
        self.is_json = getattr(config, 'is_json')

        if not self.is_active:
            return

        try:
            p = urlparse(self.url)
        except Exception as e:
            raise Exception("unable to parse '%s' in connection '%s': %s" % (self.url, self.name, e.message))
        else:
            try:
                self.host = socket.gethostbyname(p.hostname)
            except Exception as e:
                raise Exception("unable to resolve '%s' in connection '%s': %s" % (p.hostname, self.name, str(e)))
            self.hostname = p.hostname
            self.port = p.port
            self.path = p.path
            self.is_ssl = p.scheme == 'https'

    def get(self, callback, path, **kwargs):
        return _method('GET', self, callback, path, **kwargs)


class Header(object):

    def __init__(self, name, config=None, default=None, validate=None, env=None):
        self.name = name
        self.config = config if config else name
        self.default = default
        self.validate = validate
        self.env = env

    def __repr__(self):
        attrs = ', '.join('%s=%s' % (n, getattr(self, n)) for n in ('name', 'config', 'default', 'validate', 'env') if getattr(self, n))
        return 'Header[%s]' % attrs


if __name__ == '__main__':

    def on_result(rc, result):
        print('on result: rc=%s, result=%s' % (rc, result))

    MICRO.load()
    connection = MICRO.connections.test.get(on_result, '/ping')
    while connection.is_open:
        MICRO.service()
