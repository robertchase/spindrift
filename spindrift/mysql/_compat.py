import sys

PYPY = hasattr(sys, 'pypy_translation_info')
JYTHON = sys.platform.startswith('java')
IRONPYTHON = sys.platform == 'cli'
CPYTHON = not PYPY and not JYTHON and not IRONPYTHON

range_type = range
text_type = str
long_type = int
str_type = str
unichr = chr
