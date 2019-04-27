# MICRO File
## A Reference Guide

A `micro` file describes a micro-service, leaving
the implementation of service logic to custom python functions.
Things like network, routing, database and logging are described in
a `micro` file, and managed by the *spindrift* framework.

## Structure of a `micro` file

A `micro` file is a set of single-line directives that each specify some aspect of a service.
A directive accepts parameters and sometimes creates a set of one or more `config` file records.

A directive starts with a directive-type token followed by some parameters. For example:

```
DATABASE user=foo database=bar
```

This record's directive-type is *DATABASE*, and the parameters *user* and *database* are specified.
The directive-type is case insensitive, although, upper case helps legibility.
The parameter names *are* case sensitive.

A directive may automatically create one or more config file records.
The *DATABASE* directive creates a number of config records. Here are a few:

```
db.user=foo
db.database=bar
```

The config file, if it exists, is read after parsing the `micro` file, and overrides any
previously specified defaults.
Treat the `micro` file as code, and use the config file for run time configuration.

Boolean values, for instance *is_debug*, can be set to any case-insensitive
version of *true* or *false*.

## Directives

### DATABASE

```
DATABASE is_active=true user=None database=None host=None port=3306 isolation='READ COMMITTED' timeout=60.0 long_query=0.5 fsm_trace=False
```

The `database` directive defines a connection to a MySQL database.
Other databases *can* be supported, but are not at this time.

A service does not maintain a connection to the database instance; rather, request handlers can establish a connection
for the duration of a request to handle any database activity. Connections are short in duration and provided on demand.

##### parameters

`is_active` - enables or disables database connectivity

`user` - database user

`database` - database name

`host` - database host

`port` - database port

`isolation` - session isolation level established at connection

`timeout` - maximum time, in seconds, that the connection can remain open

`long_query` - log warning message for queries exceeding specified seconds

`fsm_trace` - if true, log debug messages for driver state-event transitions


##### config

```
db.is_active=true env=DATABASE_IS_ACTIVE
db.user=None env=DATABASE_USER
db.password=None env=DATABASE_PASSWORD
db.database=None env=DATABASE_NAME
db.host=None env=DATABASE_HOST
db.port=3306 env=DATABASE_PORT
db.isolation='READ COMMITTED' env=DATABASE_ISOLATION
db.timeout=60.0 env=DATABASE_TIMEOUT
db.long_query=.5 env=DATABASE_LONG_QUERY
db.fsm_trace=false env=DATABASE_FSM_TRACE
```

### LOG

```
LOG name=MICRO level=debug is_stdout=true
```

The `log` directive overrides default logging behavior for *spindrift*.
By default, log messages are created with the *TAG* `MICRO`, with log level
set to `DEBUG` and with messages sent to stdout.
The value for `log.level` is case insensitive, and can be any
valid log level, typically, *debug* or *info*.

##### config

```
log.name=MICRO env=LOG_NAME
log.level=DEBUG env=LOG_LEVEL
log.is_stdout=true env=LOG_IS_STDOUT
```

### ENUM

```
ENUM name item1 item2 ... itemN to_upper=false to_lower=false
```

The `enum` directive defines a set of tokens (`item1` to `itemN`)
that can be used to constrain values in an `ARG` or `CONTENT` directive.
The `to_upper` and `to_lower` options force the value being constrained to the specified case.

##### Example

```
ENUM sort_direction ASC DESC to_upper=true
```

This defines an `enum` named `sort_direction` which forces an `arg` or `content` value
to be one of (`ASC`, `DESC`).

This `enum` could be used like this:

```
CONTENT orderby enum=sort_direction
```

to constrain an `orderby` query-string parameter.

### SERVER

```
SERVER name port
```

The `server` directive defines a port listening for incoming HTTP connections.
The `name` parameter is used in log messages and in the config.

##### config

```
server.[name].port=[port] env=SERVER_[name]_PORT
server.[name].is_active=true env=SERVER_[name]_IS_ACTIVE
server.[name].ssl.is_active=false env=SERVER_[name]_SSL_IS_ACTIVE
server.[name].ssl.keyfile= env=SERVER_[name]_SSL_KEYFILE
server.[name].ssl.certfile= env=SERVER_[name]_SSL_CERTFILE
```

A server is active by default, and operates without ssl. If `ssl.is_active=true`
is specified in the config, the `ssl.keyfile` and `ssl.certfile` must also
be specified, and must point to existing files.

### ROUTE

```
ROUTE [pattern]
```

The `route` directive defines a regular expression used to match
the *path* in incoming HTTP documents.

The `pattern` can include regex groups, whose matched values are passed as arguments
to the rest handler.


### ARG

```
ARG type=None enum=None
```

