'''
The MIT License (MIT)

https://github.com/robertchase/spindrift/blob/master/LICENSE.txt
'''
from importlib import import_module
import logging
import logging.config
import platform
import signal

from ergaleia.normalize_path import normalize_path
from spindrift.dao.db import DB
from spindrift.micro_fsm.handler import InboundHandler, MysqlHandler
from spindrift.micro_fsm.parser import Parser as parser
from spindrift.rest.handler import RESTContext
from spindrift.rest.mapper import RESTMapper, RESTMethod
from spindrift.network import Network
from spindrift.timer import Timer

import spindrift.micro_fsm.connect as micro_connection

log = logging.getLogger(__name__)


def trace(state, event, is_default, is_internal):
    log.debug('parser s={}, e={}'.format(state, event))


class Micro(object):
    def __init__(self):
        self.network = Network()
        self.timer = Timer()
        self.connection = type('Connections', (object,), dict())

    def load(self, micro='micro', config=None, is_trace=False):
        self.parser = parser.parse(micro, trace if is_trace else None)
        if config:
            self.parser.config._load(config)
        return self

    def setup(self):
        parser = self.parser
        config = parser.config
        setup_log(config)
        setup_database(config, self)
        setup_servers(config, self, parser.servers)
        setup_connections(config, self, parser.connections)
        return self

    def run(self):
        teardown = self.parser.teardown
        start(self, self.parser.setup)
        del self.__dict__['parser']  # parser not available during run
        run(self)
        stop(teardown)
        self.close()

    def close(self):
        self.network.close()


micro = Micro()


def db_cursor(rest_handler):
    """ Add a databse cursor to a request

        The cursor is added to the request as the attribute 'cursor'
        and set to automatically close on request.respond. The
        delay() method is called on the request object to allow
        async calls to continue without a premature response.
    """
    def inner(request, *args, **kwargs):
        cursor = micro.db.cursor
        cursor.cid = request.id
        request.cursor = cursor
        request.cleanup = cursor.close
        request.delay()
        rest_handler(request, *args, **kwargs)
    return inner


class MicroContext(RESTContext):

    def __init__(
                self, mapper,
                http_max_content_length,
                http_max_line_length,
                http_max_header_count
            ):
        super(MicroContext, self).__init__(mapper)
        self.http_max_content_length = http_max_content_length
        self.http_max_line_length = http_max_line_length
        self.http_max_header_count = http_max_header_count


class MicroHandler(InboundHandler):

    def __init__(self, *args, **kwargs):
        super(InboundHandler, self).__init__(*args, **kwargs)
        context = self.context
        self.http_max_content_length = context.http_max_content_length
        self.http_max_line_length = context.http_max_line_length
        self.http_max_header_count = context.http_max_header_count

    def on_rest_exception(self, exception_type, value, trace):
        log.exception('rest handler exception')


def _import(item_path, is_module=False):
    if is_module:
        return import_module(item_path)
    path, function = item_path.rsplit('.', 1)
    module = import_module(path)
    return getattr(module, function)


def _load(path):
    path = normalize_path(path, filetype='micro')
    p = parser.parse(path)
    return p


def setup_signal():

    def toggle_debug(signal, frame):
        logger = logging.getLogger()
        if logger.getEffectiveLevel() == logging.INFO:
            level = logging.DEBUG
            name = 'DEBUG'
        else:
            level = logging.INFO
            name = 'INFO'

        logger.setLevel(level)
        log.info('log level set to %s', name)

    signal.signal(signal.SIGUSR1, toggle_debug)


def setup_log(config):

    config = config.log
    name = config.name
    level = config.level.upper()
    stdout = config.is_stdout

    conf = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'datefmt': '%Y-%m-%d %H:%M:%S',
            },
            'syslog': {
            },
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'standard',
            },
            'syslog': {
                'class': 'logging.handlers.SysLogHandler',
                'address': '/dev/log',
                'formatter': 'syslog',
            },
        },
        'loggers': {
            '': {
                'handlers': ['default'],
                'level': level,
                'propagate': True,
            },
        },
    }

    body = ' [%(levelname)s] %(name)s:%(lineno)d> %(message)s'
    conf['formatters']['standard']['format'] = '%(asctime)s ' + name + body
    conf['formatters']['syslog']['format'] = name + body

    if platform.system() == 'Darwin':
        conf['handlers']['syslog']['address'] = '/var/run/syslog'

    if stdout:
        conf['handlers']['default'] = conf['handlers']['console']
        del conf['handlers']['syslog']
    else:
        conf['handlers']['default'] = conf['handlers']['syslog']

    logging.config.dictConfig(conf)
    log.info('log level set to %s', level)

    setup_signal()


def _fsm_trace(s, e, d, i):
    log.debug('mysql fsm s=%s, e=%s, is_internal=%s', s, e,  i)


def setup_database(config, micro):
    try:
        db = config.db
    except Exception:
        return
    if db.is_active:
        micro.db = DB(
            micro.network,
            user=db.user,
            pswd=db.password,
            db=db.database,
            host=db.host,
            port=db.port,
            isolation=db.isolation,
            handler=MysqlHandler,
            fsm_trace=_fsm_trace if db.fsm_trace else None,
        )
        context = micro.db.context
        context.timer = micro.timer
        context.timeout = db.timeout
        context.long_query = db.long_query


