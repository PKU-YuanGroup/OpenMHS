"""Fake backend of the HelixCycler driver: an in-memory stand-in for tc_send_code:HardwareController.

Gate G7: every public method here exists on ``tc_send_code.HardwareController`` at the pinned commit, and every
state attribute is private (the upstream object keeps only ``port`` as public state).  The fake sends nothing: it
records the target of each set command.  To give the write probes an observable state, a temperature set command
also makes the corresponding reported temperature equal the target at once; that is a fake simplification, not a
claim that a real block reaches its setpoint instantly.  Every number below is test data, not a device fact.
"""


class FakeHardwareController:
    def __init__(self, **_options):
        self.port = None
        self._lid_celsius = 25.0                 # placeholder: a steady room-temperature reading
        self._plate_celsius = 24.5               # placeholder: a steady room-temperature reading
        self._plate_remaining = "0"              # placeholder: no hold running
        self._lid_setpoint = 37.0                # placeholder: last lid target written
        self._plate_setpoint = 25.0              # placeholder: last plate target written
        self._shake_speed = 0.0                  # placeholder: shaker idle
        self._lid_open = False                   # placeholder: lid starts closed
        self._deactivated = False                # placeholder: no deactivate-all seen yet

    # -- connection --------------------------------------------------------------------------------------------
    def connect(self, port_name):
        self.port = port_name
        return True

    def disconnect(self):
        self.port = None

    # -- temperature reads -------------------------------------------------------------------------------------
    def get_lid_temperature(self):
        return self._lid_celsius

    def get_plate_info(self):
        return [self._plate_celsius, self._plate_remaining]

    # -- actuation ---------------------------------------------------------------------------------------------
    def set_lid_temperature(self, temp):
        self._lid_setpoint = float(temp)
        self._lid_celsius = float(temp)           # placeholder: the fake reports the target at once
        self._deactivated = False

    def set_plate_temperature(self, target, time_val=None, well_vol=None):
        self._plate_setpoint = float(target)
        self._plate_celsius = float(target)       # placeholder: the fake reports the target at once
        self._plate_remaining = str(time_val) if time_val is not None else "0"   # placeholder: no hold
        self._deactivated = False

    def set_shake_speed(self, target):
        self._shake_speed = float(target)
        self._deactivated = False

    def open_lid(self):
        self._lid_open = True

    def close_lid(self):
        self._lid_open = False

    def deactivate_shaker(self):
        self._shake_speed = 0.0                   # placeholder: shaker stopped
        self._deactivated = True

    def deactivate_all(self):
        self._deactivated = True
        self._shake_speed = 0.0                   # placeholder: shaker stopped
        self._plate_remaining = "0"               # placeholder: no hold running
