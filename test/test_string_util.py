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
