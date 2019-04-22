'''
The MIT License (MIT)

https://github.com/robertchase/spindrift/blob/master/LICENSE.txt
'''
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
        def cleanup_before_callback(rc, result):
            for cleanup in self._cleanup[::-1]:
                cleanup()
            self._callback(rc, result)
        return cleanup_before_callback

    def call(self, fn, args=None, kwargs=None, on_success=None, on_none=None,
             on_none_return=False, on_error=None, on_timeout=None):
        self.is_done = False

        def cb(rc, result):
            if rc == 0:
                _callback(self, fn, result, on_success, on_none_return,
                          on_none)
            else:
                _callback_error(self, fn, result, on_error, on_timeout)
            self.is_done = True

        if args is None:
            args = ()
        elif not isinstance(args, (tuple, list)):
            args = (args,)

        if kwargs is None:
            kwargs = {}

        task, cursor = inspect_parameters(fn, kwargs)

        if task:
            cb = Task(cb, self.cid, self.cursor)
        elif cursor:
            kwargs['cursor'] = getattr(self, 'cursor')

        log.debug('task.call fn=%s %s', fn, 'as task' if task else '')
        fn(cb, *args, **kwargs)
        return self


def inspect_parameters(fn, kwargs):

    task = False
    cursor = False

    parameters = inspect.signature(fn).parameters
    parameter_names = [p.name for p in parameters.values()]

    if len(parameter_names) and parameter_names[0] == 'task':
        task = True
    else:
        if 'cursor' in parameters and 'cursor' not in kwargs:
            cursor = True

    return task, cursor


def _callback(task, fn, result, on_success, on_none_return, on_none):
    if on_none_return and result is None:
        log.debug('task.callback, cid=%s, on_none_return', task.cid)
        return task.callback(0, result)
    if on_none and result is None:
        try:
            log.debug('task.callback, cid=%s, on_none fn=%s', task.cid, on_none)
            return on_none(task, result)
        except Exception as e:
            return task.callback(1, 'exception during on_none: %s' % e)
    if on_success:
        try:
            log.debug('task.callback, cid=%s, on_success fn=%s', task.cid,
                      on_success)
            return on_success(task, result)
        except Exception as e:
            return task.callback(1, 'exception during on_success: %s' % e)
    log.debug('task.callback, cid=%s, default success callback', task.cid)
    task.callback(0, result)


def _callback_error(task, fn, result, on_error, on_timeout):
    if on_timeout and result == 'timeout':
        try:
            log.debug('task.callback, cid=%s, on_timeout fn=%s', task.cid,
                      on_timeout)
            return on_timeout(task, result)
        except Exception as e:
            return task.callback(1, 'exception during on_timeout: %s' % e)
    if on_error:
        try:
            log.debug('task.callback, cid=%s, on_error fn=%s', task.cid,
                      on_error)
            return on_error(task, result)
        except Exception as e:
            return task.callback(1, 'exception during on_error: %s' % e)
    log.debug('task.callback, cid=%s, default error callback', task.cid)
    task.callback(1, result)
