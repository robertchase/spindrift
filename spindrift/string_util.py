'''
The MIT License (MIT)

https://github.com/robertchase/spindrift/blob/master/LICENSE.txt
'''


def un_comment(s, comment='#'):
    """ uncomment a string

        truncate s at first occurrence of a non-escaped comment character

        remove escapes from escaped comment characters

        don't use when speed is important
    """
    escape = '\\'
    is_escape = False
    result = ''
    for c in s:
        if c == comment:
            if is_escape:
                is_escape = False
            else:
                return result
        if is_escape:
            result += escape
        if c == escape:
            is_escape = True
        else:
            is_escape = False
            result += c
    return result
