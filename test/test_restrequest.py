import spindrift.http as http
import spindrift.rest.request as request


class MockHandler(object):
    def __init__(self, kwargs):
        self.id = 0
        try:
            http.HTTPHandler._setup(self)
        except Exception:
            pass
        for n, v in kwargs.items():
            setattr(self, n, v)

    def _rest_send(self, code, message, content, content_type, headers, close):
        self._respond_code = code
        self._respond_message = message
        self._respond_content = content
        self._respond_content_type = content_type
        self._respond_headers = headers
        self._respond_close = close


def new_request(**kwargs):
    return request.RESTRequest(MockHandler(kwargs))


def test_simple():
    r = new_request(http_content='test')
    assert r.http_content == 'test'


def test_json_content():
    r = new_request(http_content='{"a": 1, "b": "akk"}')
    assert r.json.get('a') == 1
    assert r.json.get('b') == 'akk'


def test_json_query_string():
    r = new_request(http_query={"a": 1, "b": "akk"})
    assert r.json.get('a') == 1
    assert r.json.get('b') == 'akk'


def test_json_form():
    r = new_request(http_content='a=1&b=akk')
    assert r.json.get('a') == '1'
    assert r.json.get('b') == 'akk'


def _call_simple(callback, rc=0, result=None):
    callback(rc, result)


def test_call_simple():
    r = new_request()
    r.call(_call_simple)
    assert r.handler._respond_code == 200


def test_call_success():

    def on_success(request, result):
        request._success = True

    r = new_request()
    r._success = False
    r.call(_call_simple, on_success=on_success)
    assert r._success


def test_call_success_code():
    r = new_request()
    r.call(_call_simple, on_success_code=123)
    assert r.handler._respond_code == 123


def test_call_error():

    def on_error(request, result):
        request._error = True

    r = new_request()
    r._error = False
    r.call(_call_simple, args=1, on_error=on_error)
    assert r._error


def test_call_none():

    def on_none(request, result):
        request._none = True

    r = new_request()
    r._none = False
    r.call(_call_simple, on_none=on_none)
    assert r._none


def test_call_none_404():
    r = new_request()
    r.call(_call_simple, on_none_404=True)
    assert r.handler._respond_code == 404


def _call_task(task, value):
    task.callback(0, value)


def test_call_task():
    def on_success(request, result):
        request._task = result

    r = new_request()
    r._task = None
    r.call(_call_task, args='task', on_success=on_success)
    assert r._task == 'task'


def _call_cursor(callback, cursor=None):
    callback(0, cursor)


def test_call_cursor():
    def on_success(request, result):
        request._cursor = result

    r = new_request()
    r.cursor = 'cursor'
    r.call(_call_cursor, on_success=on_success)
    assert r._cursor == 'cursor'
