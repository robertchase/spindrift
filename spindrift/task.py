class Task(object):

    def __init__(self, callback):
        self._callback = callback
        self.is_done = True
        self._cleanup = []

    def __setattr__(self, name, value):
        if name == 'cleanup':
            self._cleanup.append(value)
        else:
            super(Task, self).__setattr__(name, value)

    @property
    def callback(self):
        for cleanup in self._cleanup:
            cleanup()
        return self._callback

    def call(self, fn, args=None, kwargs=None, on_success=None, on_error=None, on_timeout=None):
        self.is_done = False

        def cb(rc, result):
            _callback(self, rc, result, on_success, on_error, on_timeout)
            self.is_done = True

        if args is None:
            args = ()
        elif not isinstance(args, (tuple, list)):
            args = (args,)

        if kwargs is None:
            kwargs = {}

        fn(cb, *args, **kwargs)


def _callback(task, rc, result, on_success, on_error, on_timeout):
    if rc == 0:
        if on_success:
            try:
                return on_success(task, result)
            except Exception as e:
                return task.callback(1, 'exception during on_success: %s' % e)
    else:
        if on_timeout and result == 'timeout':
            try:
                return on_timeout(task, result)
            except Exception as e:
                return task.callback(1, 'exception during on_timeout: %s' % e)
        if on_error:
            try:
                return on_error(task, result)
            except Exception as e:
                return task.callback(1, 'exception during on_error: %s' % e)
    task.callback(rc, result)


def callback_as_task(fn):
    def inner(callback, *args, **kwargs):
        task = Task(callback)
        fn(task, *args, **kwargs)
    return inner