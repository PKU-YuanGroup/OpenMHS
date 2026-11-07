"""Fake backend of the SMC100 driver: an in-memory stand-in for smc100_base:smc100.

Gate G7: every public method defined here exists on the upstream smc100 class (smc100_base.py:73-243).  The fake is a
single-axis controller: the driver sends controller address 1 for every command, as the README says the motor number
is usually 1 (README.md:27).  The fake keeps only private state, answers the TP and VA? queries that the driver sends
through send_rcv, and applies the PA, PR, OR, ST and RS commands immediately; the real controller completes motion
asynchronously.  Every start value and canned reply below is test data marked ``# placeholder``, not a fact about a
device.  Nothing here opens a port or talks to hardware.
"""


class FakeSmc100:
    def __init__(self, **_options):
        self._position = 0.0                 # placeholder
        self._state = "READY from HOMING"    # placeholder
        self._velocity = 1.0                 # placeholder
        self._errors = [None]                # placeholder
        self._closed = False

    def send_rcv(self, command):
        if command.endswith("TP"):
            return f"{self._position:.9f}"
        if command.endswith("VA?"):
            return f"{self._velocity:.9f}"
        return ""                            # placeholder: the fake answers only the queries above

    def get_state(self, controller):
        return self._state

    def get_errors(self, controller):
        return list(self._errors)

    def set_velocity(self, controller, velocity):
        self._velocity = float(velocity)

    def move_absolute(self, controller, position):
        self._position = float(position)
        self._state = "READY from MOVING"    # placeholder: the real controller passes through MOVING

    def move_relative(self, controller, position):
        self._position += float(position)
        self._state = "READY from MOVING"    # placeholder: the real controller passes through MOVING

    def home(self, controller):
        self._position = 0.0                 # placeholder: homing is asynchronous on the real controller
        self._state = "READY from HOMING"    # placeholder

    def stop_motion(self, controller):
        self._state = "READY from MOVING"    # placeholder: motion stopped

    def reset(self, controller):
        self._position = 0.0                 # placeholder
        self._state = "NOT REFERENCED from reset"   # placeholder

    def kill(self):
        self._closed = True
