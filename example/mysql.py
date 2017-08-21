import argparse
from json import dumps, JSONEncoder

import spindrift.network as network
import spindrift.mysql.connection as mysql


parser = argparse.ArgumentParser(description='Run a mysql command. Query returns tuple of row-tuples.')
parser.add_argument('--user', '-u')
parser.add_argument('--pswd', '-p', default='')
parser.add_argument('--database', '-d')
parser.add_argument('--host', '-H', default='mysql')
parser.add_argument('--port', type=int, default=3306)
parser.add_argument('--transactions', action='store_true', default=False, help='turn autocommit off (default on)')
parser.add_argument('--dict', action='store_true', default=False, help='display query output as jsonified dict')
parser.add_argument('--column', action='store_true', default=False, help='return results as tuple of ((column_names,),(rows,)). overridden by --dict')
parser.add_argument('--table', action='store_true', default=False, help='add table name to --column or --dict')
parser.add_argument('--isolation', help='set isolation level (eg, "repeatable read")')
parser.add_argument('--trace', action='store_true', default=False, help='trace fsm and sql events')
parser.add_argument('query', nargs='+', help='sql statement to execute')

args = parser.parse_args()


class _decoder(JSONEncoder):
    def default(self, o):
        try:
            result = o.strftime('%Y-%m-%d %H:%M:%S')
        except AttributeError:
            pass
        else:
            return result
        return JSONEncoder.default(self, o)


def on_query(rc, result):
    if rc != 0:
        raise Exception(result)
    if args.dict:
        result = dumps(
            tuple([dict(zip(result[0], r)) for r in result[1]]),
            cls=_decoder,
            indent=4
        )
    print(result)
    cursor.close()


def trace(s, e, d, i):
    print('s=%s,e=%s,is_default=%s,is_internal=%s' % (s, e, d, i))


def sql_trace(sql):
    print('sql:', sql)


ctx = mysql.MysqlContext(
    user=args.user,
    pswd=args.pswd,
    db=args.database,
    autocommit=not args.transactions,
    column=args.column or args.dict,
    table=args.table,
    isolation=args.isolation,
    fsm_trace=trace if args.trace else None,
    sql_trace=sql_trace if args.trace else None,
)
n = network.Network()
cursor = n.add_connection(args.host, args.port, mysql.MysqlHandler, ctx).cursor
cursor.execute(on_query, ' '.join(args.query))

while cursor.is_open:
    n.service()
n.close()
