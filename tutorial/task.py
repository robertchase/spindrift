ID = {'id': 0}
TASKS = {}


def create(request):
    desc = request.json['description']
    ID['id'] = ID['id'] + 1
    id = str(ID['id'])
    TASKS[id] = desc
    request.respond(201, {'id': id, 'description': desc})


def read(request, id=None):
    if id is None:
        return TASKS
    return {'id': id, 'description': TASKS[id]}


def update(request, id):
    desc = request.json['description']
    TASKS[id] = desc
    return {'id': id, 'description': desc}


def delete(request, id):
    del TASKS[id]
