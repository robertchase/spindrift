import argparse
from json import dumps, JSONEncoder

import spindrift.network as network
import spindrift.mysql.connection as mysql


parser = argparse.ArgumentParser(description='Run a mysql command')
parser.add_argument('--user', '-u')
parser.add_argument('--pswd', '-p', default='')
parser.add_argument('--database', '-d')
parser.add_argument('--host', '-H', default='mysql')
parser.add_argument('--dict', action='store_true', default=False)
parser.add_argument('--column', action='store_true', default=False)
parser.add_argument('--table', action='store_true', default=False)
parser.add_argument('--trace', action='store_true', default=False)
parser.add_argument('query', nargs='+')

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


def trace(s, e, d, i):
    print('s=%s,e=%s,is_default=%s,is_internal=%s' % (s, e, d, i))


ctx = mysql.MysqlContext(
    user=args.user,
    pswd=args.pswd,
    db=args.database,
    host=args.host,
    column=args.column or args.dict,
    table=args.table,
    fsm_trace=trace if args.trace else None,
)
n = network.Network()
c = n.add_connection(ctx.host, ctx.port, mysql.MysqlHandler, ctx)
c.cursor().execute(on_query, ' '.join(args.query))

while c.is_open:
    n.service()
n.close()
