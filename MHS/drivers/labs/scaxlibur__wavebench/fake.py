"""Fake backend of the DG4202 driver: an in-memory stand-in for wavebench.drivers.dg4202:DG4202Source.

Gate G7: every public method defined here is a method of ``DG4202Source`` in the clone
(src/wavebench/drivers/dg4202.py:148-891), and the driver touches nothing else.  Each channel keeps the state that
``get_status`` returns, and every setter updates it, so a write is visible to the next read.  The class validates
its input the way the upstream methods do (a positive frequency and amplitude, a duty cycle strictly between 0 and
100 percent, a known function, a channel 1 or 2; dg4202.py:52-54, 538-539, 638, 669-670, 709-711).

The values below are test data, not facts: they are marked ``# placeholder`` and are not a recording of an
instrument — the clone has no simulator for this driver.  Nothing here talks to a device.
"""

from dataclasses import dataclass

FUNCTIONS = ("SIN", "SQU", "RAMP", "PULS", "NOIS", "DC")


@dataclass(frozen=True)
class _Status:
    """Stand-in for ``wavebench.instruments.models:SourceStatus`` with the same fields (dg4202.py:509-524)."""

    channel: int
    output: str
    function: str
    frequency_hz: float
    amplitude: float
    amplitude_unit: str
    offset_v: float
    phase_deg: float
    frequency_mode: str
    sweep_enabled: str
    apply_raw: str
    square_duty_cycle_percent: float


class FakeDG4202Source:
    def __init__(self, **_options):
        self._state = {
            1: {"output": "OFF", "function": "SIN",          # placeholder
                "frequency_hz": 1000.0, "amplitude": 1.0,    # placeholder
                "amplitude_unit": "VPP", "offset_v": 0.0,    # placeholder
                "phase_deg": 0.0, "frequency_mode": "FIX",   # placeholder
                "sweep_enabled": "OFF",                      # placeholder
                "apply_raw": "SIN,1.0,1.0,0.0,0.0",          # placeholder
                "square_duty_cycle_percent": 50.0},          # placeholder
            2: {"output": "OFF", "function": "SIN",          # placeholder
                "frequency_hz": 1000.0, "amplitude": 1.0,    # placeholder
                "amplitude_unit": "VPP", "offset_v": 0.0,    # placeholder
                "phase_deg": 0.0, "frequency_mode": "FIX",   # placeholder
                "sweep_enabled": "OFF",                      # placeholder
                "apply_raw": "SIN,1.0,1.0,0.0,0.0",          # placeholder
                "square_duty_cycle_percent": 50.0},          # placeholder
        }
        self.closed = False

    def _channel(self, channel):
        if channel not in self._state:
            raise ValueError("DG4000 channel must be 1 or 2")
        return self._state[channel]

    def idn(self):
        return "RIGOL TECHNOLOGIES,DG4202,FAKE000000,00.01.00"    # placeholder

    def get_status(self, channel):
        state = self._channel(channel)
        return _Status(channel=channel, **state)

    def set_frequency(self, channel, value_hz, *, ensure_fix_mode=True, check_errors=None):
        state = self._channel(channel)
        if float(value_hz) <= 0:
            raise ValueError("frequency must be > 0")
        state["frequency_hz"] = float(value_hz)
        state["frequency_mode"] = "FIX"
        return self.get_status(channel)

    def set_output(self, channel, enabled, *, check_errors=None):
        state = self._channel(channel)
        if not isinstance(enabled, bool):
            raise ValueError("output enabled must be a boolean")
        state["output"] = "ON" if enabled else "OFF"
        return self.get_status(channel)

    def set_function(self, channel, function, *, check_errors=None):
        state = self._channel(channel)
        normalized = str(function).strip().upper()
        if normalized not in FUNCTIONS:
            raise ValueError("function must be one of: sin, squ, ramp/triangle, puls, nois, dc")
        state["function"] = normalized
        return self.get_status(channel)

    def set_amplitude_vpp(self, channel, value_vpp, *, check_errors=None):
        state = self._channel(channel)
        if float(value_vpp) <= 0:
            raise ValueError("amplitude must be > 0")
        state["amplitude_unit"] = "VPP"
        state["amplitude"] = float(value_vpp)
        return self.get_status(channel)

    def set_square_duty_cycle(self, channel, duty_percent, *, check_errors=None):
        state = self._channel(channel)
        value = float(duty_percent)
        if value <= 0 or value >= 100:
            raise ValueError("duty cycle percent must be > 0 and < 100")
        state["square_duty_cycle_percent"] = value
        return self.get_status(channel)

    def close(self):
        self.closed = True
