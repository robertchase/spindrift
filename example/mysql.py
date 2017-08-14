import spindrift.network as network
import spindrift.mysql.connection as mysql


class User(object):

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
    
    def __repr__(self):
        return '{id=%s, account=%s}' % (self.id, self.account)
    
def on_query(rc, result):
    print(301, 'query', rc, result)

ctx = mysql.MysqlContext(user='test', pswd='', db='test_auth', host='mysql')
n = network.Network()
c = n.add_connection(ctx.host, ctx.port, mysql.MysqlHandler, ctx)
c.cursor().execute(on_query, 'select * from user')
while c.is_open:
    n.service()
    n.close()
