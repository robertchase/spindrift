from importlib import import_module
import logging
import logging.config
import platform
import signal
import uuid

from spindrift.dao.db import DB
import spindrift.file_util as file_util
from spindrift.micro_fsm.handler import InboundHandler, MysqlHandler
from spindrift.micro_fsm.parser import Parser as parser
from spindrift.rest.handler import RESTContext
from spindrift.rest.mapper import RESTMapper
from spindrift.network import Network
from spindrift.timer import Timer

import spindrift.micro_fsm.connect as micro_connection

log = logging.getLogger(__name__)


class Micro(object):
    def __init__(self):
        self.network = Network()
        self.timer = Timer()
        self.connection = type('Connections', (object,), dict())


micro = Micro()


class MicroContext(RESTContext):

    def __init__(self, mapper, http_max_content_length, http_max_line_length, http_max_header_count):
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


def setup_log(micro):

    config = micro.config.log
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


def setup_database(micro):
    try:
        db = micro.config.db
    except Exception:
        return
    if db.is_active:
        DB.setup(
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
        DB.context.timer = micro.timer
        DB.context.timeout = db.timeout
        DB.context.long_query = db.long_query


def setup_servers(micro, servers):
    config = micro.config
    for server in servers.values():
        conf = config._get('server.%s' % server.name)
        if conf.is_active is False:
            continue
        mapper = RESTMapper()
        context = MicroContext(
            mapper,
            conf.http_max_content_length if hasattr(conf, 'http_max_content_length') else None,
            conf.http_max_line_length if hasattr(conf, 'http_max_line_length') else 10000,
            conf.http_max_header_count if hasattr(conf, 'http_max_header_count') else 100,
        )
        for route in server.routes:
            methods = {}
            for method, path in route.methods.items():
                methods[method] = _import(path)
            mapper.add(route.pattern, **methods)
        handler = _import(conf.handler, is_module=True) if hasattr(conf, 'handler') else MicroHandler
        micro.network.add_server(
            port=conf.port,
            handler=handler,
            context=context,
            is_ssl=conf.ssl.is_active,
            ssl_certfile=conf.ssl.certfile,
            ssl_keyfile=conf.ssl.keyfile,
        )
        log.info('listening on %s port %d', server.name, conf.port)


def setup_connections(micro, connections):
    config = micro.config
    for c in connections.values():
        conf = config._get('connection.%s' % c.name)
        headers = {}
        for header in c.headers.values():
            value = config._get('connection.%s.header.%s' % (c.name, header.config)) if header.config else _import(header.code) if header.code else header.default
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
                optional[option.name] = config._get('connection.%s.resource.%s.%s' % (c.name, resource.name, option.config)) if option.config else option.default
            if resource.headers is not None:
                for header in resource.headers.values():
                    resource.headers[header.key] = config._get('connection.%s.resource.%s.header.%s' % (c.name, resource.name, header.config)) if header.config else _import(header.code) if header.code else header.default
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
    args = aparser.parse_args()

    p = parser.parse(args.micro)
    if args.no_config is False:
        p.config._load(args.config)
    if args.config_only is True:
        print(p.config)
    else:
        module.micro.config = p.config
        setup_log(module.micro)
        setup_database(module.micro)
        setup_servers(module.micro, p.servers)
        setup_connections(module.micro, p.connections)
        start(module.micro, p.setup)
        run(module.micro)
        stop(p.teardown)
        module.micro.network.close()
