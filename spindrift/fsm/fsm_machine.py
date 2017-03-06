from spindrift.fsm.FSM import STATE, EVENT, FSM
# action
# enter
# event
# exit
# state
def create(**actions):
  S_init=STATE('init')
  S_state=STATE('state',enter=actions['state'])
  S_event=STATE('event',enter=actions['event'])
  S_error=STATE('error')
  S_init.set_events([EVENT('state',[], S_state),])
  S_state.set_events([EVENT('error',[], S_error),EVENT('enter',[actions['enter']]),EVENT('exit',[actions['exit']]),EVENT('event',[], S_event),EVENT('state',[], S_state),])
  S_event.set_events([EVENT('error',[], S_error),EVENT('action',[actions['action']]),EVENT('event',[], S_event),EVENT('state',[], S_state),])
  S_error.set_events([])
  return FSM([S_init,S_state,S_event,S_error])
