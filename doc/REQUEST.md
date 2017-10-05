# REQUEST Object
## A Reference Guide

A `request` object is the first parameter passed to a `spindrift` REST handler.
It provides access to the HTTP document attributes and to functions that
assist in async operation.

## attributes

`id` - unique connection id assigned by `spindrift.network.Handler`

`json` - dict version of:
1. the content as a json document
2. or the parsed query string
3. or the content as a form

`http_headers` - dict of document headers

`http_content` - document content

`http_method` - http method

`http_multipart` - list of `spindrift.http.HTTPPart` objects

`http_resource` - http resource from status line

`http_query_string` - http query string

`http_query` - parsed http status string as dict

##### special attribute

`cleanup` - assign a callable to execute when the request is done

A request is *done* when `request.respond` is called, implicitly or explicitly.

Multiple assignments to cleanup will result in each callable being run in turn.

## methods

### respond

The `respond` method sends an HTTP response to the connection peer.

There are no required parameters for this method. If no parameters are
specified, status code=200 and an empty document are sent.

The `respond` method is automatically called if a rest handler
returns without calling `delay`. Any values returned will be treated
as parameters to the `respond` method.

Multiple calls to `respond` will only result in one response to
the connection peer.

```
 respond(code=200, content='', headers=None, message=None, content_type=None)
```

##### parameters

`code` - HTTP status code (default=200) [Note 1]

`content` - HTTP document (default='') [Note 2]

`headers` - dict of HTTP headers

`message` - HTTP status message to accompany code [Note 3]

`content_type` - value for HTTP header 'Content-Type'

##### notes

1. if `code` is not an integer, then it is assumed to be the `content`

2. if `content` is a `dict`, `list` or `tuple`, then it is json.dumps'd and
and `content_type` is set to `application/json`.

3. The following `code`s are automatically supplied with a message:

* 200 - OK
* 201 - Created
* 204 - No Content
* 302 - Found
* 400 - Bad Request
* 401 - Not Authorized
* 403 - Forbidden
* 404 - Not Found
* 500 - Internal Server Error

### call

The `call` method provides a structured way to make async calls.

The signature for an async-callable function is:

```
my_async_function(callback, *args, **kwargs)
```

When `my_async_function` is complete, it calls `callback` with two arguments:

```
callback(rc, result)
```

If `my_async_function` completes successfully, `rc`==0 and `result` is the return value.
Otherwise, `rc`!=0 and `result` is an error message.

##### example

Before getting to the full signature of the call method, an example:

```
def my_handler(request, my_param):

    def on_done(rc, result):
        if rc == 0:
            request.respond(200, result)
        else:
            log.warning(result)
            request.respond(500)

    my_logic(on_done, my_param)
```

`my_logic` is an async-callable function, taking `on_done` as its `callback`.
The result of this pattern is a whole lot of boilerplate code, checking `rc` and responding in one of a few ways.
The purpose of the `call` method is to simplify this process by supplying a set of default actions for
typical situations. In this case, the use of `call` eliminates the `callback` entirely:

```
def my_handler(request, my_param):
    request.call(
        my_logic,
        args=my_param,
    )
```

The `call` method's default success action is to respond with the `result`;
the `call` method's default error action is to `log.warning` the `result` along with the request's
connection id and respond with a 500.

Here is one more example:

```
def my_handler(request, my_param):

    def my_success(request, result):
        request.respond({"data": result['my_field'])

    def request.call(
        my_logic,
        args=my_param,
        on_success=my_success,
    )
```

This shows an `on_success` parameter being specified. The `my_success` callable, and other
functions like it, take two parameters: `request` and `result`.
`request` is the same request object passed to `my_handler`, and `result` is the
return value from the `my_logic` callable.
The `call` method can pass control to a number of callables like `on_success`. Here is
the full signature:

##### signature

```
call(
    async_callable,
    args=args,
    kwargs=kwargs,
    on_success=on_success_callable,
    on_success_code=status code to respond with on success,
    on_error=on_error_callable,
    on_none=on_none_callable,
    on_none_404=boolean (default=False),
)
```

##### parameters

`async_callable` - a callable taking a `callback` as the first parameter (required)

`args` - an argument or list of arguments to `async_callable`

`kwargs` - a dict of keyword arguments to `async_callable`

`on_success` - an `async callback` function called when `rc`==0 [Note 1]

`on_success_code` - the HTTP status code to use when `rc`==0

`on_error` - an `async callback` function called when `rc`!=0 [Note 2]

`on_none` - an `async callback` function called when `rc`==0 and `result` is None

`on_none_404` - if True, respond with HTTP status code 404 if `rc`==0 and `result` is None

##### notes

1. an `async callback` function takes two arguments: `request` and `result`

2. the `on_error` `result` is an error message

##### task handling

This is magic.

If the first parameter of an `async_callable` argument to
the `call` method is *named* `task`, then an instance of
`spindrift.task.Task` is passed to the callable.
Think of the `task` as a lightweight `request`, or as a heavyweight `callback`,
which isolates lower-level logic from any awareness of the HTTP `request`.

*For the curious*: the `call` method provides its own `callback function` that handles all the
special cases (like `on_success`, `on_error`, etc.).
If the first parameter is named `task`, by inspection, then `call`'s `callback function`
is wrapped in a `spindrift.task.Task`.


##### cursor handling

This is magic.

If a request has a `cursor` attribute, it is automatically
added to the `task` parameter (see *task handling*) of any `async_callable`.

If an `async_callable` has a `kwarg` named `cursor`,
an no `cursor` `kwarg` is specified in the `call` method,
the `request`'s `cursor` attribute is provided as the `async_method`'s `cursor` `kwarg`.

*Justification*: Database interaction eventually requires a `cursor` and a `callback`.
The purpose of transparently moving the `cursor` from `request` to `task`,  and also from
`task` to `task`, is to remove the burden of this tedious and repetitive
work from the programmer.
This helps to support a `cursor`-per-`request` model, which may be desirable.

### delay

The `delay` method signals `spindrift` not to respond immediately
after the rest handler completes.

Simple rest handlers will return a value, which is then
sent as a response.
During async handling, the response to the connection's peer is
delayed until all async activity is complete.

 The `call` method
automatically calls `delay`.
