from importlib import import_module
import logging
import sys
import uuid

import spindrift.file_util as file_util
from spindrift.micro_fsm.parser import Parser as parser
from spindrift.rest.handler import RESTHandler, RESTContext
from spindrift.rest.mapper import RESTMapper
from spindrift.network import Network
from spindrift.timer import Timer

log = logging.getLogger(__name__)


class Micro(object):
    def __init__(self):
        self.network = Network()
        self.timer = Timer()
        self.connections = type('Connections', (object,), dict())


micro = Micro()


class MicroContext(RESTContext):

    def __init__(self, mapper, http_max_content_length, http_max_line_length, http_max_header_count):
        super(MicroContext, self).__init__(mapper)
        self.http_max_content_length = http_max_content_length
        self.http_max_line_length = http_max_line_length
        self.http_max_header_count = http_max_header_count


class MicroRESTHandler(RESTHandler):

    def __init__(self, *args, **kwargs):
        super(MicroRESTHandler, self).__init__(*args, **kwargs)
        context = self.context
        self.http_max_content_length = context.http_max_content_length
        self.http_max_line_length = context.http_max_line_length
        self.http_max_header_count = context.http_max_header_count

    def on_rest_exception(self, exception_type, value, trace):
        code = uuid.uuid4().hex
        log.exception('exception encountered, code: %s', code)
        return 'oh, no! something broke. sorry about that.\nplease report this problem using the following id: %s\n' % code


def _import(item_path, is_module=False):
    if is_module:
        return import_module(item_path)
    path, function = item_path.rsplit('.', 1)
    module = import_module(path)
    return getattr(module, function)


def _load(path):
    path = file_util.normalize_path(path, filetype='micro')
    p = parser.parse(path)
    return p


def load_server(filename, config=None):
    p = _load(filename)
    if config:
        p.config._load(file_util.normalize_path(config))
    sys.modules[__name__].config = p.config
    micro.server.close()
    setup_servers(p.config, p.servers)
    return p


def load_connection(filename, config=None):
    p = _load(filename)
    if config:
        p.config._load(file_util.normalize_path(config))
    sys.modules[__name__].config = p.config
    # setup_connections(p.config, p.connections)
    return p


def re_start(p):
    micro.server.close()
    setup_servers(p.config, p.servers)


def load_config(config='config', micro='micro'):
    p = parser.parse(micro)
    p.config._load(file_util.normalize_path(config))
    sys.modules[__name__].config = p.config
    return p.config


def setup_servers(config, servers):
    for server in servers.values():
        conf = config._get('server.%s' % server.name)
        if conf.is_active is False:
            continue
        mapper = RESTMapper()
        for route in server.routes:
            methods = {}
            for method, path in route.methods.items():
                methods[method] = _import(path)
            mapper.add(route.pattern, **methods)
        context = MicroContext(
            mapper,
            conf.http_max_content_length if hasattr(conf, 'http_max_content_length') else None,
            conf.http_max_line_length if hasattr(conf, 'http_max_line_length') else 10000,
            conf.http_max_header_count if hasattr(conf, 'http_max_header_count') else 100,
        )
        handler = _import(conf.handler, is_module=True) if hasattr(conf, 'handler') else RESTHandler
        micro.network.add_server(
            port=conf.port,
            handler=handler,
            context=context,
            is_ssl=conf.ssl.is_active,
            ssl_certfile=conf.ssl.certfile,
            ssl_keyfile=conf.ssl.keyfile,
        )
        log.info('listening on %s port %d', server.name, conf.port)


# def setup_connections(config, connections):
#     for c in connections.values():
#         conf = config._get('connection.%s' % c.name)
#         headers = {}
#         for header in c.headers.values():
#             value = config._get('connection.%s.header.%s' % (c.name, header.config)) if header.config else _import(header.code) if header.code else header.default
#             if value:
#                 headers[header.key] = value
#         conn = async.Connection(
#            conf.url if c.url is not None else _import(c.code),
#            c.is_json,
#            conf.is_debug,
#            conf.timeout,
#            c.is_form,
#            _import(c.wrapper) if c.wrapper else None,
#            _import(c.handler) if c.handler else None,
#            _import(c.setup) if c.setup else None,
#            headers,
#         )
#         for resource in c.resources.values():
#             optional = {}
#             for option in resource.optional.values():
#                 optional[option.name] = config._get('connection.%s.resource.%s.%s' % (c.name, resource.name, option.config)) if option.config else option.default
#             if resource.headers is not None:
#                 for header in resource.headers.values():
#                     resource.headers[header.key] = config._get('connection.%s.resource.%s.header.%s' % (c.name, resource.name, header.config)) if header.config else _import(header.code) if header.code else header.default
#             conn.add_resource(
#                 resource.name,
#                 resource.path,
#                 resource.method,
#                 resource.required,
#                 optional,
#                 resource.headers,
#                 resource.is_json,
#                 resource.is_debug,
#                 resource.trace,
#                 resource.timeout,
#                 resource.is_form,
#                 _import(resource.handler) if resource.handler else None,
#                 _import(resource.wrapper) if resource.wrapper else None,
#                 _import(resource.setup) if resource.setup else None,
#             )
#         setattr(connection, c.name, conn)


def start(config, setup):
    if setup:
        _import(setup)(config)


def run(sleep=100, max_iterations=100):
    while True:
        try:
            micro.network.service(timeout=sleep/1000.0, max_iterations=max_iterations)
            micro.timer.service()
        except KeyboardInterrupt:
            log.info('Received shutdown command from keyboard')
            break
        except Exception:
            log.exception('exception encountered')


def stop(teardown):
    if teardown:
        _import(teardown)()


def launch(micro):
    p = parser.parse(micro)
    sys.modules[__name__].config = p.config
    setup_servers(p.config, p.servers)
    # setup_connections(p.config, p.connections)
    run()


if __name__ == '__main__':
    import argparse

    import spindrift.micro as module

    logging.basicConfig(level=logging.DEBUG)

    aparser = argparse.ArgumentParser(
        description='start a micro service',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    aparser.add_argument('--config', default='config', help='configuration file')
    aparser.add_argument('--no-config', dest='no_config', default=False, action='store_true', help="don't use a config file")
    aparser.add_argument('--micro', default='micro', help='micro description file')
    aparser.add_argument('-c', '--config-only', dest='config_only', action='store_true', default=False, help='parse micro and config files and display config values')

    aparser.add_argument('-v', '--verbose', action='store_true', default=False, help='display debug level messages')
    aparser.add_argument('-s', '--stdout', action='store_true', default=False, help='display messages to stdout')
    args = aparser.parse_args()

    p = parser.parse(args.micro)
    if args.no_config is False:
        p.config._load(args.config)
    if args.config_only is True:
        print(p.config)
    else:
        module.config = p.config
        setup_servers(p.config, p.servers)
        pass  # setup_connections(p.config, p.connections)
        start(p.config, p.setup)
        run()
        stop(p.teardown)