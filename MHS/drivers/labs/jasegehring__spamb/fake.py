"""Fake backend of the SPAMB syringe-pump driver: an in-memory stand-in for hardware.pump:PumpController.

Gate G7: every public method here exists on ``hardware.pump:PumpController`` (fluidics-control/hardware/pump.py),
and the state lives in private attributes.  The methods keep the upstream units: mm, mL/min and mL.  Nothing here
talks to a device, and it does not import the clone or pyserial.

Every number below is placeholder test data, not a fact, a limit or a device setting.
"""


class FakePumpController:
    def __init__(self, **_options):
        self._connected = False
        self._diameter = 26.59       # placeholder: example 60 mL syringe diameter (mm)
        self._rate = 1.0             # placeholder: configured flow rate (mL/min)
        self._target_volume = 5.0    # placeholder: configured target volume (mL)
        self._dispensed = 0.0        # placeholder: volume dispensed since the last start (mL)
        self._direction = "withdraw"  # placeholder: upstream direction word
        self._running = False

    def connect(self):
        self._connected = True

    def disconnect(self):
        self._connected = False

    def set_diameter(self, diameter):
        self._diameter = float(diameter)
        return True

    def set_rate(self, rate):
        self._rate = float(rate)
        return True

    def set_volume(self, volume):
        self._target_volume = abs(float(volume))
        return True

    def set_direction(self, direction):
        if direction not in ("infuse", "withdraw"):
            return False
        self._direction = direction
        return True

    def get_direction(self):
        return self._direction

    def start(self):
        self._running = True
        self._dispensed = 0.0
        return True

    def stop(self):
        self._running = False
        return True

    def is_running(self):
        return self._running

    def get_status(self):
        remaining = max(0.0, self._target_volume - self._dispensed)
        return {
            "pump_number": 1,                 # placeholder
            "is_running": self._running,
            "rate": self._rate,
            "target_volume": self._target_volume,
            "dispensed_volume": self._dispensed,
            "volume_remaining": remaining,
            "elapsed_time": 0.0,              # placeholder
            "diameter": self._diameter,
            "direction": self._direction,
        }
