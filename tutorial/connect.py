from spindrift.micro import micro


def read(request, id):
    request.call(
        micro.connection.posts.resource.read,
        args=id,
    )
