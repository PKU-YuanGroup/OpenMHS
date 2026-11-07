"""Fake backend of the XIA PFCU driver: an in-memory stand-in for xia_pfcu.pfcu:PFCU.

Gate G7: every public method defined here exists on xia_pfcu.pfcu:PFCU, and the one other attribute the driver
reaches, ``protocol``, is set by the upstream __init__ (xia_pfcu/pfcu.py:23-25).  The methods follow the upstream
signatures: ``set_filters(a=None, b=None, c=None, d=None)`` leaves a filter unchanged with ``None``
(xia_pfcu/pfcu.py:69-95), ``set_decimation(value)`` sends the D command (xia_pfcu/protocol.py:162-163), and
``start_exposure(duration)`` sends the decimation and then the exposure command
(xia_pfcu/protocol.py:229-236).  ``filters_status()`` returns channel state names and ``info()`` returns the fields
``parse_status`` produces (xia_pfcu/protocol.py:108-138); the driver accepts either that dict or the names.

The starting values and the status text are test data, not facts of any device: every state assignment below is
marked ``# placeholder``.  The shutter starts enabled and closed so that the open/close, exposure and safe-state
paths can be exercised.  Nothing here talks to a device.
"""


class _FakeConnection:
    """The connection object a real device owns (``device.protocol.conn``); the driver only closes it."""

    def __init__(self):
        self.is_open = True

    def close(self):
        self.is_open = False


class _FakeProtocol:
    def __init__(self):
        self.conn = _FakeConnection()


class FakePFCU:
    def __init__(self, **_options):
        self.protocol = _FakeProtocol()
        self._module_id = "15"              # placeholder: module address of the stand-in
        self._shutter_mode = True           # placeholder: start with shutter commands enabled
        self._shutter_open = False          # placeholder: start with the shutter closed
        self._decimation = 1                # placeholder: initial decimation
        self._lock = False                  # placeholder: start unlocked
        self._remote_control = True         # placeholder: RS232 control enabled
        self._filters = ["Out", "Out", "Out", "Out"]  # placeholder: all filters removed

    def status(self):
        """The raw status report the S command returns, shaped like xia_pfcu/simulator.py:27-38."""
        mode = "YES Shutter is {}".format(self._shutter_state()) if self._shutter_mode else "NO"
        lines = [
            "%PFCU{} OK PFCU v1.0 (c) XIA 1999 All Rights Reserved".format(self._module_id),
            "CHANNEL IN/OUT (FPanel   TTL  RS232) Shorted? Open?",
        ]
        for index, state in enumerate(self._filters, start=1):
            lines.append("    {}      {}     OUT    OUT   OUT      NO      NO".format(index, state.upper()))
        lines.extend([
            "RS232 Control Enabled: {}".format("YES" if self._remote_control else "NO"),
            "RS232 Control Only: {}".format("YES" if self._lock else "NO"),
            "Shutter Mode Enabled: {}".format(mode),
            "Exposure Decimation: {:5d}".format(self._decimation),
        ])
        return "\n".join(lines)

    def info(self):
        """The fields parse_status builds: identity, channels, control flags, shutter state and decimation."""
        return {
            "id": self.status().split("\n", 1)[0],
            "channels": [
                {
                    "nb": index,
                    "in_out": state.capitalize(),
                    "front_panel": "Out",
                    "ttl": "Out",
                    "rs232": "Out",
                    "shorted": False,
                    "open": False,
                }
                for index, state in enumerate(self._filters, start=1)
            ],
            "remote_control_enabled": self._remote_control,
            "remote_control_only": self._lock,
            "shutter_enabled": self._shutter_mode,
            "shutter_status": self._shutter_state() if self._shutter_mode else "Disabled",
            "decimation": int(self._decimation),
        }

    def filters_status(self):
        """The state of the four filter channels, as FilterStatus names would decode them."""
        return list(self._filters)

    def set_filters(self, a=None, b=None, c=None, d=None):
        """Set the requested filters and return all four states, like xia_pfcu/pfcu.py:69-95."""
        values = {"out": "Out", "o": "Out", "0": "Out", "in": "In", "i": "In", "1": "In", "=": None, "": None}
        for index, value in enumerate((a, b, c, d)):
            if value is None:
                continue
            mapped = values.get(str(value).lower())
            if mapped is not None:
                self._filters[index] = mapped
        return self.filters_status()

    def set_decimation(self, value):
        """Store the decimation, like the D command handler (xia_pfcu/protocol.py:162-163)."""
        self._decimation = int(value)
        return self._decimation

    def enable_shutter(self):
        """Enable the shutter commands (command 2), like xia_pfcu/pfcu.py:30-35."""
        self._shutter_mode = True
        return "Shutter mode Enabled"

    def disable_shutter(self):
        """Disable the shutter commands (command 4), like xia_pfcu/pfcu.py:37-41."""
        self._shutter_mode = False
        return "Shutter mode Disabled"

    def open_shutter(self):
        """Open the shutter (command O) when shutter mode is enabled, like xia_pfcu/pfcu.py:43-48."""
        if not self._shutter_mode:
            raise RuntimeError("Shutter mode disabled")
        self._shutter_open = True
        return "Shutter Open"

    def close_shutter(self):
        """Close the shutter (command C) when shutter mode is enabled, like xia_pfcu/pfcu.py:50-55."""
        if not self._shutter_mode:
            raise RuntimeError("Shutter mode disabled")
        self._shutter_open = False
        return "Shutter Closed"

    def shutter_status(self):
        """The shutter state (command H) when shutter mode is enabled, like xia_pfcu/pfcu.py:57-58."""
        if not self._shutter_mode:
            raise RuntimeError("Shutter mode disabled")
        return self._shutter_state()

    def start_exposure(self, duration):
        """Start an exposure (command E), like xia_pfcu/protocol.py:229-236."""
        if not self._shutter_mode:
            raise RuntimeError("Shutter mode disabled")
        decimation = 1
        deci_millis = float(duration) * 100
        while (2 ** 16 * decimation) < deci_millis:
            decimation *= 10
        self._decimation = decimation
        self._shutter_open = True
        return "Exposure Started"

    def lock(self):
        """Ignore the non-RS232 controls (command L), like xia_pfcu/pfcu.py:114-121."""
        self._lock = True
        return "Locked"

    def unlock(self):
        """Allow every control source again (command U), like xia_pfcu/pfcu.py:123-129."""
        self._lock = False
        return "Unlocked"

    def _shutter_state(self):
        return "Open" if self._shutter_open else "Closed"
