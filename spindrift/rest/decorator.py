import logging

from spindrift.dao.db import DB


log = logging.getLogger(__name__)


def content_to_json(*fields, **kwargs):
    """rest_handler decorator that converts handler.html_content to handler.json

    The content must be a valid json document or a valid URI query string (as
    produced by a POSTed HTML form). If the content starts with a '[' or '{',
    it is treated as json; else it is treated as a URI. The URI only expects
    one value per key.

    Arguments:
        fields - a list of field names. the names will be used to look up
                 values in the json dictionary which are appended, in order,
                 to the rest_handler's argument list. The specified fields
                 must be present in the content.

                 if a field name is a tuple, then the first element is the name,
                 which is treated as stated above, and the second element is
                 a type conversion function which accepts the value and returns
                 a new value. for instance ('a', int) will look up the value
                 for 'a', and convert it to an int (or fail trying).

                 if field name is a tuple with three elements, then the third
                 element is a default value.
        as_args - if true, append fields as described above, else add to decorated
                  call as kwargs.

    Errors:
        400 - json conversion fails or specified fields not present in json
    Notes:
         1. This is responsive to the is_delayed flag on the request.
    """
    as_args = kwargs.setdefault('as_args', True)

    def __content_to_json(rest_handler):
        def inner(request, *args):
            kwargs = dict()
            try:
                if fields:
                    args = list(args)
                    for field in fields:
                        if isinstance(field, tuple):
                            if len(field) == 3:
                                fname, ftype, fdflt = field
                                value = request.json.get(fname, fdflt)
                            else:
                                fname, ftype = field
                                value = request.json[fname]
                            if ftype:
                                value = ftype(value)
                        else:
                            fname = field
                            value = request.json[fname]
                        if as_args:
                            args.append(value)
                        else:
                            kwargs[fname] = value
            except KeyError as e:
                msg = 'Missing required key: %s' % str(e)
                log.warning('content error, cid=%s: %s', request.id, msg)
                return request.respond(400, msg)
            except Exception as e:
                msg = "Unable to read field '%s': %s" % (fname, e.message)
                log.warning('content error, cid=%s: %s', request.id, msg)
                return request.respond(400, msg)
            return rest_handler(request, *args, **kwargs)
        return inner
    return __content_to_json


def db_cursor(rest_handler):
    """ Add a databse cursor to a request

        The cursor is added to the request as the attribute 'cursor'
        and set to automatically close on request.respond. The
        delay() method is called on the request object to allow
        async calls to continue without a premature response.
    """
    def inner(request, *args, **kwargs):
        cursor = DB.cursor
        cursor.cid = request.id
        request.cursor = cursor
        request.cleanup = cursor.close
        request.delay()
        rest_handler(request, *args, **kwargs)
    return inner
