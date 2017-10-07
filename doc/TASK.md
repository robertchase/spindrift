# TASK Object
## A Reference Guide

A `task` object wraps a `callback`, adding async functionality.

The `task` is similar to the
`request` object, while hiding the latter's HTTP attributes.
This allows separation of rest-handler code from other logic
within the service.

## constructor

A `task` is usually created by a `request` or by another `task`.
If an operation is not started by an incoming REST call, for instance
by a `timer` event, then a `task` can be created by wrapping
a `callback` routine.

```
Task(callback, cid=None, cursor=None)
```

##### parameters

`callback` - a callable accepting (`rc`, `result`)

`cid` - connection id, assigned by a `request` (default=None)

`cursor` - `micro.db.cursor`. If multiple database
interactions or the use of transactions is desired, assigning a cursor
might be helpful. By setting `cleanup` to `cursor.close`, the `cursor` will
be automatically cleaned up when the `task` is complete. (default=None)

## attributes

`cid` - unique connection id passed from request [Note 1]

`cursor` - database cursor object [Note 2]

##### notes

1. The `cid` is used in `log.warning` message to tie
lower-level messages to the `request`. If the `task` is not
related to a `request`, this value is None.

2. If the `task` is created by a `request`, or another `task`, which already has a
database curosr, the cursor is automatically passed to the `task` on init.

##### special assign-only attribute

`cleanup` - assign a callable to execute when the task is done

A task is *done* when `task.callback` is called, implicitly or explicitly.

Multiple assignments to cleanup will result in each callable being run in turn.

## methods

### callback

The `callback` method provides direct access to the wrapped `callback` from the constructor.

### call

The `call` method provides a structured way to make async calls.

See the description of the `call` method for `request`.

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

`on_none` - an `async callback` function called when `rc`==0 and `result` is None

`on_error` - an `async callback` function called when `rc`!=0 [Note 2]

`on_timeout` - an `async callback` function called with `rc`==` and `result` == 'timeout'


##### notes

1. an `async callback` function takes two arguments: `request` and `result`

2. the `on_error` `result` is an error message

##### cursor handling

See the `cursor handling` section for `request`.

##### task handling

See the `task handling` section for `request`.
