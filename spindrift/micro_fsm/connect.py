'''
The MIT License (MIT)

https://github.com/robertchase/spindrift/blob/master/LICENSE.txt
'''
import logging
import string

from spindrift.connect import connect_parsed, URLParser
from spindrift.micro_fsm.handler import OutboundHandler as MicroHandler


log = logging.getLogger(__name__)


class MicroConnect(object):

    def __init__(
                self,
                name,
                network,
                timer,
                url,
                headers,
                is_json,
                is_verbose,
                timeout,
                handler,
                wrapper,
                setup,
                is_form,
            ):
        self.name = name
        self.network = network
        self.timer = timer
        self.url = url
        self._last_url = None
        self.headers = headers
        self.is_json = is_json
        self.is_verbose = is_verbose
        self.timeout = timeout
        self.handler = handler or MicroHandler
        self.wrapper = wrapper
        self.setup = setup
        self.is_form = is_form

        self.resource = type('Resources', (object,), dict())

    def _parse_url(self):
        url = self.url
        if callable(url):
            url = url()
        if url == self._last_url:
            return True  # parsed url is cached
        try:
            p = URLParser(url)
        except Exception as e:
            log.warning("unable to parse '%s': %s", url, str(e))
            return False
        else:
            self._url = url
            self._last_url = url
            self.host = p.host
            self.address = p.address
            self.port = p.port
            self.initial_path = p.path
            self.query = p.query
            self.is_ssl = p.is_ssl
            return True

    def add_resource(
                self,
                name,
                path,
                method,
                headers,
                is_json,
                is_verbose,
                trace,
                timeout,
                handler,
                wrapper,
                setup,
                is_form,
                required,
                optional,
            ):

        _headers = self.headers.copy()
        _headers.update(headers or {})

        if is_form is True:
            _headers['Content-Type'] = 'application/x-www-form-urlencoded'

        resource = MicroResource(
            name,
            path,
            method,
            _headers,
            is_json if is_json is not None else self.is_json,
            is_verbose if is_verbose is not None else self.is_verbose,
            trace,
            timeout or self.timeout,
            handler or self.handler,
            wrapper or self.wrapper,
            setup or self.setup,
            required or [],
            optional or {},
        )
        setattr(self.resource, name, Resource(self, resource))
        return resource


class Resource(object):

    def __init__(self, connection, resource):
        self.connection = connection
        self.resource = resource

    def __repr__(self):
        return 'connection.%s.resource.%s' % (self.connection.name, self.resource.name)

    def __call__(self, callback, *args, **kwargs):
        is_verbose = kwargs.pop('is_verbose', None)
        trace = kwargs.pop('trace', None)
        if len(args) != len(self.resource.substitution + self.resource.required):
            raise Exception('Incorrect number of required arguments')
        for k in kwargs.keys():
            if k not in self.resource.optional:
                raise Exception('Invalid keyword argument: %s' % k)

        path = self.resource.path
        if len(self.resource.substitution):
            sub, args = args[:len(self.resource.substitution)], args[len(self.resource.substitution):]
            path = path.format(**dict(zip(self.resource.substitution, sub)))

        body = dict(zip(self.resource.required, args)) if len(args) else {}
        body.update(self.resource.optional)
        body.update(kwargs)

        headers = {n: v() if callable(v) else v for n, v in self.resource.headers.items()}

        if self.resource.setup:
            path, headers, body = self.resource.setup(path, headers, body)

        if not self.connection._parse_url():
            return callback(1, 'unable to parse resource url')

        return connect_parsed(
            self.connection.network,
            self.connection.timer,
            callback,
            self.connection._url + self.resource.path,
            self.connection.host,
            self.connection.address,
            self.connection.port,
            self.connection.initial_path + self.resource.path,
            self.connection.query,
            self.connection.is_ssl,
            method=self.resource.method,
            headers=headers,
            body=body,
            is_json=self.resource.is_json,
            is_form=False,
            timeout=self.resource.timeout,
            wrapper=self.resource.wrapper,
            handler=self.resource.handler,
            evaluate=None,
            debug=is_verbose or self.resource.is_verbose,
            trace=trace or self.resource.trace,
        )


def parse_substitution(path):
    return [t[1] for t in string.Formatter().parse(path) if t[1] is not None]  # grab substitution names


class MicroResource(object):

    def __init__(
                self,
                name,
                path,
                method,
                headers,
                is_json,
                is_verbose,
                trace,
                timeout,
                handler,
                wrapper,
                setup,
                required,
                optional,
            ):
        self.name = name
        self.path = path
        self.method = method
        self.headers = headers
        self.is_json = is_json
        self.is_verbose = is_verbose
        self.trace = trace
        self.timeout = timeout
        self.handler = handler
        self.wrapper = wrapper
        self.setup = setup
        self.required = required
        self.optional = optional
        self.cid = 0

        self.substitution = parse_substitution(path)
