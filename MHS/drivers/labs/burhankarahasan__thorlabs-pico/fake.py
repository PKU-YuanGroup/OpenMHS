"""Fake backend of the thorlabs-pico driver: an in-memory stand-in for stepper_controller:PicoStepperController.

Gate G7: every public method defined here exists on PicoStepperController in stepper_controller.py.  The fake
implements the methods this driver calls -- get_status, set_speed_rps, set_ramp_rate, enable_motor, disable_motor,
stop and close -- and keeps the same return types as the upstream class: get_status returns a
(current_rps, target_rps, position) tuple (stepper_controller.py:139-154) and the command methods return a bool
(stepper_controller.py:70-137).  DISABLE zeros the speeds, as the example firmware does
(accel_stepper_serial.ino:90-95).  The values never move by themselves, so reading the state twice gives the same
state.  Nothing here talks to a device.
"""


class FakePicoStepperController:
    def __init__(self, **_options):
        # placeholder: every starting value is test data for the fake, not a fact about a device
        self._current_rps = 0.0
        self._target_rps = 0.0
        self._position_steps = 0
        self._ramp_rate = 10.0
        self._enabled = False
        self._closed = False

    def get_status(self):
        # placeholder: a canned STATUS reply built from the fake's test state
        return (self._current_rps, self._target_rps, self._position_steps)

    def set_speed_rps(self, rps):
        self._target_rps = float(rps)
        return True

    def set_ramp_rate(self, rate):
        self._ramp_rate = float(rate)
        return True

    def enable_motor(self):
        self._enabled = True
        return True

    def disable_motor(self):
        # the example firmware zeros the target and current speed on DISABLE (accel_stepper_serial.ino:90-95)
        self._enabled = False
        self._target_rps = 0.0
        self._current_rps = 0.0
        return True

    def stop(self):
        self._target_rps = 0.0
        self._current_rps = 0.0
        return True

    def close(self):
        self._closed = True
