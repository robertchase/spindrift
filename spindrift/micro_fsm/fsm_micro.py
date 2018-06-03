from fsm.FSM import STATE, EVENT, FSM
# add_arg
# add_config
# add_connection
# add_content
# add_database
# add_header
# add_log
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
  S_database=STATE('database',enter=actions['add_database'])
  S_setup=STATE('setup',enter=actions['add_setup'])
  S_teardown=STATE('teardown',enter=actions['add_teardown'])
  S_log=STATE('log',enter=actions['add_log'])
  S_server=STATE('server',enter=actions['add_server'])
  S_route=STATE('route',enter=actions['add_route'])
  S_method=STATE('method',enter=actions['add_method'])
  S_connection=STATE('connection',enter=actions['add_connection'])
  S_resource=STATE('resource',enter=actions['add_resource'])
  S_init.set_events([EVENT('server',[], S_server),EVENT('connection',[], S_connection),EVENT('config',[actions['add_config']]),EVENT('database',[], S_database),EVENT('setup',[], S_setup),EVENT('teardown',[], S_teardown),EVENT('log',[], S_log),])
  S_database.set_events([EVENT('server',[], S_server),EVENT('connection',[], S_connection),EVENT('config',[actions['add_config']]),EVENT('setup',[], S_setup),EVENT('teardown',[], S_teardown),EVENT('log',[], S_log),])
  S_setup.set_events([EVENT('server',[], S_server),EVENT('connection',[], S_connection),EVENT('config',[actions['add_config']]),EVENT('database',[], S_database),EVENT('teardown',[], S_teardown),EVENT('log',[], S_log),])
  S_teardown.set_events([EVENT('server',[], S_server),EVENT('connection',[], S_connection),EVENT('config',[actions['add_config']]),EVENT('database',[], S_database),EVENT('setup',[], S_setup),EVENT('log',[], S_log),])
  S_log.set_events([EVENT('server',[], S_server),EVENT('connection',[], S_connection),EVENT('config',[actions['add_config']]),EVENT('database',[], S_database),EVENT('setup',[], S_setup),])
  S_server.set_events([EVENT('route',[], S_route),EVENT('config',[actions['add_config']]),EVENT('connection',[], S_connection),])
  S_route.set_events([EVENT('arg',[actions['add_arg']]),EVENT('get',[], S_method),EVENT('post',[], S_method),EVENT('put',[], S_method),EVENT('delete',[], S_method),])
  S_method.set_events([EVENT('content',[actions['add_content']]),EVENT('get',[actions['add_method']]),EVENT('post',[actions['add_method']]),EVENT('put',[actions['add_method']]),EVENT('delete',[actions['add_method']]),EVENT('route',[actions['add_route']]),EVENT('config',[actions['add_config']]),EVENT('server',[], S_server),EVENT('connection',[], S_connection),EVENT('database',[], S_database),EVENT('setup',[], S_setup),EVENT('teardown',[], S_teardown),EVENT('log',[], S_log),])
  S_connection.set_events([EVENT('header',[actions['add_header']]),EVENT('resource',[], S_resource),EVENT('config',[actions['add_config']]),])
  S_resource.set_events([EVENT('resource',[], S_resource),EVENT('header',[actions['add_resource_header']]),EVENT('required',[actions['add_required']]),EVENT('optional',[actions['add_optional']]),EVENT('config',[actions['add_config']]),EVENT('server',[], S_server),EVENT('connection',[], S_connection),EVENT('database',[], S_database),EVENT('setup',[], S_setup),EVENT('teardown',[], S_teardown),EVENT('log',[], S_log),])
  return FSM([S_init,S_database,S_setup,S_teardown,S_log,S_server,S_route,S_method,S_connection,S_resource])
