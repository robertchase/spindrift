import struct

import spindrift.mysql.charset as charset
from spindrift.mysql.constants import CLIENT, SERVER_STATUS
import spindrift.mysql.util as util


MAX_PACKET_LEN = 2**24-1

NULL_COLUMN = 251
UNSIGNED_CHAR_COLUMN = 251
UNSIGNED_SHORT_COLUMN = 252
UNSIGNED_INT24_COLUMN = 253
UNSIGNED_INT64_COLUMN = 254


def write(send, sequence, payload):
    data = util.pack_int24(len(payload)) + util.int2byte(sequence) + payload
    send(data)


class Packet(object):

    def __init__(self, data=None):
        self.number = 0
        self.data = data
        self.buffer = None
        self._error = None
        self._position = 0

    def __repr__(self):
        return 'n=%s, d=%s' % (self.number, self.data)

    def reset(self, sequence):
        self.clear()
        if sequence is not None:
            self.number = sequence
        else:
            self.increment()

    def clear(self):
        self.data = b''
        self._position = 0

    def increment(self):
        self.number = (self.number + 1) % 256

    def read(self, size):
        result = self.data[self._position:self._position+size]
        self._position += size
        return result

    def read_all(self):
        result = self.data[self._position:]
        self._position = None  # ensure no subsequent read()
        return result

    def read_uint8(self):
        result = self.data[self._position]
        self._position += 1
        return result

    def read_uint16(self):
        result = struct.unpack_from('<H', self.data, self._position)[0]
        self._position += 2
        return result

    def read_uint24(self):
        low, high = struct.unpack_from('<HB', self.data, self._position)
        self._position += 3
        return low + (high << 16)

    def read_uint32(self):
        result = struct.unpack_from('<I', self.data, self._position)[0]
        self._position += 4
        return result

    def read_uint64(self):
        result = struct.unpack_from('<Q', self.data, self._position)[0]
        self._position += 8
        return result

    def read_struct(self, fmt):
        s = struct.Struct(fmt)
        result = s.unpack_from(self.data, self._position)
        self._position += s.size
        return result

    def read_string(self):
        end_pos = self.data.find(b'\0', self._position)
        if end_pos < 0:
            return None
        result = self.data[self._position:end_pos]
        self._position = end_pos + 1
        return result

    def read_length_encoded_integer(self):
        """Read a 'Length Coded Binary' number from the data buffer.

        Length coded numbers can be anywhere from 1 to 9 bytes depending
        on the value of the first byte.
        """
        c = self.read_uint8()
        if c == NULL_COLUMN:
            return None
        if c < UNSIGNED_CHAR_COLUMN:
            return c
        elif c == UNSIGNED_SHORT_COLUMN:
            return self.read_uint16()
        elif c == UNSIGNED_INT24_COLUMN:
            return self.read_uint24()
        elif c == UNSIGNED_INT64_COLUMN:
            return self.read_uint64()

    def read_length_coded_string(self):
        """Read a 'Length Coded String' from the data buffer.

        A 'Length Coded String' consists first of a length coded
        (unsigned, positive) integer represented in 1-9 bytes followed by
        that many bytes of binary data.  (For example "cat" would be "3cat".)
        """
        length = self.read_length_encoded_integer()
        if length is None:
            return None
        return self.read(length)

    @property
    def is_ok(self):
        return self.data[0:1] == b'\0' and len(self.data) >= 7

    @property
    def is_error(self):
        return self.data[0:1] == b'\xff'

    @property
    def is_eof(self):
        return self.data[0:1] == b'\xfe' and len(self.data) < 9

    @property
    def error(self):
        if self._error:
            return self._error
        if not hasattr(self, 'data'):
            return None
        if not self.is_error or self.data[3:4] != b'#':
            return None
        return self.data[9:].decode('utf-8', 'replace')

    def is_auth_switch_request(self):
        return self.data[0:1] == b'\xfe'

    def handle(self, data=None):
        if data is None:
            data = b''
        if self.buffer is None:
            self.buffer = data
        else:
            self.buffer += data

        if len(self.buffer) < 4:
            return False

        low, high, packet_number = struct.unpack('<HBB', self.buffer[:4])
        packet_length = low + (high << 16)

        if packet_number != self.number:
            self._error = 'Packet number out of sequence (%s != %s)' % (packet_number, self.number)
            return False

        if len(self.buffer) - 4 < packet_length:
            return False

        self.data, self.buffer = self.buffer[4: 4+packet_length], self.buffer[4+packet_length:]

        if self.error:
            return False

        return True

    def dump(self):
        print('dump:', self.data)


