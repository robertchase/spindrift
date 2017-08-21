from spindrift.fsm.FSM import STATE, EVENT, FSM
# authenticate
# autocommit
# check_query_response
# close
# connected
# init_query
# isolation
# parse_auth_response
# parse_greeting
# query
# query_complete
# read_data_packet
# read_descriptor_packet
# transaction
# transaction_end
def create(**actions):
  S_init=STATE('init')
  S_greeting=STATE('greeting',enter=actions['parse_greeting'])
  S_authenticate=STATE('authenticate',enter=actions['authenticate'])
  S_autocommit=STATE('autocommit',enter=actions['autocommit'])
  S_isolation=STATE('isolation',enter=actions['isolation'])
  S_connected=STATE('connected',enter=actions['connected'])
  S_transaction=STATE('transaction',enter=actions['transaction'])
  S_query=STATE('query',enter=actions['init_query'])
  S_transaction_end=STATE('transaction_end')
  S_query_descriptors=STATE('query_descriptors')
  S_query_fields=STATE('query_fields')
  S_close=STATE('close',enter=actions['close'])
  S_init.set_events([EVENT('packet',[], S_greeting),EVENT('query',[]),])
  S_greeting.set_events([EVENT('done',[], S_authenticate),EVENT('query',[]),EVENT('close',[], S_close),])
  S_authenticate.set_events([EVENT('sent',[]),EVENT('ok',[actions['parse_auth_response']]),EVENT('done',[], S_autocommit),EVENT('query',[]),EVENT('close',[], S_close),])
  S_autocommit.set_events([EVENT('ok',[], S_isolation),EVENT('close',[], S_close),])
  S_isolation.set_events([EVENT('ok',[], S_connected),EVENT('close',[], S_close),])
  S_connected.set_events([EVENT('query',[actions['query']]),EVENT('transaction',[], S_transaction),EVENT('sent',[], S_query),EVENT('close',[], S_close),])
  S_transaction.set_events([EVENT('ok',[actions['query']]),EVENT('sent',[], S_query),EVENT('close',[], S_close),])
  S_query.set_events([EVENT('packet',[actions['check_query_response']]),EVENT('ok',[actions['transaction_end']], S_transaction_end),EVENT('done',[], S_query_descriptors),EVENT('close',[], S_close),])
  S_transaction_end.set_events([EVENT('ok',[actions['query_complete']], S_connected),])
  S_query_descriptors.set_events([EVENT('packet',[actions['read_descriptor_packet']]),EVENT('eof',[], S_query_fields),EVENT('close',[], S_close),])
  S_query_fields.set_events([EVENT('packet',[actions['read_data_packet']]),EVENT('eof',[actions['transaction_end']]),EVENT('ok',[actions['query_complete']], S_connected),EVENT('query',[]),EVENT('close',[], S_close),])
  S_close.set_events([])
  return FSM([S_init,S_greeting,S_authenticate,S_autocommit,S_isolation,S_connected,S_transaction,S_query,S_transaction_end,S_query_descriptors,S_query_fields,S_close])
