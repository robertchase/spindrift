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
