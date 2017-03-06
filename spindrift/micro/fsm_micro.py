from spindrift.fsm.FSM import STATE, EVENT, FSM
# add_config
# add_connection
# add_header
# add_method
# add_route
# add_server
def create(**actions):
  S_init=STATE('init')
  S_connection=STATE('connection',enter=actions['add_connection'])
  S_server=STATE('server',enter=actions['add_server'])
  S_route=STATE('route',enter=actions['add_route'])
  S_init.set_events([EVENT('server',[], S_server),EVENT('connection',[], S_connection),EVENT('config',[actions['add_config']]),])
  S_connection.set_events([EVENT('header',[actions['add_header']]),EVENT('connection',[actions['add_connection']]),EVENT('config',[actions['add_config']]),EVENT('server',[], S_server),])
  S_server.set_events([EVENT('route',[], S_route),EVENT('server',[actions['add_server']]),EVENT('config',[actions['add_config']]),EVENT('connection',[], S_connection),])
  S_route.set_events([EVENT('get',[actions['add_method']]),EVENT('post',[actions['add_method']]),EVENT('put',[actions['add_method']]),EVENT('delete',[actions['add_method']]),EVENT('route',[actions['add_route']]),EVENT('config',[actions['add_config']]),EVENT('server',[], S_server),EVENT('connection',[], S_connection),])
  return FSM([S_init,S_connection,S_server,S_route])
