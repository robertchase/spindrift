import struct

import spindrift.mysql._compat as compat
import spindrift.mysql.converters as converters
import spindrift.mysql.charset as charset
# from spindrift.mysql.constants import CLIENT, COMMAND, FIELD_TYPE, SERVER_STATUS
from spindrift.mysql.constants import CLIENT, COMMAND, FIELD_TYPE
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
            isolation=self.act_isolation,
            parse_auth_response=self.act_parse_auth_response,
            parse_greeting=self.act_parse_greeting,
            query=self.act_query,
            query_complete=self.act_query_complete,
            read_data_packet=self.act_read_data_packet,
            read_descriptor_packet=self.act_read_descriptor_packet,
            transaction=self.act_transaction,
            transaction_end=self.act_transaction_end,

            dump_packet=self.dump_packet,
        )
        self.fsm.state = 'init'
        if self.connection.context.fsm_trace:
            self.fsm.trace = self.connection.context.fsm_trace

        self.packet = packet.Packet()

        self.charset = 'utf8'
        self.encoding = charset.charset_by_name(self.charset).encoding

        self._callback = None
        self._query = None
        self._query_status = None

        self._transaction_start = False
        self._transaction_end = None

    @property
    def context(self):
        return self.connection.context

    def close(self):
        self.connection.close()

    @property
    def is_open(self):
        return self.connection.is_open

    @property
    def lastrowid(self):
        return self._query_status.insert_id

    @property
    def rows_affected(self):
        return self._query_status.affected_rows

    def dump_packet(self):
        self.packet.dump()

    def handle(self, data):
        if self.packet.handle(data):
            self.packet.increment()
            if self.packet.is_ok:
                self._ok = packet.OKPacket(self.packet.data, self.encoding)
                event = 'ok'
            elif self.packet.is_eof:
                event = 'eof'
            else:
                event = 'packet'
            if self.fsm.handle(event):
                self.packet.clear()
                self.handle(None)  # handle any buffered data
            else:
                self.connection.close('error handling event')
        elif self.packet.error:
            self._done(1, self.packet.error)

    def escape(self, obj, mapping=None):
        if isinstance(obj, compat.str_type):
            return "'" + self._escape_string(obj) + "'"
        return converters.escape_item(obj, self.charset, mapping=mapping)

    def _escape_string(self, s):
        # if (self.handshake.server_status & SERVER_STATUS.SERVER_STATUS_NO_BACKSLASH_ESCAPES):
        #     return s.replace("'", "''")
        return converters.escape_string(s)

    def query(self, callback, sql, start_transaction=False, end_transaction=None, cls=None):
        self._callback = callback
        self._cls = cls
        self._query = sql
        if not self.context.autocommit:
            self._transaction_start = start_transaction
            self._transaction_end = end_transaction
        self.fsm.handle('query')

    def act_query(self):
        if self._callback and self._query:
            if self._transaction_start:
                return 'transaction'
            self.connection.on_query_start(self._query)
            self._execute_command(COMMAND.COM_QUERY, self._query)
            self._query = None
            return 'sent'

    def _done(self, rc, result):
        if self._callback:
            callback, self._callback = self._callback, None
            callback(rc, result)

    def _execute_command(self, command, sql):
        if self.connection.context.sql_trace:
            self.connection.context.sql_trace(sql)
        if isinstance(sql, compat.text_type):
            sql = sql.encode(self.encoding)
        sql = struct.pack('B', command) + sql
        sequence = 0
        while True:
            packet_size = min(packet.MAX_PACKET_LEN, len(sql))
            self.write_packet(sql[:packet_size], sequence=sequence)
            sequence = None
            sql = sql[packet_size:]
            if not sql and packet_size < packet.MAX_PACKET_LEN:
                break

    def act_transaction(self):
        self._transaction_start = False
        self._execute_command(COMMAND.COM_QUERY, 'START TRANSACTION')

    def act_transaction_end(self):
        self._query_status = self._ok
        self.connection.on_query_end()
        if self._transaction_end:
            self._execute_command(COMMAND.COM_QUERY, self._transaction_end)
            self._transaction_end = None
        else:
            return 'ok'

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
        self._cls = None
        self._done(0, result)
        if self.connection.is_closed:
            return 'close'
        else:
            return 'done'

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

        self.write_packet(data, sequence=1)
        return 'sent'

    def act_parse_auth_response(self):
        auth_packet = self.packet
        if auth_packet.data[0:1] == b'\xfe':
            auth_packet.read_uint8()  # advance
            plugin_name = auth_packet.read_string()
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

    def act_dump_greeting(self):
        self.handshake.dump()

    def act_autocommit(self):
        if self.context.autocommit == self.handshake.autocommit:
            return 'ok'
        sql = 'SET AUTOCOMMIT = %s' % (1 if self.context.autocommit else 0)
        self._execute_command(COMMAND.COM_QUERY, sql)

    def act_isolation(self):
        if self.context.isolation is None:
            return 'ok'
        sql = 'SET SESSION TRANSACTION ISOLATION LEVEL %s' % self.context.isolation
        self._execute_command(COMMAND.COM_QUERY, sql)

    def act_close(self):
        self.connection.close(None)

    def act_connected(self):
        self.connection.on_connected()
        return 'query'

    def write_packet(self, payload, sequence):
        self.packet.reset(sequence)
        packet.write(self.connection.send, self.packet.number, payload)
        self.packet.increment()