The `arg` directive defines a type-coercion function or `enum`
for a `route pattern`'s
regex group.

If `enum` is specified,
the value parsed from the path must match an already defined `enum`.
The allowed values are constrained to the tokens in the `enum`.

If `type` is specified,
the value parsed from the path is
wrapped with the specified function before being
added as a handler's parameter.
The function may transform the value in any way, or raise a ValueError.

Some built-in functions are available:

* int - ensure value is composed of only numeric characters, return int
* count - ensure value is a positive integer (counting number), return int
* bool - transform `true` (any case) or `1` to True, and `false` (any case) or `0` to False

Otherwise, `type` is a dot-delimited path to a custom function, which will
be dynamically loaded.

Each `ARG` directive is paired to the regex groups in sequence. There cannot
be more `ARG` directives than regex groups, but there can be fewer.

### GET / POST / PUT / DELETE

A `route` directive is not useful without
one or more of the following
directives describing how to handle HTTP methods.

```
[GET|POST|PUT|DELETE] [path]
```

These directives define a code path to run when the respective HTTP method is received.

These directives will be associated with the most recently encountered `route` directive.

##### Example

```
ROUTE /users/(\d+)$
  GET myservice.handlers.user.get
  PUT myservice.handlers.user.update
```

Here, the function `get` in the module `myservice/handlers.user.py` will be called
when an HTTP document's method matches `GET` and the path matches `/users/123` (or any number).

The function `update` in the program `myservice/handlers.user.py` will be called
when an HTTP document's method matches `PUT` and the path matches `/users/456` (or any number).

### CONTENT
```
CONTENT name type=None enum=None is_required=True
```

The `content` directive defines a keyword argument to the rest handler
that is extracted from the http document.
The `type` parameter, if specified, acts in the same way as the `arg` directive.
The `enum` parameter, if specified, acts in the same way as the `arg` directive.
The `is_required` parameter indicates if the `content` argument is required
to be present.

The parameter is located in the http document as a key value-pair in one of:

1. http_body as a json dictionary
2. query string
3. http_body as form data

##### Example

```
ROUTE /users/(\d+)/age$
  ARG int
  PUT myservice.handlers.user.update_age
    CONTENT age int
```

Here the function `update_age` in the module `myservice/handlers/user`
will be called when an HTTP document's method matches `PUT` and the path
matches `/users/123/age` (or any number).

If the `PUT` call includes the following body:
```
{
  "age": 50
}
```

then `age=50` will be passed to the `update_age` handler.

The `user_id` argument will be coerced to an `int` (123), as will `age` (50).

Here is a possible signature for the `update_age` handler (including
the `request` argument, which is passed to all handlers):
```
def update_age(request, user_id, age):
  pass
```

### CONNECTION

```
CONNECTION name url=None is_json=True is_verbose=True timeout=5.0 handler=None wrapper=None setup=None is_form=False code=None
```

The `connection` directive defines an outbound connection to a REST API.

A `connection` directive is combined with a `resource` directive
before a an outbound API resource is completely described.
More than one `resource` can be associated with a `connection`.

##### example

```
CONNECTION test https://jsonplaceholder.typicode.com
  RESOURCE users /users/{user_id}
```

This creates a function:

```
from spindrift.micro import micro
micro.connection.test.resource.users(callback, user_id)
```

which takes a `callback` function followed by `user_id`. When the
REST call is complete, the callback is called with `(0, result)` on success,
or `(1, error_message)` on failure.

