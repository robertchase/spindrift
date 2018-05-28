from spindrift.rest.decorator import content_to_args, coerce


ID = {'id': 0}
TASKS = {}


def found(rest_handler):
    def _found(request, id, *args):
        if id not in TASKS:
            return rest_handler.respond(404)
        return rest_handler(request, id, *args)
    return _found


def list(request):
    return TASKS


@content_to_args('description')
def add(request, description):
    id = ID['id'] = ID['id'] + 1
    TASKS[id] = description
    request.respond(201, {'id': id, 'description': description})


@coerce(int)
@found
def get(request, id):
    return {'id': id, 'description': TASKS[id]}


@coerce(int)
@found
@content_to_args('description')
def update(request, id, description):
    TASKS[id] = description
    return {'id': id, 'description': TASKS[id]}


@coerce(int)
@found
def delete(request, id):
    del TASKS[id]
