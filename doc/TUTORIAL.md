# SPINDRIFT
## Tutorial

## Echo server

We begin with a `REST` service that echos content back to
the client.

```
def echo(request):
    return request.http_content
```
This function, found in `tutorial/echo.py`, is a `REST`
handler that takes a
[spindrift.rest.request.Request](REQUEST.md)
object as its only argument, and returns the content found in the request.

```
SERVER echo 12345
  ROUTE /echo
    POST tutorial.echo.echo
```

This
[micro](MICRO.md)
file, in `tutorial/echo.micro`, describes
a `REST` server listening on port `12345` for incoming `HTTP` requests
that have `/echo` as a resource. `POST` requests are routed to
the `echo` function in `tutorial/echo.py`.

Let's see this in action.
(`PYTHONPATH` includes `spindrift`, `ergaleia` and `fsm`).

```
# python -m spindrift.micro --micro tutorial/echo.micro
2018-05-26 12:30:48 MICRO [INFO] spindrift.micro:189> log level set to DEBUG
2018-05-26 12:30:48 MICRO [INFO] spindrift.micro:250> listening on echo port 12345
```

In another terminal, use `curl` to talk to the server.

```
# curl localhost:12345/echo --data-binary 'where is my mind'
where is my mind
```

The `http_content` (where is my mind) echos back immediately,
and, in the server terminal, log messages record the processing of the `REST` call.

```
2018-05-26 13:21:25 MICRO [INFO] spindrift.micro_fsm.handler:80> open: cid=1, 127.0.0.1:12345 <- 127.0.0.1:38708
2018-05-26 13:21:25 MICRO [INFO] spindrift.micro_fsm.handler:99> request cid=1, method=POST, resource=/echo, query=, groups=()
2018-05-26 13:21:25 MICRO [INFO] spindrift.micro_fsm.handler:108> response cid=1, code=200, message=OK, headers=None
2018-05-26 13:21:25 MICRO [INFO] spindrift.micro_fsm.handler:89> close: cid=1, reason=remote close, t=0.0066, rx=169, tx=92
```

The log messages show data about the peer, the `REST` resource, the response code and
statistics about handler duration, bytes received (rx) and bytes transmitted (tx).

## CRUD service

Now, we look at a set of CRUD calls.

```
class Tasks(dict):

    def __init__(self):
        self.id = 0

    @property
    def next_id(self):
        self.id += 1
        return self.id


TASKS = Tasks()


def format(id=0):
    if id:
        return dict(id=id, description=TASKS[id])
    return [format(key) for key in TASKS.keys()]


def create(request, description):
    id = TASKS.next_id
    TASKS[id] = description
    return format(id)


def read(request, id=None):
    if id and id not in TASKS:
        return 404
    return format(id)


def update(request, id, description):
    if id not in TASKS:
        return 404
    TASKS[id] = description
    return format(id)


def delete(request, id):
    if id not in TASKS:
        return 404
    del TASKS[id]
```
These functions, found in `tutorial/task.py`, form a `REST`
service that manages a basic task list. The task list
disappears when the service is stopped.

Here is a description of the service::

```
SERVER tasks 12345

  ROUTE /tasks$
    GET tutorial.task.read
    POST tutorial.task.create
        CONTENT description

  ROUTE /tasks/(?P<id>\d*)$
    TYPE int
    GET tutorial.task.read
    PUT tutorial.task.update
        CONTENT description
    DELETE tutorial.task.delete
```

This `micro` file,
in `tutorial/task.micro`, describes
a `REST` service listening on port `12345` for incoming `HTTP` requests
that have `/tasks` as a resource.

Some of the routes include a task id, depicted by the regex `(\d*)`,
matching a numeric value.
The parenthesis around the value define an argument to be passed
to the `REST` handler function.
The `?P<id>` part of the regex allows the group to have a name,
which is used here to note the purpose of the field.
the `TYPE int` directive causes the `id` group value to be
coerced to an `int`.

The `create` and `update` functions each accept another
argument in addition to `request`, whose value is pulled from
the `query string`, `form` or `json` body of the request. The
`CONTENT` directive specifies this additional parameter.

Let's see this in action.
(`PYTHONPATH` includes `spindrift`, `ergaleia` and `fsm`).

```
# python -m spindrift.micro --micro tutorial/task.micro
2018-05-26 12:30:48 MICRO [INFO] spindrift.micro:189> log level set to DEBUG
2018-05-26 12:30:48 MICRO [INFO] spindrift.micro:250> listening on echo port 12345
```

In another terminal, use `curl` to talk to the server.

```
> # list all tasks
> curl localhost:12345/tasks
[]

> # add a task
> curl localhost:12345/tasks -d description='make coffee'
{"id": 1, "description": "make coffee"}

> # list all tasks again
> curl localhost:12345/tasks
[{"id": 1: "description": "make coffee"}]

> # add another task
> curl localhost:12345/tasks -d description='buy donut'
{"id": "2", "description": "buy donut"}

> curl localhost:12345/tasks
[{"id": 1: "description": "make coffee", "id": 2: "description": "buy coffee"}]

> # change a task
> curl localhost:12345/tasks/1 -XPUT -d description='buy coffee'
{"id": 1, "description": "buy coffee"}

> curl localhost:12345/tasks
[{"id": 1: "description": "buy coffee", "id": 2: "description": "buy donut"}]

> # delete a task
> curl localhost:12345/tasks/2 -XDELETE

> curl localhost:12345/tasks
[{"id": 1: "description": "buy coffee"}]
```