class Greeting(Packet):

    def __init__(self, data):
        self.data = data
        self.parse()

    @property
    def autocommit(self):
        return bool(self.server_status & SERVER_STATUS.SERVER_STATUS_AUTOCOMMIT)

    def parse(self):
        data = self.data
        i = 0

        self.protocol_version = util.byte2int(data[i:i+1])
        i += 1

        server_end = data.find(b'\0', i)
        self.server_version = data[i:server_end].decode('latin1')
        i = server_end + 1

        self.server_thread_id = struct.unpack('<I', data[i:i+4])
        i += 4
        self.salt = data[i:i+8]
        i += 9  # 8 + 1(filler)

        self.server_capabilities = struct.unpack('<H', data[i:i+2])[0]
        i += 2

        if len(data) >= i + 6:
            lang, stat, cap_h, salt_len = struct.unpack('<BHHB', data[i:i+6])
            i += 6
            self.server_language = lang
            self.server_charset = charset.charset_by_id(lang).name

            self.server_status = stat

            self.server_capabilities |= cap_h << 16
            salt_len = max(12, salt_len - 9)

        # reserved
        i += 10

        if len(data) >= i + salt_len:
            # salt_len includes auth_plugin_data_part_1 and filler
            self.salt += data[i:i+salt_len]
            i += salt_len

        i += 1
        # AUTH PLUGIN NAME may appear here.
        if self.server_capabilities & CLIENT.PLUGIN_AUTH and len(data) >= i:
            # Due to Bug#59453 the auth-plugin-name is missing the terminating
            # NUL-char in versions prior to 5.5.10 and 5.6.2.
            # ref: https://dev.mysql.com/doc/internals/en/connection-phase-packets.html#packet-Protocol::Handshake
            # didn't use version checks as mariadb is corrected and reports
            # earlier than those two.
            server_end = data.find(b'\0', i)
            if server_end < 0:  # pragma: no cover - very specific upstream bug
                # not found \0 and last field so take it all
                self._auth_plugin_name = data[i:].decode('latin1')
            else:
                self._auth_plugin_name = data[i:server_end].decode('latin1')

        return self

    def dump(self):
        print('protocol_version', self.protocol_version)
        print('server_version', self.server_version)
        print('server_thread_id', self.server_thread_id)
        print('salt', self.salt)
        print('server_capabilities', self.server_capabilities)
        print('server_language', self.server_language)
        print('server_charset', self.server_charset)
        print('server_status', self.server_status)
        print('_auth_plugin_name', getattr(self, '_auth_plugin_name'))


class FieldDescriptorPacket(Packet):

    def __init__(self, data, encoding):
        super(FieldDescriptorPacket, self).__init__(data)
        self.parse(encoding)

    def parse(self, encoding):
        self.catalog = self.read_length_coded_string()
        self.db = self.read_length_coded_string()
        self.table_name = self.read_length_coded_string().decode(encoding)
        self.org_table = self.read_length_coded_string().decode(encoding)
        self.name = self.read_length_coded_string().decode(encoding)
        self.org_name = self.read_length_coded_string().decode(encoding)
        self.charsetnr, self.length, self.type_code, self.flags, self.scale = (self.read_struct('<xHIBHBxx'))


class OKPacket(Packet):

    def __init__(self, data, encoding):
        super(OKPacket, self).__init__(data)
        self.parse(encoding)

    def __repr__(self):
        return 'rows=%s, id=%s, status=%s, warning=%s, message=%s' % (
            self.affected_rows,
            self.insert_id,
            self.server_status,
            self.warning_count,
            self.message,
        )

    def parse(self, encoding):
        self._position += 1
        self.affected_rows = self.read_length_encoded_integer()
        self.insert_id = self.read_length_encoded_integer()
        self.server_status, self.warning_count = self.read_struct('<HH')
        self.message = self.read_all()
        self.has_next = self.server_status & SERVER_STATUS.SERVER_MORE_RESULTS_EXISTS
