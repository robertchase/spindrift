from spindrift.fsm.FSM import STATE, EVENT, FSM
# add_config
# add_connection
# add_header
# add_method
# add_optional
# add_required
# add_resource
# add_resource_header
# add_route
# add_server
# add_setup
# add_teardown
def create(**actions):
  S_init=STATE('init')
  S_server=STATE('server',enter=actions['add_server'])
  S_route=STATE('route',enter=actions['add_route'])
  S_connection=STATE('connection',enter=actions['add_connection'])
  S_resource=STATE('resource',enter=actions['add_resource'])
  S_init.set_events([EVENT('server',[], S_server),EVENT('connection',[], S_connection),EVENT('config',[actions['add_config']]),EVENT('setup',[actions['add_setup']]),EVENT('teardown',[actions['add_teardown']]),])
  S_server.set_events([EVENT('route',[], S_route),EVENT('server',[actions['add_server']]),EVENT('config',[actions['add_config']]),EVENT('connection',[], S_connection),EVENT('setup',[actions['add_setup']]),EVENT('teardown',[actions['add_teardown']]),])
  S_route.set_events([EVENT('get',[actions['add_method']]),EVENT('post',[actions['add_method']]),EVENT('put',[actions['add_method']]),EVENT('delete',[actions['add_method']]),EVENT('route',[actions['add_route']]),EVENT('config',[actions['add_config']]),EVENT('server',[], S_server),EVENT('connection',[], S_connection),EVENT('setup',[actions['add_setup']]),EVENT('teardown',[actions['add_teardown']]),])
  S_connection.set_events([EVENT('connection',[actions['add_connection']]),EVENT('config',[]),EVENT('header',[actions['add_header']]),EVENT('resource',[], S_resource),EVENT('server',[], S_server),EVENT('setup',[actions['add_setup']]),EVENT('teardown',[actions['add_teardown']]),])
  S_resource.set_events([EVENT('resource',[], S_resource),EVENT('header',[actions['add_resource_header']]),EVENT('required',[actions['add_required']]),EVENT('optional',[actions['add_optional']]),EVENT('config',[actions['add_config']]),EVENT('server',[], S_server),EVENT('connection',[], S_connection),EVENT('setup',[actions['add_setup']]),EVENT('teardown',[actions['add_teardown']]),])
  return FSM([S_init,S_server,S_route,S_connection,S_resource])
