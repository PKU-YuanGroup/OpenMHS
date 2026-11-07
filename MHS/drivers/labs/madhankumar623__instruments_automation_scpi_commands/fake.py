"""Fake SCPI transport of the DC-supply driver: an in-memory stand-in for DCsupply_1 channels 2 and 3.

The driver sends one semicolon-separated line at a time: ``INST:NSEL 2`` selects a channel, then
``VOLT <value>``, ``CURR <value>`` or ``OUTP ON|OFF`` changes it, and ``VOLT?``, ``CURR?``, ``OUTP?``,
``MEAS:VOLT?`` or ``MEAS:CURR?`` asks for a reply.  This transport applies every part of a line in order and queues
one reply for each query, so any request order works on a fresh transport.  Gate G7 (transport mode) checks the
command mnemonics the driver sends against the clone, not this class.  Nothing here talks to a device.

Every number and canned string below is test data, not a fact from the clone or a record of an instrument; each is
marked ``# placeholder``.
"""


class FakePowerSupply:
    """A fresh in-memory supply per endpoint; all starting values are placeholders."""

    def __init__(self, **_options):
        self.written = []
        self._pending = []
        self._selected = 2                                  # placeholder: channel 2 is the upstream S1 channel
        self._channels = {
            2: {"voltage": 0.0, "current": 0.0, "output": False, "load_ohms": 1000.0},  # placeholder
            3: {"voltage": 0.0, "current": 0.0, "output": False, "load_ohms": 1000.0},  # placeholder
        }
        self.closed = False

    def _channel(self):
        return self._channels[self._selected]

    def _measured_voltage(self):
        channel = self._channel()
        return channel["voltage"] if channel["output"] else 0.0   # placeholder: no output, no voltage

    def _measured_current(self):
        channel = self._channel()
        if not channel["output"]:
            return 0.0                                            # placeholder: no output, no current
        drawn = channel["voltage"] / channel["load_ohms"]         # placeholder: Ohm's law on the modelled load
        if channel["current"] > 0:
            return min(drawn, channel["current"])                 # placeholder: the current limit
        return 0.0                                                # placeholder: a zero limit draws nothing

    def write(self, line, *, timeout_s=None):
        self.written.append(line)
        for part in line.split(";"):
            self._command(part.strip())

    def _command(self, command):
        upper = command.upper()
        if upper.startswith("INST:NSEL "):
            channel = int(command.split(" ", 1)[1])
            if channel not in self._channels:
                raise ValueError(f"the fake has no channel {channel}")
            self._selected = channel
        elif upper.startswith("VOLT "):
            self._channel()["voltage"] = float(command.split(" ", 1)[1])
        elif upper.startswith("CURR "):
            self._channel()["current"] = float(command.split(" ", 1)[1])
        elif upper == "OUTP ON":
            self._channel()["output"] = True
        elif upper == "OUTP OFF":
            self._channel()["output"] = False
        elif upper == "VOLT?":
            self._pending.append(f"{self._channel()['voltage']:.6g}")
        elif upper == "CURR?":
            self._pending.append(f"{self._channel()['current']:.6g}")
        elif upper == "OUTP?":
            self._pending.append("ON" if self._channel()["output"] else "OFF")
        elif upper == "MEAS:VOLT?":
            self._pending.append(f"{self._measured_voltage():.6g}")
        elif upper == "MEAS:CURR?":
            self._pending.append(f"{self._measured_current():.6g}")
        elif upper == "*OPC?":
            self._pending.append("1")                              # placeholder
        elif upper == "*IDN?":
            self._pending.append("FAKE,PROGRAMMABLE_DC_SUPPLY,0,0")  # placeholder identity
        else:
            raise ValueError(f"the fake does not know the command {command!r}")

    def read(self, *, timeout_s=None):
        if not self._pending:
            raise TimeoutError("no response is pending")
        return self._pending.pop(0)

    def query(self, line, *, timeout_s=None):
        self.write(line, timeout_s=timeout_s)
        return self.read(timeout_s=timeout_s)

    def close(self):
        self.closed = True
