from spindrift.sequence import sequence, Step


def fn_a(callback, value):
    callback(0, value)


def fn_b(callback, value, fn_a=None):
    if value == 'ohno':
        return callback(1, 'yikes')
    if value == 'boom':
        raise Exception('boom')
    callback(0, fn_a + value)


def test_basic():

    done = False

    def on_complete(results):
        nonlocal done
        assert results['fn_a'] == 'abc'
        done = True

    assert sequence(
        lambda x, y: None,
        Step(fn_a, args='abc'),
        on_complete=on_complete,
    )

    assert done


def test_name():

    def on_complete(results):
        assert results['fn_a'] == 'abc'
        assert results['fn_a_prime'] == 'xyz'

    assert sequence(
        lambda x, y: None,
        Step(fn_a, args='abc'),
        Step(fn_a, name='fn_a_prime', args='xyz'),
        on_complete=on_complete,
    )


def test_include():

    def on_complete(results):
        assert results['fn_a'] == 'abc'
        assert results['fn_b'] == 'abcxyz'

    assert sequence(
        lambda x, y: None,
        Step(fn_a, args='abc'),
        Step(fn_b, args='xyz', include='fn_a'),
        on_complete=on_complete,
    )


def test_callback():

    done = False

    def on_done(rc, result):
        nonlocal done
        assert rc == 0
        assert result == 'abcxyz'
        done = True

    assert sequence(
        on_done,
        Step(fn_a, args='abc'),
        Step(fn_b, args='xyz', include='fn_a'),
    )

    assert done


def test_callback_complete():

    def on_done(rc, result):
        assert rc == 0
        assert result == 'abc,abcxyz'

    def on_complete(results):
        return ','.join(results.values())

    assert sequence(
        on_done,
        Step(fn_a, args='abc'),
        Step(fn_b, args='xyz', include='fn_a'),
        on_complete=on_complete,
    )


def test_exception():

    def on_done(rc, result):
        assert rc != 0
        assert result == 'step exception during sequence'

    assert sequence(
        on_done,
        Step(fn_b, args='boom'),
    )


def test_failure():

    def on_done(rc, result):
        assert rc != 0
        assert result == 'step failure during sequence'

    assert sequence(
        on_done,
        Step(fn_b, args='ohno'),
    )
