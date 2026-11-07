"""Hardware backend: opens the Opentrons Temp Deck Gen 3 over its USB serial port with pyserial.

The upstream clone is firmware plus host-side test scripts; it is not an installable Python package and
this module does not import it.  The transport below is the same one the upstream ``Tempdeck`` class
uses (``stm32-modules/tempdeck-gen3/scripts/test_utils.py:194-225``): 115200 baud, one newline-terminated
command line written, one reply line read, an ``ERR`` reply or a reply missing its guard prefix raised as
``RuntimeError``.  The commands are the ones the firmware documents:
``M105.D``, ``M103.D``, ``M104 S<temp>``, ``M106 S<power>`` and ``M18``.

Used only with ``backend="hardware"`` after a human sets ``reviewed_by`` in driver.lock.json: this is an
R2 model-authored driver, so the loader refuses the hardware backend until then.  The acceptance gate
runs the fake backend and never imports this module.
"""

import re

_TEMP_RE = re.compile(
    r"^M105\.D PT1:(?P<plate1>.+) PT2:(?P<plate2>.+) HST:(?P<heatsink>.+) "
    r"PA1:(.+) PA2:(.+) HSA:(.+) OK\n$"
)
_POWER_RE = re.compile(r"^M103\.D I:(?P<current>.+) R:(?P<rpm>.+) P:(?P<p_pwm>.+) F:(?P<f_pwm>.+) OK\n$")


class SerialTempdeck:
    """The two serial exchanges the driver reads and the three commands it writes."""

    def __init__(self, port: str, timeout_s: float = 2.0):
        import serial  # imported lazily: the gate and the fake backend never need pyserial

        self._ser = serial.Serial(port, 115200, timeout=timeout_s)

    def _send_and_recv(self, msg: str, guard_ret: str) -> str:
        self._ser.write(msg.encode())
        ret = self._ser.readline().decode()
        if not ret.startswith(guard_ret):
            raise RuntimeError(f"incorrect response to {msg.strip()!r}: {ret!r}")
        if ret.startswith("ERR"):
            raise RuntimeError(ret)
        return ret

    def get_temperatures(self):
        res = self._send_and_recv("M105.D\n", "M105.D PT1:")
        match = _TEMP_RE.match(res)
        if match is None:
            raise RuntimeError(f"unparsable M105.D reply: {res!r}")
        return float(match.group("plate1")), float(match.group("plate2")), float(match.group("heatsink"))

    def get_thermal_power(self):
        res = self._send_and_recv("M103.D\n", "M103.D I:")
        match = _POWER_RE.match(res)
        if match is None:
            raise RuntimeError(f"unparsable M103.D reply: {res!r}")
        return (float(match.group("current")), float(match.group("rpm")),
                float(match.group("p_pwm")), float(match.group("f_pwm")))

    def set_fan_power(self, power: float = 0):
        self._send_and_recv(f"M106 S{power}\n", "M106 OK")

    def set_temperature(self, temp: float):
        self._send_and_recv(f"M104 S{temp}\n", "M104 OK")

    def deactivate(self):
        self._send_and_recv("M18\n", "M18 OK")


def _find_port():
    from serial.tools import list_ports

    avail = list(list_ports.grep(".*empdeck*"))
    if not avail:
        raise RuntimeError("could not find a Temp Deck on a USB serial port; pass port=")
    return avail[0].device


def connect(port: str | None = None, **options):
    """Open the module; ``port`` is the serial device (found by USB details when omitted)."""
    return SerialTempdeck(port or _find_port(), **options)
