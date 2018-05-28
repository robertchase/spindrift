ID = {'id': 0}
TASKS = {}


def not_found(rest_handler):
    def _not_found(request, *args):
        try:
            return rest_handler(request, *args)
        except KeyError:
            return request.respond(404)
    return _not_found


def list(request):
    return [{
        'id': id,
        'description': description
        } for id, description in TASKS.items()
    ]


def add(request):
    desc = request.json['description']
    id = ID['id'] = ID['id'] + 1
    id = str(id)
    TASKS[id] = desc
    request.respond(201, {'id': id, 'description': desc})


@not_found
def get(request, id):
    return {'id': id, 'description': TASKS[id]}


@not_found
def update(request, id):
    desc = request.json['description']
    TASKS[id] = desc
    return {'id': id, 'description': desc}


@not_found
def delete(request, id):
    del TASKS[id]
