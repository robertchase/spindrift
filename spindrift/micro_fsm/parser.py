import re

import spindrift.config as config_file
from spindrift.file_util import normalize_path
from spindrift.micro_fsm.fsm_micro import create as create_machine

import logging
log = logging.getLogger(__name__)


def to_args(line):
    args = []
    kwargs = {}
    for tok in line.split():
        nvp = re.split(r'(?<!\\)=', tok, 1)  # split by first non-escaped equal sign
        if len(nvp) == 2:
            n, v = nvp
            n = n.replace('\=', '=')
            v = v.replace('\=', '=')
            kwargs[n] = v
        else:
            args.append(tok.replace('\=', '='))
    return args, kwargs


def load(micro='micro', files=None, lines=None):

    path = micro

    if files is None:
        files = []
    if lines is None:
        lines = []

    if isinstance(micro, str):
        if micro in files:
            raise Exception('a micro file (in this case, %s) cannot be recursively imported' % micro)
        files.append(micro)
        micro = open(micro).readlines()
    elif isinstance(micro, list):
        files.append('dict')
    else:
        raise Exception('Invalid micro file type %s' % type(micro))

    fname = files[-1]

    for num, line in enumerate(micro, start=1):
        line = line.split('#', 1)[0].strip()
        if len(line):
            line = line.split(' ', 1)
            if len(line) == 1:
                raise Exception('too few tokens, file=%s, line=%d' % (fname, num))
            if line[0].lower() == 'import':
                import_fname = normalize_path(line[1], 'micro', parent=path)
                load(import_fname, files, lines)
            else:
                lines.append((fname, num, line[0], line[1]))
    return lines