def setup_servers(config, micro, servers):
    for server in servers.values():
        conf = config._get('server.%s' % server.name)
        if conf.is_active is False:
            continue
        mapper = RESTMapper()
        context = MicroContext(
            mapper,
            conf.http_max_content_length,
            conf.http_max_line_length,
            conf.http_max_header_count,
        )
        for route in server.routes:
            methods = {}
            for name, defn in route.methods.items():
                method = RESTMethod(defn.path)
                for arg in route.args:
                    method.add_arg(arg.type)
                for arg in defn.content:
                    method.add_content(arg.name, arg.type, arg.is_required)
                methods[name] = method
            mapper.add(route.pattern, methods)
        try:
            handler = _import(conf.handler, is_module=True)
        except KeyError:
            handler = MicroHandler
        micro.network.add_server(
            port=conf.port,
            handler=handler,
            context=context,
            is_ssl=conf.ssl.is_active,
            ssl_certfile=conf.ssl.certfile,
            ssl_keyfile=conf.ssl.keyfile,
        )
        log.info('listening on %s port %d', server.name, conf.port)


def setup_connections(config, micro, connections):
    for c in connections.values():
        conf = config._get('connection.%s' % c.name)
        headers = {}
        for header in c.headers.values():
            if header.config:
                value = config._get(
                    'connection.%s.header.%s' % (c.name, header.config)
                )
            else:
                value = _import(header.code)
            if value:
                headers[header.key] = value
        conn = micro_connection.MicroConnect(
            c.name,
            micro.network,
            micro.timer,
            conf.url if c.url is not None else _import(c.code),
            headers,
            c.is_json,
            conf.is_verbose,
            conf.timeout,
            _import(c.handler) if c.handler else None,
            _import(c.wrapper) if c.wrapper else None,
            _import(c.setup) if c.setup else None,
            c.is_form,
        )
        for resource in c.resources.values():
            optional = {}
            for option in resource.optional.values():
                if option.config:
                    optional[option.name] = config._get(
                        'connection.%s.resource.%s.%s' % (
                            c.name, resource.name, option.config)
                    )
                else:
                    optional[option.name] = option.default
            if resource.headers is not None:
                for header in resource.headers.values():
                    if header.config:
                        resource.headers[header.key] = config._get(
                            'connection.%s.resource.%s.header.%s' % (
                                c.name,
                                resource.name,
                                header.config)
                        )
                    elif header.code:
                        resource.headers[header.key] = _import(header.code)
                    else:
                        resource.headers[header.key] = header.default
            conn.add_resource(
                resource.name,
                resource.path,
                resource.method,
                resource.headers,
                resource.is_json,
                resource.is_verbose,
                resource.trace,
                resource.timeout,
                _import(resource.handler) if resource.handler else None,
                _import(resource.wrapper) if resource.wrapper else None,
                _import(resource.setup) if resource.setup else None,
                resource.is_form,
                resource.required,
                optional,
            )
        setattr(micro.connection, c.name, conn)


def start(micro, setup):
    if setup:
        _import(setup)(micro.config)


def run(micro, sleep=100, max_iterations=100):
    while True:
        try:
            micro.network.service(
                timeout=sleep/1000.0, max_iterations=max_iterations
            )
            micro.timer.service()
        except KeyboardInterrupt:
            log.info('Received shutdown command from keyboard')
            break
        except Exception:
            log.exception('exception encountered')


def stop(teardown):
    if teardown:
        _import(teardown)()


if __name__ == '__main__':
    import argparse
    import os

    import spindrift.micro as module

    logging.basicConfig(level=logging.DEBUG)

    aparser = argparse.ArgumentParser(
        description='start a micro service',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    aparser.add_argument(
        '--config', help='configuration file (default=config)'
    )
    aparser.add_argument(
        '--no-config', dest='no_config', default=False, action='store_true',
        help="don't use a config file"
    )
    aparser.add_argument(
        '--micro', default='micro', help='micro description file'
    )
    aparser.add_argument(
        '-c', '--config-only',
        dest='config_only', action='store_true', default=False,
        help='parse micro and config files and display config values'
    )
    aparser.add_argument(
        '-n', '--connections',
        dest='connections_only', action='store_true', default=False,
        help='parse micro and config files and display defined connections'
    )
    aparser.add_argument(
        '-t', '--trace',
        dest='trace', action='store_true', default=False,
        help='log parser fsm events'
    )
    args = aparser.parse_args()

    micro = args.micro
    if args.no_config:
        config = None
    elif args.config is None:
        if os.path.isfile('config'):
            config = 'config'
        else:
            config = None
    else:
        config = args.config

    m = module.micro.load(micro, config, is_trace=args.trace)
    if args.config_only:
        print(m.parser.config)
    elif args.connections_only:
        print(m.parser.show_connections())
    else:
        m.setup().run()
