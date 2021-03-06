'''
The MIT License (MIT)

https://github.com/robertchase/spindrift/blob/master/LICENSE.txt
'''
import ergaleia.config as config_file
from ergaleia.to_args import to_args
from ergaleia.import_by_path import import_by_path
from ergaleia.normalize_path import normalize_path
from spindrift.micro_fsm.fsm_micro import create as create_machine

import logging
log = logging.getLogger(__name__)


class ParserException(Exception):
    pass


class ParserFileException(ParserException):
    def __init__(self, fname, line, msg=None):
        if msg:
            msg = '{}, file={}, line={}'.format(msg, fname, line)
        else:
            msg = 'file={}, line={}'.format(fname, line)
        super(ParserFileException, self).__init__(msg)


class RecursiveMicro(ParserException):
    def __init__(self, micro):
        super(RecursiveMicro, self).__init__(
            'name={}'.format(micro)
        )


class InvalidMicroSpecification(ParserException):
    def __init__(self, micro):
        super(InvalidMicroSpecification, self).__init__(
            'name={}'.format(micro)
        )


class IncompleteLine(ParserException):
    pass


class UnexpectedDirective(ParserException):
    def __init__(self, directive, fname, line):
        super(UnexpectedDirective, self).__init__(
            fname, line, 'directive={}'.format(directive)
        )


def load(micro='micro', files=None, lines=None):

    if files is None:
        files = []
    if lines is None:
        lines = []

    if isinstance(micro, str):
        if micro in files:
            raise RecursiveMicro(micro)
        files.append(micro)
        micro = open(micro).readlines()
    elif isinstance(micro, list):
        files.append('list')
    else:
        raise InvalidMicroSpecification(micro)

    fname = files[-1]

    for num, line in enumerate(micro, start=1):
        line = line.split('#', 1)[0].strip()
        if len(line):
            line = line.split(' ', 1)
            if len(line) == 1:
                raise IncompleteLine(fname, num)
            if line[0].lower() == 'import':
                import_fname = normalize_path(line[1])
                load(import_fname, files, lines)
            else:
                lines.append((fname, num, line[0], line[1]))
    return lines


