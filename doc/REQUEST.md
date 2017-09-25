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

Multiple calls to cleanup will result in each callable being run in turn.

## methods

### respond

`respond()`

### call

The `call` method on the request provides a structured way to make async calls.

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

    def success(rc, result):
        if rc == 0:
            request.respond(200, result)
        else:
            log.warning(result)
            request.respond(500)

    my_logic(success, my_param)
```

The result of this pattern is a whole lot of boilerplate code, checking `rc` and responding in one of a few ways.
The purpose of the `call` method is to simplify this process by supplying a set of default actions for
typical situations. In this case, the use of `call` eliminates the callback entirely:

```
def my_handler(request, my_param):
    request.call(
        my_logic,
        args=my_param,
    )
```

The request handler's async activity is chained together through `request_cb` functions with this signature:

```
request_cb(request, result)
```

Where `request` is the request object, and `result` is the response from the called function.
This pattern allows the request to maintain state, and keep moving forward despite the async discontinuities.

```
call(
    async_callable,
    args=arg or list of args for callable,
    kwargs=dict of kwargs for callable,
    on_success=request_cb,
)
```


### delay
