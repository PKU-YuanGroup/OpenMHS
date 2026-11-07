"""Fake backend of the Tecan Genesis driver.

The fake has the two public methods of the upstream class ``tecan_funcs.Cmd_delayed`` and the two instance lists its
``__init__`` creates (``cmdStack`` and ``runningStack``); gate G7 checks that surface against the clone.  It does not
speak the serial frame: it records what the driver queued and what a start dispatched.  All counters start at 0;
those values are test data (``# placeholder``), not device facts.  Nothing here talks to an instrument.
"""


class FakeCmdDelayed:
    # placeholder: a queued-command counter that mirrors Cmd_delayed.cmdCount; not a device fact.
    cmdCount = 0

    def __init__(self, **_options):
        # placeholder: both stacks start empty, as Cmd_delayed.__init__ does; not a device fact.
        self.cmdStack = []
        self.runningStack = []

    def add_cmd(self, cmd="RFV", dev="M1"):
        self.cmdStack.append((cmd, dev))
        type(self).cmdCount += 1

    def start(self, cmd="RFV", dev="M1"):
        # Cmd_delayed.start appends each queued device to runningStack and does not clear cmdStack
        # (tecan_funcs.py:63-70); the driver resets the stacks before it queues the next command.
        for (_command, device) in self.cmdStack:
            self.runningStack.append(device)
