import functools
import logging
import string

from spindrift.rest.connect import connect_parsed, URLParser
from spindrift.micro_fsm.handler import OutboundHandler as MicroHandler


log = logging.getLogger(__name__)


class MicroConnect(object):

    def __init__(
                self,
                network,
                timer,
                url,
                headers,
                is_json,
                is_debug,
                timeout,
                handler,
                wrapper,
                setup,
                is_form,
            ):
        self.network = network
        self.timer = timer
        self.url = url
        self._last_url = None
        self.headers = headers
        self.is_json = is_json
        self.is_debug = is_debug
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
            return  # parsed url is cached
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
                is_debug,
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
        resource = MicroResource(
            name,
            path,
            method,
            _headers,
            is_json if is_json is not None else self.is_json,
            is_debug if is_debug is not None else self.is_debug,
            trace,
            timeout or self.timeout,
            handler or self.handler,
            wrapper or self.wrapper,
            setup or self.setup,
            is_form if is_form is not None else self.is_form,
            required or [],
            optional or {},
        )
        setattr(self.resource, name, functools.partial(self._call, resource))
        return resource

    def _call(self, resource, callback, is_debug=None, trace=None, *args, **kwargs):
        if len(args) != len(resource.substitution + resource.required):
            raise Exception('Incorrect number of required arguments')
        for k in kwargs.keys():
            if k not in resource.optional:
                raise Exception('Invalid keyword argument: %s' % k)

        path = resource.path
        if len(resource.substitution):
            sub, args = args[:len(resource.substitution)], args[len(resource.substitution):]
            path = path.format(**dict(zip(resource.substitution, sub)))

        body = dict(zip(resource.required, args)) if len(args) else {}
        body.update(kwargs)

        headers = {n: v() if callable(v) else v for n, v in resource.headers.items()}

        if resource.setup:
            path, headers, body = resource.setup(path, headers, body)

        if not self._parse_url():
            return callback(1, 'unable to parse resource url')

        return connect_parsed(
            self.network,
            self.timer,
            callback,
            self._url + resource.path,
            self.host,
            self.address,
            self.port,
            self.initial_path + resource.path,
            self.query,
            self.is_ssl,
            method=resource.method,
            headers=headers,
            body=body,
            is_json=resource.is_json,
            timeout=resource.timeout,
            wrapper=resource.wrapper,
            handler=resource.handler,
            is_debug=is_debug or resource.is_debug,
            trace=trace or resource.trace,
        )


class MicroResource(object):

    def __init__(
                self,
                name,
                path,
                method,
                headers,
                is_json,
                is_debug,
                trace,
                timeout,
                handler,
                wrapper,
                setup,
                is_form,
                required,
                optional,
            ):
        self.name = name
        self.path = path
        self.method = method
        self.headers = headers
        self.is_json = is_json
        self.is_debug = is_debug
        self.trace = trace
        self.timeout = timeout
        self.handler = handler
        self.wrapper = wrapper
        self.setup = setup
        self.is_form = is_form
        self.required = required
        self.optional = optional

        self.substitution = [t[1] for t in string.Formatter().parse(path) if t[1] is not None]  # grab substitution names