class Parser(object):

    def __init__(self):
        self.fsm = create_machine(
            add_config=self.act_add_config,
            add_connection=self.act_add_connection,
            add_database=self.act_add_database,
            add_header=self.act_add_header,
            add_log=self.act_add_log,
            add_method=self.act_add_method,
            add_optional=self.act_add_optional,
            add_required=self.act_add_required,
            add_resource=self.act_add_resource,
            add_resource_header=self.act_add_resource_header,
            add_route=self.act_add_route,
            add_server=self.act_add_server,
            add_setup=self.act_add_setup,
            add_teardown=self.act_add_teardown,
        )
        self.error = None
        self.fsm.state = 'init'
        self.config = config_file.Config()
        self.setup = None
        self.teardown = None
        self.database = None
        self.log = Log()
        self.add_log_config()
        self.connections = {}
        self._config_servers = {}
        self.servers = {}

    @property
    def is_new(self):
        return len(self._config_servers) == 0

    @classmethod
    def parse(cls, micro='micro'):
        parser = cls()
        for fname, num, parser.event, parser.line in load(micro):
            parser.args, parser.kwargs = to_args(parser.line)
            if not parser.fsm.handle(parser.event.lower()):
                raise Exception("Unexpected directive '%s', file=%s, line=%d" % (parser.event, fname, num))
            if parser.error:
                raise Exception('%s, line=%d' % (parser.error, num))
        return parser

    def _add_config(self, name, **kwargs):
        self.config._define(name, **kwargs)

    def _normalize_validator(self):
        if self.kwargs.get('validate') is not None:
            try:
                self.kwargs['validate'] = {
                    'int': config_file.validate_int,
                    'bool': config_file.validate_bool,
                    'file': config_file.validate_file,
                }[self.kwargs['validate']]
            except KeyError:
                raise Exception("validate must be one of 'int', 'bool', 'file'")

    def act_add_config(self):
        self._normalize_validator()
        config = Config(*self.args, **self.kwargs)
        if config.default and config.validate:
            config.default = config.validate(config.default)
        self._add_config(config.name, **config.kwargs)

    def add_log_config(self):
        self._add_config('log.name', value=self.log.name)
        self._add_config('log.level', value=self.log.level, env='SPINDRIFT_LOG_LEVEL')
        self._add_config('log.is_stdout', value=self.log.is_stdout, validator=config_file.validate_bool)

    def act_add_log(self):
        self.log = Log(*self.args, **self.kwargs)
        self.add_log_config()

    def act_add_connection(self):
        connection = Connection(*self.args, **self.kwargs)
        if connection.name in self.connections:
            self.error = 'duplicate CONNECTION name: %s' % connection.name
        elif connection.url is None and connection.code is None:
            self.error = 'connection must have an url or code defined: %s' % connection.name
        else:
            self.connections[connection.name] = connection
            self.connection = connection
            if connection.url is not None:
                self._add_config('connection.%s.url' % connection.name, value=connection.url)
            self._add_config('connection.%s.is_active' % connection.name, value=True, validator=config_file.validate_bool)
            self._add_config('connection.%s.is_verbose' % connection.name, value=connection.is_verbose, validator=config_file.validate_bool)
            self._add_config('connection.%s.timeout' % connection.name, value=connection.timeout, validator=float)

    def act_add_database(self):
        if self.database:
            self.error = 'DATABASE specified more than once'
        else:
            database = Database(*self.args, **self.kwargs)
            self.database = database
            self._add_config('db.is_active', value=database.is_active, validator=config_file.validate_bool)
            self._add_config('db.user', value=database.user)
            self._add_config('db.password', value=database.password)
            self._add_config('db.database', value=database.database)
            self._add_config('db.host', value=database.host, env='MYSQL_HOST')
            self._add_config('db.port', value=database.port, validator=config_file.validate_int)
            self._add_config('db.isolation', value=database.isolation)
            self._add_config('db.timeout', value=database.timeout, validator=float)
            self._add_config('db.long_query', value=database.long_query, validator=float)
            self._add_config('db.fsm_trace', value=database.fsm_trace, validator=config_file.validate_bool, env='SPINDRIFT_DB_FSM_TRACE')

    def act_add_header(self):
        header = Header(*self.args, **self.kwargs)
        if header.default is None and header.config is None and header.code is None:
            self.error = 'header must have a default, config or code setting: %s' % header.key
        else:
            self.connection.add_header(header)
            if header.config:
                self._add_config('connection.%s.header.%s' % (self.connection.name, header.config), value=header.default)

    def act_add_resource_header(self):
        header = Header(*self.args, **self.kwargs)
        if header.default is None and header.config is None and header.code is None:
            self.error = 'header must have a default, config or code setting: %s' % header.key
        else:
            self.connection.add_resource_header(header)
            if header.config:
                self._add_config('connection.%s.resource.%s.header.%s' % (self.connection.name, self.connection._resource.name, header.config), value=header.default)

    def act_add_method(self):
        self.server.add_method(Method(self.event, *self.args, **self.kwargs))

    def act_add_required(self):
        self.connection.add_required(*self.args, **self.kwargs)

    def act_add_optional(self):
        self._normalize_validator()
        optional = Optional(*self.args, **self.kwargs)
        resource = self.connection.add_optional(optional)
        if optional.config:
            self._add_config('connection.%s.resource.%s.%s' % (self.connection.name, resource.name, optional.config), value=optional.default, validator=optional.validate)

    def act_add_resource(self):
        resource = Resource(*self.args, **self.kwargs)
        if resource.name in self.connection:
            self.error = 'duplicate connection resource: %s' % resource.name
        else:
            self.connection.add_resource(resource)
            self._add_config(
                'connection.%s.resource.%s.is_verbose' % (self.connection.name, resource.name),
                value=config_file.validate_bool(resource.is_verbose) if resource.is_verbose is not None else None,
                validator=config_file.validate_bool,
            )

    def act_add_route(self):
        self.server.add_route(Route(*self.args, **self.kwargs))

    def act_add_server(self):
        server = Server(*self.args, **self.kwargs)
        if server.port in [s.port for s in self.servers.values()]:
            self.error = 'duplicate SERVER port: %s' % server.port
        else:
            self.servers[server.name] = server
            self.server = server
            self._add_config('server.%s.port' % server.name, value=server.port, validator=config_file.validate_int)
            self._add_config('server.%s.is_active' % server.name, value=True, validator=config_file.validate_bool)
            self._add_config('server.%s.ssl.is_active' % server.name, value=False, validator=config_file.validate_bool)
            self._add_config('server.%s.ssl.keyfile' % server.name, validator=config_file.validate_file)
            self._add_config('server.%s.ssl.certfile' % server.name, validator=config_file.validate_file)

    def act_add_setup(self):
        if len(self.args) > 1:
            raise Exception('too many tokens specified')
        self.setup = self.args[0]

    def act_add_teardown(self):
        if len(self.args) > 1:
            raise Exception('too many tokens specified')
        self.teardown = self.args[0]


