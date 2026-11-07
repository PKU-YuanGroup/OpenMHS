"""Fake backend of the ScopeMCP driver: an in-memory stand-in for ds1102_mcp:ScopeController.

Gate G7: every public method defined here (``get_device``, ``send_cmd``, ``read_resp`` and ``get_metadata_cached``)
is a method of ``ScopeController`` in the clone, and the driver touches no other native attribute.  The upstream class
is a pyusb transport, so this fake replaces the USB device with private state: ``send_cmd`` parses the same command
strings the upstream MCP tools send, and ``get_metadata_cached`` returns the JSON metadata dict the upstream class
would parse from the ``:DATA:WAVE:SCREEN:HEAD?`` reply.  The clone has no simulator for this class, so this is an
in-memory stand-in, not a recording of a session.  Every starting value and canned reply below is placeholder test
data, never a Fact, a Limit or a reference; nothing here talks to a device.
"""

import json


class FakeScopemcp:
    """A fresh in-memory DS1102 per endpoint; all starting values are placeholders."""

    def __init__(self, **_options):
        self._model = "DS1102"                                # placeholder
        self._run_status = "TRIG"                              # placeholder (README.md:95)
        self._channels = [
            {"NAME": "CH1", "FREQUENCE": 1000.0, "SCALE": "1.00V",   # placeholder
             "COUPLING": "DC", "DISPLAY": "ON", "OFFSET": 0},        # placeholder
            {"NAME": "CH2", "FREQUENCE": 500.0, "SCALE": "500mV",    # placeholder
             "COUPLING": "DC", "DISPLAY": "ON", "OFFSET": 0},        # placeholder
        ]
        self._timebase = {"SCALE": "1ms", "OFFSET": 0.0}       # placeholder
        self._trigger = {"SWEEP": "AUTO", "SLOPE": "RISE",     # placeholder
                         "SOURCE": "CH1", "LEVEL": "0.0mV"}    # placeholder
        self._last_command = ""                                # placeholder

    # -- the upstream transport surface ---------------------------------------------------------------
    def get_device(self):
        """The upstream returns the USB device; the fake is its own device object."""
        return self

    def send_cmd(self, dev, cmd, clear_buffer=True):
        """Parse one command string exactly as the upstream MCP tools write it."""
        text = str(cmd).strip()
        upper = text.upper()
        if upper.startswith(":AUTOSET"):
            self._channels[0]["SCALE"] = "2.00V"               # placeholder
            self._channels[0]["COUPLING"] = "DC"               # placeholder
        elif upper.startswith(":CH1:SCALE "):
            self._channels[0]["SCALE"] = text.split(" ", 1)[1]
        elif upper.startswith(":CH2:SCALE "):
            self._channels[1]["SCALE"] = text.split(" ", 1)[1]
        elif upper.startswith(":CH1:COUPLING "):
            self._channels[0]["COUPLING"] = text.split(" ", 1)[1].upper()
        elif upper.startswith(":CH2:COUPLING "):
            self._channels[1]["COUPLING"] = text.split(" ", 1)[1].upper()
        elif upper.startswith(":CH1:OFFSET "):
            self._last_command = text
        elif upper.startswith(":HORIZONTAL:SCALE "):
            self._timebase["SCALE"] = text.split(" ", 1)[1]
        elif upper.startswith(":TRIGGER:EDGE:LEVEL "):
            self._trigger["LEVEL"] = text.split(" ", 1)[1]
        elif upper.startswith(":TRIGGER:EDGE:SLOPE "):
            self._trigger["SLOPE"] = text.split(" ", 1)[1].upper()
        elif upper.startswith(":TRIGGER:EDGE:SOURCE "):
            self._trigger["SOURCE"] = text.split(" ", 1)[1].upper()
        elif upper.startswith(":TRIGGER:SWEEP "):
            self._trigger["SWEEP"] = text.split(" ", 1)[1].upper()
        elif upper in (":RUN", ":STOP"):
            self._run_status = "TRIG"                          # placeholder (the firmware always reports TRIG)
        self._last_command = text

    def read_resp(self, dev, size=32768, timeout=800):
        """The metadata reply the upstream HEAD query would parse: a 4-byte length plus JSON."""
        payload = json.dumps(self._metadata(), separators=(",", ":")).encode("ascii")
        return len(payload).to_bytes(4, "little") + payload

    def get_metadata_cached(self, dev, max_age=2.0):
        """The metadata dict the upstream class parses from the HEAD reply (max_age is ignored)."""
        return self._metadata()

    # -- private test data ----------------------------------------------------------------------------
    def _metadata(self):
        return {
            "MODEL": self._model,                              # placeholder
            "RUNSTATUS": self._run_status,                     # placeholder
            "TIMEBASE": dict(self._timebase),                  # placeholder
            "CHANNEL": [dict(item) for item in self._channels],  # placeholder
        }
