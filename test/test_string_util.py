import pytest
import spindrift.string_util as string_util


@pytest.mark.parametrize('value,expected', [
    ('test', 'test'),
    ('#test', ''),
    ('\#test', '#test'),
    ('\#te\#st', '#te#st'),
    ('\#te#st', '#te'),
    ('te#s#t', 'te'),
    ('#te#s#t', ''),
    ('\f\o\o', '\f\o\o'),
    ('\f\o#o', '\f\o'),
    ('\f\o\#o', '\f\o#o'),
    ('\f\o\##o', '\f\o#'),
])
def test_un_comment(value, expected):
    assert string_util.un_comment(value) == expected


@pytest.mark.parametrize('value,args_expected,kwargs_expected', [
    ('', [], {}),
    ('a b c', ['a', 'b', 'c'], {}),
    ('a    b    c', ['a', 'b', 'c'], {}),
    ('a\tb\tc', ['a', 'b', 'c'], {}),
    ('a "b c d e f" c', ['a', 'b c d e f', 'c'], {}),
    ('a "b \\"c  d e f" c', ['a', 'b "c  d e f', 'c'], {}),
    ('a=b c=d', [], {'a': 'b', 'c': 'd'}),
    ('a =b c=d', [], {'a': 'b', 'c': 'd'}),
    ('a   =\tb c=d', [], {'a': 'b', 'c': 'd'}),
    ('a b c d=f g=h', ['a', 'b', 'c'], {'d': 'f', 'g': 'h'}),
])
def test_to_args(value, args_expected, kwargs_expected):
    args, kwargs = string_util.to_args(value)
    assert len(args) == len(args_expected)
    for a, b in zip(args, args_expected):
        assert a == b
    assert len(kwargs) == len(kwargs_expected)
    for k, v in kwargs.items():
        v == kwargs_expected[k]


@pytest.mark.parametrize('value,expected', [
    ('=', string_util.InvalidStartCharacter),
    ('a==', string_util.ConsecutiveEqual),
    ('a=b c', string_util.ExpectingKey),
    ('abc\\def', string_util.UnexpectedCharacter),
    ('abc"def', string_util.UnexpectedCharacter),
    ('abc\'def', string_util.UnexpectedCharacter),
    ('a=b c', string_util.ExpectingKey),
    ('a=b a=', string_util.DuplicateKey),
    ('a=b=', string_util.ConsecutiveKeys),
    ('a=', string_util.IncompleteKeyValue),
])
def test_to_args_errors(value, expected):
    with pytest.raises(expected):
        string_util.to_args(value)