class Config(object):

    def __init__(self, name, default=None, validate=None, env=None):
        self.name = name
        self.default = default
        self.validate = validate
        self.env = env

    @property
    def kwargs(self):
        return {'value': self.default, 'validator': self.validate, 'env': self.env}


class Log(object):

    def __init__(self, name='MICRO', level='debug', is_stdout=True):
        self.name = name
        self.level = level
        self.is_stdout = is_stdout


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


class Database(object):

    def __init__(self, is_active=True, user=None, password=None, database=None, host=None, port=3306, isolation='READ COMMITTED', handler=None, timeout=60.0, long_query=0.5, fsm_trace=False):
        self.is_active = is_active
        self.user = user
        self.password = password
        self.database = database
        self.host = host
        self.port = port
        self.isolation = isolation
        self.timeout = float(timeout)
        self.long_query = float(long_query)
        self.fsm_trace = fsm_trace


class Connection(object):

    def __init__(self, name, url=None, is_json=True, is_verbose=True, timeout=5.0, handler=None, wrapper=None, setup=None, is_form=False, code=None):
        self.name = name
        self.url = url
        self.is_json = config_file.validate_bool(is_json)
        self.is_verbose = config_file.validate_bool(is_verbose)
        self.timeout = float(timeout)
        self.handler = handler
        self.wrapper = wrapper
        self.setup = setup
        self.is_form = config_file.validate_bool(is_form)
        self.code = code

        self.headers = {}
        self.resources = {}
        self._resource = None

    def __repr__(self):
        return 'Connection[name=%s, url=%s, hdr=%s, res=%s]' % (self.name, self.url, self.headers, self.resources)

    def __contains__(self, name):
        return name in self.resources

    def add_header(self, header):
        self.headers[header.key] = header

    def add_resource(self, resource):
        self._resource = resource
        self.resources[resource.name] = resource

    def add_resource_header(self, header):
        self._resource.add_header(header)

    def add_required(self, parameter_name):
        self._resource.add_required(parameter_name)

    def add_optional(self, optional):
        self._resource.add_optional(optional)
        return self._resource


class Header(object):

    def __init__(self, key, default=None, config=None, code=None):
        self.key = key
        self.default = default
        self.config = config
        self.code = code

    def __repr__(self):
        return 'Header[key=%s, dft=%s, cfg=%s, cod=%s]' % (self.key, self.default, self.config, self.code)


class Resource(object):

    def __init__(self, name, path, method='GET', is_json=None, is_verbose=None, trace=None, timeout=None, handler=None, wrapper=None, setup=None, is_form=None):
        self.name = name
        self.path = path
        self.method = method
        self.is_json = config_file.validate_bool(is_json) if is_json is not None else None
        self.is_verbose = config_file.validate_bool(is_verbose) if is_verbose is not None else None
        self.trace = config_file.validate_bool(trace) if trace is not None else None
        self.timeout = float(timeout) if timeout is not None else None
        self.handler = handler
        self.wrapper = wrapper
        self.setup = setup
        self.is_form = config_file.validate_bool(is_form) if is_form is not None else None

        self.required = []
        self.optional = {}
        self.headers = {}

    def __repr__(self):
        return 'Resource[name=%s, url=%s, req=%s, opt=%s' % (self.name, self.path, self.required, self.optional)

    def add_required(self, parameter_name):
        self.required.append(parameter_name)

    def add_optional(self, optional):
        self.optional[optional.name] = optional

    def add_header(self, header):
        self.headers[header.key] = header


class Optional(object):

    def __init__(self, name, default=None, config=None, validate=None):
        if default and validate:
            default = validate(default)
        self.name = name
        self.default = default
        self.config = config
        self.validate = validate

    def __repr__(self):
        return 'Optional[name=%s, dft=%s, cfg=%s]' % (self.name, self.default, self.config)