class Parser(object):

    def __init__(self):
        self.fsm = create_machine(
            add_arg=self.act_add_arg,
            add_config=self.act_add_config,
            add_connection=self.act_add_connection,
            add_content=self.act_add_content,
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
            add_enum=self.act_add_enum,
            add_teardown=self.act_add_teardown,
        )
        self.error = None
        self.fsm.state = 'init'
        self.config = config_file.Config()
        self._enums = {}
        self.setup = None
        self.teardown = None
        self.database = None
        self.log = Log()
        self.add_log_config()
        self.connections = {}
        self._config_servers = {}
        self.servers = {}

    @classmethod
    def parse(cls, micro='micro', trace=None):
        parser = cls()
        if trace:
            parser.fsm.trace = trace
        for fname, num, parser.event, parser.line in load(micro):
            try:
                parser.args, parser.kwargs = to_args(parser.line)
            except Exception:
                parser.args = parser.line.split()
                parser.kwargs = {}
            try:
                if not parser.fsm.handle(parser.event.lower()):
                    raise UnexpectedDirective(parser.event, fname, num)
                if parser.error:
                    raise Exception(parser.error)
            except ParserException:
                raise
            except Exception as e:
                raise ParserFileException(fname, num, str(e))
        return parser

    def _add_config(self, name, **kwargs):
        self.config._define(name, **kwargs)

    def _normalize_validator(self):
        if self.kwargs.get('validate') is not None:
            try:
                self.kwargs['validate'] = {
                    'int': int,
                    'bool': config_file.validate_bool,
                    'file': config_file.validate_file,
                }[self.kwargs['validate']]
            except KeyError:
                raise ValueError(
                    "validate must be one of 'int', 'bool', 'file'"
                )

    def act_add_config(self):
        self._normalize_validator()
        config = Config(*self.args, **self.kwargs)
        if config.default and config.validate:
            config.default = config.validate(config.default)
        self._add_config(config.name, **config.kwargs)

    def add_log_config(self):
        self._add_config('log.name', value=self.log.name, env='LOG_NAME')
        self._add_config(
            'log.level', value=self.log.level, env='LOG_LEVEL'
        )
        self._add_config(
            'log.is_stdout',
            value=self.log.is_stdout,
            validator=config_file.validate_bool,
            env='LOG_IS_STDOUT',
        )

    def act_add_arg(self):
        self.server.add_arg(Arg(*self.args, enums=self._enums, **self.kwargs))

    def act_add_enum(self):
        enum = Enum(*self.args, **self.kwargs)
        if enum.name in self._enums:
            self.error = "ENUM '%s' specified more than once" % enum.name
        self._enums[enum.name] = enum

    def act_add_log(self):
        self.log = Log(*self.args, **self.kwargs)
        self.add_log_config()

    def act_add_connection(self):
        connection = Connection(*self.args, **self.kwargs)
        if connection.name in self.connections:
            self.error = 'duplicate CONNECTION name: %s' % connection.name
        elif connection.url is None and connection.code is None:
            self.error = 'connection must have an url or code defined: %s' % (
                connection.name
            )
        else:
            self.connections[connection.name] = connection
            self.connection = connection
            if connection.url is not None:
                self._add_config(
                    'connection.%s.url' % connection.name,
                    value=connection.url,
                    env='CONNECTION_%s_URL' % connection.name,
                )
            self._add_config(
                'connection.%s.is_active' % connection.name,
                value=True,
                validator=config_file.validate_bool,
                env='CONNECTION_%s_IS_ACTIVE' % connection.name,
            )
            self._add_config(
                'connection.%s.is_verbose' % connection.name,
                value=connection.is_verbose,
                validator=config_file.validate_bool,
                env='CONNECTION_%s_IS_VERBOSE' % connection.name
            )
            self._add_config(
                'connection.%s.timeout' % connection.name,
                value=connection.timeout,
                validator=float,
                env='CONNECTION_%s_TIMEOUT' % connection.name
            )

    def act_add_content(self):
        self.server.add_content(Content(*self.args, enums=self._enums,
                                        **self.kwargs))

    def act_add_database(self):
        if self.database:
            self.error = 'DATABASE specified more than once'
        else:
            database = Database(*self.args, **self.kwargs)
            self.database = database
            self._add_config(
                'db.is_active',
                value=database.is_active,
                validator=config_file.validate_bool,
                env='DATABASE_IS_ACTIVE',
            )
            self._add_config('db.user', value=database.user,
                             env='DATABASE_USER')
            self._add_config('db.password', value=database.password,
                             env='DATABASE_PASSWORD')
            self._add_config('db.database', value=database.database,
                             env='DATABASE_NAME')
            self._add_config('db.host', value=database.host,
                             env='DATABASE_HOST')
            self._add_config(
                'db.port',
                value=database.port,
                validator=int,
                env='DATABASE_PORT',
            )
            self._add_config('db.isolation', value=database.isolation,
                             env='DATABASE_ISOLATION')
            self._add_config(
                'db.timeout',
                value=database.timeout,
                validator=float,
                env='DATABASE_TIMEOUT',
            )
            self._add_config(
                'db.long_query',
                value=database.long_query,
                validator=float,
                env='DATABASE_LONG_QUERY',
            )
            self._add_config(
                'db.fsm_trace',
                value=database.fsm_trace,
                validator=config_file.validate_bool,
                env='DATABASE_FSM_TRACE',
            )

    def act_add_header(self):
        header = Header(*self.args, **self.kwargs)
        if header.default is None \
                and header.config is None \
                and header.code is None:
            self.error = \
                'header must have a default, config or code setting: %s' % (
                    header.key,
                )
        else:
            self.connection.add_header(header)
            if header.config:
                self._add_config('connection.%s.header.%s' % (
                    self.connection.name,
                    header.config),
                    value=header.default,
                    env='CONNECTION_%s_HEADER_%s' % (
                        self.connection.name, header.config
                    ),
                )

    def act_add_resource_header(self):
        header = Header(*self.args, **self.kwargs)
        if header.default is None \
                and header.config is None \
                and header.code is None:
            self.error = \
                'header must have a default, config or code setting: %s' % (
                    header.key,
                )
        else:
            self.connection.add_resource_header(header)
            if header.config:
                self._add_config('connection.%s.resource.%s.header.%s' % (
                    self.connection.name,
                    self.connection._resource.name,
                    header.config),
                    value=header.default,
                    env='CONNECTION_%s_RESOURCE_%s_HEADER_%s' % (
                        self.connection.name,
                        self.connection._resource.name,
                        header.config,
                    )
                )

    def act_add_method(self):
        self.server.add_method(Method(self.event, *self.args, **self.kwargs))

    def act_add_required(self):
        self.connection.add_required(*self.args, **self.kwargs)

    def act_add_optional(self):
        self._normalize_validator()
        optional = Optional(*self.args, **self.kwargs)
        resource = self.connection.add_optional(optional)
        if optional.config:
            self._add_config(
                'connection.%s.resource.%s.%s' % (
                    self.connection.name,
                    resource.name,
                    optional.config),
                value=optional.default,
                validator=optional.validate,
                env='CONNECTION_%s_RESOURCE_%s_%s' % (
                    self.connection.name,
                    resource.name,
                    optional.config,
                ),
            )

    def act_add_resource(self):
        resource = Resource(*self.args, **self.kwargs)
        if resource.name in self.connection:
            self.error = 'duplicate connection resource: %s' % resource.name
        else:
            self.connection.add_resource(resource)
            if resource.is_verbose is not None:
                value = config_file.validate_bool(resource.is_verbose)
            else:
                value = None
            self._add_config(
                'connection.%s.resource.%s.is_verbose' % (
                    self.connection.name,
                    resource.name,
                ),
                value=value,
                validator=config_file.validate_bool,
                env='CONNECTION_%s_RESOURCE_%s_IS_VERBOSE' % (
                    self.connection.name,
                    resource.name,
                ),
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
            self._add_config(
                'server.%s.port' % server.name,
                value=server.port,
                validator=int,
                env='SERVER_%s_PORT' % server.name,
            )
            self._add_config(
                'server.%s.is_active' % server.name,
                value=True,
                validator=config_file.validate_bool,
                env='SERVER_%s_IS_ACTIVE' % server.name,
            )
            self._add_config(
                'server.%s.ssl.is_active' % server.name,
                value=False,
                validator=config_file.validate_bool,
                env='SERVER_%s_SSL_IS_ACTIVE' % server.name,
            )
            self._add_config(
                'server.%s.ssl.keyfile' % server.name,
                validator=config_file.validate_file,
                env='SERVER_%s_SSL_KEYFILE' % server.name,
            )
            self._add_config(
                'server.%s.ssl.certfile' % server.name,
                validator=config_file.validate_file,
                env='SERVER_%s_SSL_CERTFILE' % server.name,
            )

            self._add_config(
                'server.%s.http_max_content_length' % server.name,
                validator=int,
            )
            self._add_config(
                'server.%s.http_max_line_length' % server.name,
                validator=int,
                value=10000,
            )
            self._add_config(
                'server.%s.http_max_header_count' % server.name,
                validator=int,
                value=100,
            )

    def act_add_setup(self):
        if len(self.args) > 1:
            raise Exception('too many tokens specified')
        self.setup = self.args[0]

    def act_add_teardown(self):
        if len(self.args) > 1:
            raise Exception('too many tokens specified')
        self.teardown = self.args[0]

    def show_connections(self):
        return '\n'.join(str(c) for c in self.connections.values())


class Config(object):

    def __init__(self, name, default=None, validate=None, env=None):
        self.name = name
        self.default = default
        self.validate = validate
        self.env = env

    @property
    def kwargs(self):
        return {
            'value': self.default,
            'validator': self.validate,
            'env': self.env,
        }


class Log(object):

    def __init__(self, name='MICRO', level='debug', is_stdout=True):
        self.name = name
        self.level = level
        self.is_stdout = config_file.validate_bool(is_stdout)


class Server(object):

    def __init__(self, name, port):
        self.name = name
        self.port = int(port)
        self.routes = []

    def add_route(self, route):
        self.routes.append(route)
        self.route = route

    def add_method(self, method):
        self.route.method = method
        self.route.methods[method.method] = method

    def add_arg(self, arg):
        self.route.args.append(arg)

    def add_content(self, arg):
        method = self.route.method
        method.content.append(arg)


class Route(object):

    def __init__(self, pattern):
        self.pattern = pattern
        self.method = None
        self.methods = {}
        self.args = []


class Method(object):

    def __init__(self, method, path):
        self.method = method.lower()
        self.path = path
        self.content = []


class Enum:

    def __init__(self, name, *values, to_upper=False, to_lower=False):
        self.name = name
        self.values = values
        self.to_upper = to_upper
        self.to_lower = to_lower

    def __call__(self, value):
        if self.to_upper:
            value = value.upper()
        elif self.to_lower:
            value = value.lower()
        if value in self.values:
            return value
        raise ValueError('must be one of: %s' % str(self.values))


def _coerce_type(type, enum, enums):

    def validate_int(value):
        try:
            return int(value)
        except Exception:
            raise ValueError('must be an int')

    def validate_count(value):
        try:
            value = int(value)
            if value > 0:
                return value
        except Exception:
            pass
        raise ValueError('must be a postive int')

    if enum:
        if enum not in enums:
            raise Exception("enum '%s' not defined" % enum)
        type = enums[enum]
    elif type == 'int':
        type = validate_int
    elif type == 'count':
        type = validate_count
    elif type == 'bool':
        type = config_file.validate_bool
    else:
        try:
            type = import_by_path(type)
        except Exception:
            raise Exception(
                "unable to import validation function '{}'".format(type)
            )

    return type


class Arg:

    def __init__(self, type=None, enum=None, enums=None):
        self.type = _coerce_type(type, enum, enums)


class Content:

    def __init__(self, name, type=None, enum=None, enums=None,
                 is_required=True):
        self.name = name
        self.type = _coerce_type(type, enum, enums)
        self.is_required = config_file.validate_bool(is_required)


class Database(object):

    def __init__(
                self,
                is_active=True,
                user=None,
                password=None,
                database=None,
                host=None,
                port=3306,
                isolation='READ COMMITTED',
                timeout=60.0,
                long_query=0.5,
                fsm_trace=False
            ):
        self.is_active = config_file.validate_bool(is_active)
        self.user = user
        self.password = password
        self.database = database
        self.host = host
        self.port = int(port)
        self.isolation = isolation
        self.timeout = float(timeout)
        self.long_query = float(long_query)
        self.fsm_trace = config_file.validate_bool(fsm_trace)


class Connection(object):

    def __init__(
                self,
                name,
                url=None,
                is_json=True,
                is_verbose=True,
                timeout=5.0,
                handler=None,
                wrapper=None,
                setup=None,
                is_form=False,
                code=None
            ):
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


class Resource(object):

    def __init__(
                self,
                name,
                path,
                method='GET',
                is_json=None,
                is_verbose=None,
                trace=None,
                timeout=None,
                handler=None,
                wrapper=None,
                setup=None,
                is_form=None
            ):
        self.name = name
        self.path = path
        self.method = method
        self.is_json = config_file.validate_bool(is_json) \
            if is_json is not None else None
        self.is_verbose = config_file.validate_bool(is_verbose) \
            if is_verbose is not None else None
        self.trace = config_file.validate_bool(trace) \
            if trace is not None else None
        self.timeout = float(timeout) if timeout is not None else None
        self.handler = handler
        self.wrapper = wrapper
        self.setup = setup
        self.is_form = config_file.validate_bool(is_form) \
            if is_form is not None else None

        self.required = []
        self.optional = {}
        self.headers = {}

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
