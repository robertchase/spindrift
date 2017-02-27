import time

import spindrift.timer as timer


class Action(object):

    def __init__(self):
        self.is_running = True

    def action(self):
        self.is_running = False


t = timer.Timer()
a = Action()
t1 = t.add_hourly(a.action).start()
while a.is_running:
    print('tick', t1)
    time.sleep(10)
    t.service()