This function does an HTTP GET on `https://jsonplaceholder.typicode.com/users/123`
(or whatever user_id is specified) and returns the result as a python object
(the json loads'd HTTP content).

##### parameters

`name` - name of the connection

`url` - first portion of the url (completed by each `resource`) [Note 1] [Note 2]

`is_json` - json.loads successful result (default=True)

`is_verbose` -  log `info` messages at open and close of connection (default=True) [Note 3]

`timeout` - tolerable period of network inactivity in seconds (default=5.0) [Note 4]

`handler` - path to handler class for connection (default=None) [Note 5]

`wrapper` - path to wrapper callable for successful result (default=None)

`setup` - path to setup callable (default=None) [Note 6]

`is_form` - treat content as application/x-www-form-urlencoded (default=False)

`code` path to dynamic url callable (default=None) [Note 7]

##### notes

[1] *typically*: scheme://host:port.

[2] a url is resolved against the dns one time and
the result is cached. in the case of a url assigned by `code`, the url is
resolved any time it changes.

[3] the following messages are produced:

* `open oid=[connection id]: [server ip]:[server port] <- [remove ip]:[remote port]`
* http: `close oid=[connection id], reason=[close reason], opn=[time to connect], dat=[time to response data received], tot=[total time to close] rx=[bytes received], tx=[bytes sent]`
* https: `close oid=[connection id], reason=[close reason], opn=[time to connect], rdy=[time to ssl handshake complete], dat=[time to response data received], tot=[total time to close] rx=[bytes received], tx=[bytes sent], ssl handshake [success or fail]`

[4] if function ends in timeout, the callback is invoked with `(1, 'timeout')`

[5] handler is subclass of `spindrift.connect.ConnectHandler`

[6] used to perform unusual setup logic
(for instance rendering an XML document from `args` and `kwargs`);
called with `(path, headers, body)` and must return the same three
attributes, modified as necessary.

[7] some urls cannot be known until runtime.
the `code` callable allows
url assignment to be delayed until the connection is made.

##### config

```
connection.[name].url=url env=CONNECTION_[name]_URL
connection.[name].is_active=True env=CONNECTION_[name]_IS_ACTIVE
connection.[name].is_verbose=is_verbose env=CONNECTION_[name]_IS_VERBOSE
connection.[name].timeout=timeout env=CONNECTION_[name]_TIMEOUT
```

### HEADER

```
HEADER key default=None config=None code=None
```

The `header` directive defines an HTTP header for the most recently defined `resource` or `connection`.

An HTTP header record is of the form:

```
[key]: [value]
```

The `value` is determined by:

1. what is returned by the `code` callable, if specified,
2. or what is found in the `config`, if specified,
3. or the `default`

At least one of `default`, `config` or `code` must be specified.

##### parameters

`default` - default value for the header (default=None)

`config` - name of the key in the config (can be different from `key` (default=None)

`code` - path to callable returning a value for the header (default=None)

##### config

```
connection.[name].header.[key]=[value] env=CONNECTION_[name]_HEADER_[key]
```

**or**

```
connection.[name].resource[name].header.[key]=[value] env=CONNECTION_[name]_RESOURCE_[name]_HEADER_[key]
```

### RESOURCE
```
RESOURCE name path method=GET is_json=None is_verbose=None trace=None timeout=None handler=None wrapper=None setup=None is_form=None
```

The `resource` directive defines a resource bound to the most recent `connection` directive.

##### micro function

The `resource` creates a function on `spindrift.micro.micro` that looks like this:

```
micro.connection.[name].resource.[name](callback, *args, **kwargs)
```

The `callback` parameter is a callback function which is called when the `resource` function is complete.
On success, the callback
is called with `(0, result)`; on failure `(1, error_message)`.

The `args` and `kwargs` are defined by:
1. substitution parameters in `path`

    substitution parameters are curly-bracket delimited tokens (eg, `/foo/{bar}/foobar` defines `bar` as a substitution parameter).

2. `required` directives associated with the `resource`
3. `optional` directives associated with the `resource`

The `args` are used, in order, to modify the path, and then to satisfy the `required` directives.
The number of `args` must match the number of substitution parameters plus the number of `required` directives.

The `kwargs` are used to supply `optional` directive values.

##### forming the body

The HTTP body is, by default, a jsonified dict formed from the
`required` arguments and the `optional` arguments.

The `required` arguments are added to the dict using the argument's `name` as the key;
all `optional` arguments are added in a similar fashion.
If no `required` or `optional` arguments are specified, then the body is empty.

##### parameters
`name` - name of the `resource`

`path` - path of the `resource` (appended to `connection` url)

`is_json` - override `connection` `is_json` (default=None)

`is_verbose` - override `connection` `is_verbose` (default=None)

`trace` - log `debug` messages for incoming and outgoing data [Note]

`timeout` - override `connection` `timeout` (default=None)

`handler` - override `connection` `handler` (default=None)

`wrapper` - override `connection` `wrapper` (default=None)

`setup` - override `connection` `setup` (default=None)

`is_form` - override `connection` `is_form` (default=None)

##### config
```
connection.[name].resource.[name].is_verbose= env=CONNECTION_[name]_RESOURCE_[name]_IS_VERBOSE
```

### REQUIRED

```
REQUIRED name
```

The `required` directive defines a required argument for the most recent `resource` directive.

A `required` argument must be supplied to the `resource` function.

### OPTIONAL

```
OPTIONAL name default=None config=None validate=None
```

The `optional` directive defines an optional argument for the most recent `resource` directive.

The parameter value is determined by:

1. an env variable (if config value is specified): `CONNECTION_[name]_RESOURCE_[name]_[config]`,
2. the config value, if specified,
3. the the default value, if specified,
3. otherwise the value is None

If a [key]=[value] `kwarg` is specified in the function call, this value overrides any of the above.

##### parameters

`name` - optional parameter name used as `kwargs` key if `value` is specified

`default` - default option value

`config` - config file name `connection.[name].resource.[name].[config]`
