from itertools import chain
import logging


log = logging.getLogger(__name__)


class Step:
    """One step managed by a sequence
    """
    def __init__(self, fn, name=None, args=None, kwargs=None, include=None):
        """Create a Step

            Parameters:
                fn - a function to be called by the sequence (1)
                name - optional name for the Step (2)
                args - arguments for fn (None, scalar or tuple/list)
                kwargs - keyword arguments for fn (dict)
                include - results from previous Steps (3)

            Notes:

                1. The function takes a callback as the first argument.
                   The callback is invoked with two arguments when the
                   function is complete:

                       callback(rc, result)

                   "rc" is 0 on success, else failure
                   "result" is the function result on success, else an
                       error message.

                2. The results of each step are cached by the sequence
                   in a dict, keyed by Step name (which, if not specified,
                   if the function's __name__).

                3. Results from previous Steps in the sequence are available
                   to subsequent Steps by using the "include" parameter.
                   This parameter is either None (no results included),
                   a string (one result included) or a tuple/list of strings
                   (multiple results included). Each include string is
                   used to lookup the previous Step's result by Step name (see
                   Note 2) and passed to the current Step as a keyword
                   argument.
        """
        if include:
            include = include if isinstance(include, (tuple, list)) \
                else (include,)
        if args:
            args = args if isinstance(args, (tuple, list)) else (args,)
        self.fn = fn
        self.name = name or fn.__name__
        self.include = include or list()
        self.args = args or list()
        self.kwargs = kwargs or dict()

    @property
    def label(self):
        if self.name != self.fn.__name__:
            return 'Step<fn=%s name=%s>' % (self.fn.__name__, self.name)
        return 'Step<fn=%s>' % self.fn.__name__

    def __call__(self, callback, results):
        log.debug('step.call %s' % self.label)
        for key in self.include:
            self.kwargs[key] = results[key]
        self.fn(callback, *self.args, **self.kwargs)


def flatten(items):
    """flatten an iterable of scalars and tuples and lists to scalars
    """
    return list(
        chain(*(
            (s,) if not isinstance(s, (tuple, list)) else s for s in items
        ))
    )


def sequence(callback, *steps, on_complete=None, on_failure=None):
    """Execute a series of Step instances

        Parameters:
            callback - a callback function (1)
            steps - any number of Step instances
            on_complete - a function to run at the end of the sequence (2)
            on_failure - a function to run if a failure occurs (3)

        Notes:
            1. The callback is invoked with two arguments when the function is
               complete:

                   callback(rc, result)

                   "rc" is 0 on success, else failure
                   "result" is the function result on success, else an
                       error message.

               The result on success is the result value of the last Step
               in the sequence, unless on_complete is specified.

            2. If the sequence completes without error, then on_complete is
               called with a dict of Step results, keyed by Step name. The
               return value of on_complete is used as the result of the
               sequence callback.

            3. If a failure occurs, on_failure is called with a callback.
               The failure function can perform any operation after which
               the specified callback function is invoked. The result passed
               to the callback function will be used as the error result
               passed to the sequence callback.
    """

    steps = flatten(steps)

    class _context:
        def __init__(self):
            self.is_done = False
    context = _context()
    results = {}

    def done(rc, result):
        context.is_done = True
        callback(rc, result)

    def fail(message):
        if on_failure:
            return on_failure(lambda x, y: done(1, y))
        done(1, message)

    def on_step(rc, result):
        step = steps.pop(0)
        results[step.name] = result
        if rc != 0:
            log.warning('failure running %s: %s' % (step.label, result))
            return fail('step failure during sequence')
        if len(steps) == 0:
            if on_complete:
                result = on_complete(results)
            return done(0, result)
        next_step()

    def next_step():
        step = steps[0]
        try:
            step(on_step, results)
        except Exception:
            log.exception('failure running step: %s' % step.label)
            return fail('step exception during sequence')

    next_step()
    return context


def transaction(callback, cursor, *steps, on_complete=None):

    for step in steps:
        step.kwargs['cursor'] = cursor

    def failure(callback):
        def on_rollback(rc, result):
            if rc != 0:
                log.warning('failure on rollback: %s' % result)
            callback(1, 'unable to complete transaction sequence')
        cursor.rollback(on_rollback)

    return sequence(
        callback,
        Step(cursor.start_transaction),
        steps,
        Step(cursor.commit),
        on_complete=on_complete,
        on_failure=failure,
    )
