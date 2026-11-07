"""Fake SMC100 controller for the acceptance gate.

It implements only methods that the upstream ``smc100:SMC100`` class has (gate G7): ``get_position_mm``,
``get_status``, ``home``, ``move_absolute_mm``, ``move_relative_mm``, ``stop`` and ``close``.  The state lives in
plain attributes.  Every number below is test data, not a device fact:

* the start position 5.0 mm and the start state "33" are placeholders;
* the error code 0 is a placeholder;
* the state codes written by the moves are the upstream constants' values, used as placeholders.

No hardware is attached and no command is sent to a device.
"""


class FakeSMC100:
    def __init__(self, **_options):
        self.position_mm = 5.0  # placeholder: start position
        self.state = "33"  # placeholder: READY from MOVING
        self.error_code = 0  # placeholder: no error
        self.stopped = False
        self.stop_calls = 0
        self.closed = False

    def get_position_mm(self):
        return self.position_mm

    def get_status(self, silent=False):
        return self.error_code, self.state

    def home(self, waitStop=True):
        self.position_mm = 0.0  # placeholder: the origin
        self.state = "32"  # placeholder: READY from HOMING
        return None

    def move_absolute_mm(self, position_mm, waitStop=True):
        self.position_mm = float(position_mm)
        self.state = "33"  # placeholder: READY from MOVING
        return None

    def move_relative_mm(self, dist_mm, waitStop=True):
        self.position_mm += float(dist_mm)
        self.state = "33"  # placeholder: READY from MOVING
        return None

    def stop(self):
        self.stopped = True
        self.stop_calls += 1
        self.state = "3C"  # placeholder: DISABLE from READY
        return None

    def close(self):
        self.closed = True
