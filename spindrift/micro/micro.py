import functools
import socket
from urllib.parse import urlparse

import spindrift.config as config_file
from spindrift.micro.fsm_micro import create as create_machine
import spindrift.micro.handler as handler
from spindrift.network import Network
from spindrift.rest.mapper import RESTMapper
from spindrift.timer import Timer

import logging
log = logging.getLogger(__name__)


class Micro(object):

    def __init__(self):
        self.config = config_file.Config()
        self.NETWORK = Network()
        self.TIMER = Timer()

    def __repr__(self):
        rep = []
        for server in self.servers.values():
            rep.append(str(server))
        for connection in self.connection.values():
            rep.append(str(connection))
        return '\n'.join(rep)

    def load(self, micro='micro', config='config'):
        if isinstance(micro, str):
            micro = open(micro).readlines()
        elif isinstance(micro, list):
            pass
        else:
            micro = micro.readlines()
        self.servers, self.connection = Parser.parse(micro, self.config)

        self.config._define('loop.sleep', value=100)
        self.config._define('loop.max_iterations', value=100)

        if config:
            self.config._load(config)

        return self

    def start(self):
        for connection in self.connection.values():
            connection.micro = self
            connection.setup(self.config)
        for server in self.servers.values():
            server.micro = self
            server.start(self.config)
        return self

    def service(self):
        self.NETWORK.service(self.config.loop.sleep, self.config.loop.max_iterations)
        self.TIMER.service()

    def close(self):
        self.NETWORK.close()


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

    def __init__(self, config):
        self.fsm = create_machine(
            add_config=self.act_add_config,
            add_connection=self.act_add_connection,
            add_method=self.act_add_method,
            add_route=self.act_add_route,
            add_server=self.act_add_server,
        )
        self.error = None
        self.fsm.state = 'init'
        self.config = config
        self.connections = Connections()
        self.servers = {}

    @classmethod
    def parse(cls, data, config):
        parser = cls(config)
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

        return parser.servers, parser.connections

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
            self._add_config('connection.%s.url' % connection.name, value=connection.url)
            self._add_config('connection.%s.is_active' % connection.name, value=True, validator=config_file.validate_bool)
            self._add_config('connection.%s.is_json' % connection.name, value=connection.is_json, validator=config_file.validate_bool)
            self._add_config('connection.%s.is_debug' % connection.name, value=False, validator=config_file.validate_bool)
            self._add_config('connection.%s.api_key' % connection.name)
            self._add_config('connection.%s.wrapper' % connection.name, value=connection.wrapper)
            self._add_config('connection.%s.timeout' % connection.name, value=connection.timeout, validator=float)

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
            self._add_config('server.%s.port' % server.name, value=server.port, validator=config_file.validate_int)
            self._add_config('server.%s.is_active' % server.name, value=True, validator=config_file.validate_bool)
            self._add_config('server.%s.api_key' % server.name)
            self._add_config('server.%s.ssl.is_active' % server.name, value=False, validator=config_file.validate_bool)
            self._add_config('server.%s.ssl.keyfile' % server.name, validator=config_file.validate_file)
            self._add_config('server.%s.ssl.certfile' % server.name, validator=config_file.validate_file)


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
        self.route.methods[method.method] = method.path

    def start(self, config):
        config = config._get('server.%s' % self.name)

        if not config.is_active:
            return

        mapper = RESTMapper()
        for route in self.routes:
            mapper.add(route.pattern, **route.methods)

        context = handler.InboundContext(mapper, self.micro, config.api_key)

        ssl = config.ssl
        self.micro.NETWORK.add_server(config.port, handler.InboundHandler, context, ssl.is_active, ssl.keyfile, ssl.certfile)
        log.info('listening on server.%s %sport %s', self.name, 'ssl ' if ssl.is_active else '', config.port)


class Route(object):

    def __init__(self, pattern):
        self.pattern = pattern
        self.methods = {}

    def __repr__(self):
        return 'Route[pattern=%s, methods=%s]' % (self.pattern, self.methods)


class Method(object):

    def __init__(self, method, path):
        self.method = method.lower()
        self.path = path

    def __repr__(self):
        return 'Method[method=%s, path=%s]' % (self.method, self.path)


def _method(method, connection, config, callback, path, headers=None, is_json=None, is_debug=None, api_key=None, wrapper=None, is_ssl=None, timeout=None, body=None, **kwargs):
    is_json = is_json if is_json is not None else connection.is_json
    is_debug = is_debug if is_debug is not None else connection.is_debug
    api_key = api_key if api_key is not None else connection.api_key
    wrapper = wrapper if wrapper is not None else connection.wrapper
    is_ssl = is_ssl if is_ssl is not None else connection.is_ssl
    timeout = timeout if timeout is not None else connection.timeout
    timer = connection.micro.TIMER.add(None, timeout * 1000)
    ctx = handler.OutboundContext(callback, connection.micro, config, connection.url, method, connection.hostname, connection.path + path, headers, body, is_json, is_debug, api_key, wrapper, timer, **kwargs)
    return connection.micro.NETWORK.add_connection(connection.host, connection.port, handler.OutboundHandler, ctx, is_ssl=is_ssl)


class Connections(dict):

    def __getattr__(self, name):
        return self[name]


class Connection(object):

    def __init__(self, name, url, is_json=True, wrapper=None, timeout=5.0):
        self.name = name
        self.url = url
        self.is_json = config_file.validate_bool(is_json)
        self.wrapper = wrapper
        self.timeout = float(timeout)

    def __repr__(self):
        return 'Connection[name=%s, url=%s' % (self.name, self.url)

    def __getattr__(self, name):
        if name in ('get', 'put', 'post'):
            return functools.partial(_method, name.upper(), self, self.micro.config._get('connection.%s' % self.name))
        raise AttributeError("'%s' object has no attribute '%s'" % (self.__class__.__name__, name))

    def setup(self, config):
        config = config._get('connection.%s' % self.name)
        self.url = config.url
        self.is_active = config.is_active
        self.is_json = config.is_json
        self.is_debug = config.is_debug
        self.api_key = config.api_key
        self.wrapper = config.wrapper

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


if __name__ == '__main__':
    import argparse
    import logging
    logging.basicConfig(level=logging.DEBUG)

    parser = argparse.ArgumentParser(
        description='start a micro service',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument('--config', default='config', help='configuration file')
    parser.add_argument('--no-config', dest='no_config', default=False, action='store_true', help="don't use a config file")
    parser.add_argument('--micro', default='micro', help='micro description file')
    parser.add_argument('-c', '--config-only', dest='config_only', action='store_true', default=False, help='parse micro and config files and display config values')
    args = parser.parse_args()

    micro = Micro()
    micro.load(micro=args.micro, config=args.config if args.no_config is False else None)

    if args.config_only:
        print(micro.config)
    else:
        micro.start()
        while True:
            try:
                micro.service()
            except KeyboardInterrupt:
                log.info('Received shutdown command from keyboard')
                break
            except Exception:
                log.exception('exception encountered')
