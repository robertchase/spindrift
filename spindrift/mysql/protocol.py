import struct

import spindrift.mysql._compat as compat
import spindrift.mysql.converters as converters
import spindrift.mysql.charset as charset
from spindrift.mysql.constants import CLIENT, COMMAND, FIELD_TYPE, SERVER_STATUS
import spindrift.mysql.fsm_protocol as fsm
import spindrift.mysql.util as util

import spindrift.mysql.packet as packet


class Protocol(object):

    def __init__(self, connection):
        self.connection = connection
        self.fsm = fsm.create(
            authenticate=self.act_authenticate,
            autocommit=self.act_autocommit,
            check_query_response=self.act_check_query_response,
            close=self.act_close,
            connected=self.act_connected,
            dump_greeting=self.act_dump_greeting,
            init_query=self.act_init_query,
            parse_auth_response=self.act_parse_auth_response,
            parse_greeting=self.act_parse_greeting,
            parse_password_response=self.act_parse_password_response,
            password=self.act_password,
            query=self.act_query,
            read_data_packet=self.act_read_data_packet,
            read_descriptor_packet=self.act_read_descriptor_packet,
            query_complete=self.act_query_complete,

            dump_packet=self.dump_packet,
        )
        self.fsm.state = 'init'
        if self.connection.context.trace:
            self.fsm.trace = self.connection.context.trace

        self.packet = packet.Packet()

        self.charset = 'utf8'
        self.encoding = charset.charset_by_name(self.charset).encoding

        self._callback = None
        self._query = None

    @property
    def context(self):
        return self.connection.context

    def dump_packet(self):
        self.packet.dump()

    def handle(self, data):
        if self.packet.handle(data):
            if self.packet.is_ok:
                event = 'ok'
            elif self.packet.is_eof:
                event = 'eof'
            else:
                event = 'packet'
            if not self.fsm.handle(event):
                self.connection.close('error handling event')
            else:
                self.packet.reset()
                self.handle(None)
        elif self.packet.error:
            self.connection.close(self.packet.error)

    def escape(self, obj, mapping=None):
        if isinstance(obj, compat.str_type):
            return "'" + self._escape_string(obj) + "'"
        return converters.escape_item(obj, self.charset, mapping=mapping)

    def _escape_string(self, s):
        if (self.server_status & SERVER_STATUS.SERVER_STATUS_NO_BACKSLASH_ESCAPES):
            return s.replace("'", "''")
        return converters._escape_string(s)

    def query(self, callback, sql, cls=None):
        self._callback = callback
        self._cls = cls
        if isinstance(sql, compat.text_type):
            sql = sql.encode(self.encoding, 'surrogateescape')
        self._query = sql
        self.fsm.handle('query')

    def act_query(self):
        if self._callback and self._query:
            self._execute_command(COMMAND.COM_QUERY, self._query)
            self._query = None
            self.fsm.handle('sent')

    def _execute_command(self, command, sql):
        self.packet.reset(0)
        if isinstance(sql, compat.text_type):
            sql = sql.encode(self.encoding)
        packet_size = min(packet.MAX_PACKET_LEN, len(sql) + 1)  # +1 is for command
        prelude = struct.pack('<iB', packet_size, command)
        p = prelude + sql[:packet_size-1]
        self.connection.send(p)

        if packet_size < packet.MAX_PACKET_LEN:
            return

        sql = sql[packet_size-1:]
        while True:
            packet_size = min(packet.MAX_PACKET_LEN, len(sql))
            self.write_packet(sql[:packet_size])
            sql = sql[packet_size:]
            if not sql and packet_size < packet.MAX_PACKET_LEN:
                break

    def act_read_descriptor_packet(self):
        f = packet.FieldDescriptorPacket(self.packet.data, self.encoding)

        field_type = f.type_code
        if field_type == FIELD_TYPE.JSON:
            encoding = self.encoding
        elif field_type in FIELD_TYPE.TEXT_TYPES:
            if f.charsetnr == 63:  # binary
                encoding = None
            else:
                encoding = self.encoding
        else:
            encoding = 'ascii'

        converter = converters.decoders.get(field_type)
        if converter is converters.through:
            converter = None
        self.converters.append((f.name, encoding, converter))
        self.fields.append('%s.%s' % (f.table_name, f.name) if self.connection.context.table else f.name)

    def act_read_data_packet(self):
        if self._cls is None:
            self._read_data_tuple()
        else:
            self._read_data_object()

    def _read_data_tuple(self):
        row = []
        for name, encoding, converter in self.converters:
            value = self.packet.read_length_coded_string()
            if value is not None:
                if encoding:
                    value = value.decode(encoding)
                if converter:
                    value = converter(value)
                row.append(value)
        self.result.append(tuple(row))

    def _read_data_object(self):
        row = {}
        for name, encoding, converter in self.converters:
            value = self.packet.read_length_coded_string()
            if value is not None:
                if encoding:
                    value = value.decode(encoding)
                if converter:
                    value = converter(value)
                row[name] = value
        self.result.append(self._cls(**row))

    def act_query_complete(self):
        result = tuple(self.result)
        if self.connection.context.column:
            result = (tuple(self.fields), result)
        self._callback(0, result)
        self._callback = None
        self._cls = None

    def act_parse_greeting(self):
        self.handshake = packet.Greeting(self.packet.data)
        return 'done'

    def act_init_query(self):
        self.fields = []
        self.converters = []
        self.result = []

    def act_authenticate(self):
        user = self.connection.user

        charset_id = charset.charset_by_name(self.charset).id
        if isinstance(user, compat.text_type):
            user = user.encode(self.encoding)

        data_init = struct.pack('<iIB23s', CLIENT.CAPABILITIES, 1, charset_id, b'')

        data = data_init + user + b'\0'

        authresp = b''
        if self.handshake._auth_plugin_name in ('', 'mysql_native_password'):
            authresp = util.scramble(self.connection.pswd.encode('latin1'), self.handshake.salt)

        data += struct.pack('B', len(authresp)) + authresp

        db = self.connection.db
        if db and self.handshake.server_capabilities & CLIENT.CONNECT_WITH_DB:
            if isinstance(db, compat.text_type):
                db = db.encode(self.encoding)
            data += db + b'\0'

        name = self.handshake._auth_plugin_name
        if isinstance(name, compat.text_type):
            name = name.encode('ascii')
        data += name + b'\0'

        self.write_packet(data)
        return 'sent'

    def act_parse_auth_response(self):
        auth_packet = self.packet
        if auth_packet.data[0:1] == b'\xfe':
            auth_packet.read_uint8()  # advance
            plugin_name = auth_packet.read_string()
            if self.handshake.server_capabilities & CLIENT.PLUGIN_AUTH and plugin_name == b'mysql_native_password':
                return 'password'
            else:
                raise Exception("Authentication plugin '%s' not configured" % plugin_name)
        else:
            return 'done'

    def act_check_query_response(self):
        if self.packet.is_ok:
            print(777)
            pass
        else:
            self.field_count = self.packet.read_length_encoded_integer()
            return 'done'

    def act_password(self):
        data = util.scramble(self.connection.pswd.encode('latin1'), self.packet.read_all())  # wrong scramble
        self.write_packet(data)

    def act_parse_password_response(self):
        if self.packet.is_ok:
            return 'done'
        return 'close'

    def act_dump_greeting(self):
        self.handshake.dump()

    def act_autocommit(self):
        if self.context.autocommit == self.handshake.autocommit:
            return 'ok'
        sql = 'SET AUTOCOMMIT = %s' % (1 if self.context.autocommit else 0)
        self._execute_command(COMMAND.COM_QUERY, sql)

    def act_close(self):
        self.connection.close('state-machine triggered close')

    def act_connected(self):
        self.connection.on_connected()
        return 'query'

    def write_packet(self, payload):
        self.packet.increment()
        packet.write(self.connection.send, self.packet.number, payload)
