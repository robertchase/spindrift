import functools


class MicroConnect(object):

    def __init__(
                self,
                name,
                url=None,
                is_json=True,
                is_debug=False,
                timeout=5.0,
                handler=None,
                wrapper=None,
                setup=None,
                is_form=None,
            ):
        self.name = name
        self.url = url
        self.is_json = is_json
        self.is_debug = is_debug
        self.timeout = timeout
        self.handler = handler
        self.wrapper = wrapper
        self.setup = setup
        self.is_form = None

        self._resources = {}
        self.resource = type('Resources', (object,), dict())

    def add_resource(
                self,
                name,
                path,
                method='GET',
                is_json=None,
                is_debug=None,
                trace=False,
                timeout=None,
                handler=None,
                wrapper=None,
                setup=None,
                is_form=None,
            ):
        resource = MicroResource(
            name,
            path,
            method,
            is_json or self.is_json,
            is_debug or self.is_debug,
            trace,
            timeout or self.timeout,
            handler or self.handler,
            wrapper or self.wrapper,
            setup or self.setup,
            is_form or self.is_form or False,
        )
        self._resources.append(resource)
        setattr(self.resource, name, functools.partial(self._call, name))
        return resource

    def _call(self, name, is_debug=None, trace=None, *args, **kwargs):
        resource = self._resources[name]
        resource


class MicroResource(object):

    def __init__(
                name,
                path,
                method,
                is_json,
                is_debug,
                trace,
                timeout,
                handler,
                wrapper,
                setup,
                is_form,
            ):
        pass
