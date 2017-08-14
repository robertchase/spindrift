from functools import partial
import hashlib
import struct

import spindrift.mysql._compat as compat


def byte2int(b):
    if isinstance(b, int):
        return b
    else:
        return struct.unpack("!B", b)[0]


def int2byte(i):
    return struct.pack("!B", i)


def join_bytes(bs):
    if len(bs) == 0:
        return ""
    else:
        rv = bs[0]
        for b in bs[1:]:
            rv += b
        return rv


def pack_int24(n):
    return struct.pack('<I', n)[:3]


def scramble(password, message):
    SCRAMBLE_LENGTH = 20
    sha_new = partial(hashlib.new, 'sha1')

    if not password:
        return b''
    stage1 = sha_new(password).digest()
    stage2 = sha_new(stage1).digest()
    s = sha_new()
    s.update(message[:SCRAMBLE_LENGTH])
    s.update(stage2)
    result = s.digest()
    return _crypt(result, stage1)


def _crypt(message1, message2):
    length = len(message1)
    result = b''
    for i in compat.range_type(length):
        x = (struct.unpack('B', message1[i:i+1])[0] ^
             struct.unpack('B', message2[i:i+1])[0])
        result += struct.pack('B', x)
    return result


def lenenc_int(i):
    if (i < 0):
        raise ValueError("Encoding %d is less than 0 - no representation in LengthEncodedInteger" % i)
    elif (i < 0xfb):
        return int2byte(i)
    elif (i < (1 << 16)):
        return b'\xfc' + struct.pack('<H', i)
    elif (i < (1 << 24)):
        return b'\xfd' + struct.pack('<I', i)[:3]
    elif (i < (1 << 64)):
        return b'\xfe' + struct.pack('<Q', i)
    else:
        raise ValueError("Encoding %x is larger than %x - no representation in LengthEncodedInteger" % (i, (1 << 64)))
