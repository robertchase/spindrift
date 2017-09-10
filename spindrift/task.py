import inspect
import logging


log = logging.getLogger(__name__)


class Task(object):

    def __init__(self, callback, cid=None, cursor=None):
        self._callback = callback
        self.cid = cid
        self.cursor = cursor
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

    def call(self, fn, args=None, kwargs=None, on_success=None, on_error=None, on_timeout=None, task=False):
        self.is_done = False

        def cb(rc, result):
            _callback(self, fn, rc, result, on_success, on_error, on_timeout)
            self.is_done = True

        if args is None:
            args = ()
        elif not isinstance(args, (tuple, list)):
            args = (args,)

        if kwargs is None:
            kwargs = {}

        if task:
            cb = Task(cb, self.cid, self.cursor)
        else:
            # pass along the cursor if available in task and needed in fn
            if hasattr(self, 'cursor') and 'cursor' not in kwargs:
                if 'cursor' in inspect.signature(fn).parameters:
                    kwargs['cursor'] = self.cursor

        log.debug('task.call %s', fn)
        fn(cb, *args, **kwargs)


def _callback(task, fn, rc, result, on_success, on_error, on_timeout):
    if rc == 0:
        if on_success:
            try:
                log.debug('task.callback, cid=%s, on_success fn=%s', task.cid, on_success)
                return on_success(task, result)
            except Exception as e:
                return task.callback(1, 'exception during on_success: %s' % e)
    else:
        if on_timeout and result == 'timeout':
            try:
                log.debug('task.callback, cid=%s, on_timeout fn=%s', task.cid, on_timeout)
                return on_timeout(task, result)
            except Exception as e:
                return task.callback(1, 'exception during on_timeout: %s' % e)
        if on_error:
            try:
                log.debug('task.callback, cid=%s, on_error fn=%s', task.cid, on_error)
                return on_error(task, result)
            except Exception as e:
                return task.callback(1, 'exception during on_error: %s' % e)
    log.debug('task.callback, cid=%s, default callback, rc=%s', task.cid, fn, rc)
    task.callback(rc, result)
