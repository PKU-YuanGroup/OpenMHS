"""Fake SCPI transport of the OIC Arduino DAQ driver.

The transport answers the exact commands the firmware registers (``*IDN?``, ``:MEASURE:VOLTAGE?``,
``:MEASURE:VOLTAGE1?``, ``:MEASURE:VOLTAGE2?``, ``:SOURCE:VOLTAGE`` and ``:SOURCE:VOLTAGE1``) and nothing else: an
unknown query times out, like a firmware that does not implement it.  The start values are placeholders; the fake
models the input/output loopback that the upstream host example assumes when it writes a channel and then reads the
same channel (``src/Examples/Meter/test.py:79-89``).  Nothing here talks to an instrument.

The identity reply is the firmware's own line (``Meter.ino:78``); it is a protocol constant, not a measurement.  All
numbers below are test data and every placeholder is marked as such.
"""


class FakeArduinoDAQ:
    def __init__(self, **_options):
        self._identity = "OIC,Embedded SCPI Example,1,10"
        self._measured = {0: 0.0, 1: 0.0, 2: 0.0}  # placeholder
        self._source = {0: 0.0, 1: 0.0}  # placeholder
        self._pending = []
        self.written = []

    def write(self, line, *, timeout_s=None):
        text = line.strip()
        self.written.append(text)
        if text == "*IDN?":
            self._pending.append(self._identity)
        elif text == ":MEASURE:VOLTAGE?":
            self._pending.append(f"{self._measured[0]:.4f}")  # 4 decimals as Serial.println(voltage,4)
        elif text == ":MEASURE:VOLTAGE1?":
            self._pending.append(f"{self._measured[1]:.4f}")
        elif text == ":MEASURE:VOLTAGE2?":
            self._pending.append(f"{self._measured[2]:.4f}")
        elif text.startswith(":SOURCE:VOLTAGE1 "):
            self._set_source(1, text.split(" ", 1)[1])
        elif text.startswith(":SOURCE:VOLTAGE "):
            self._set_source(0, text.split(" ", 1)[1])
        elif "?" in text:
            self._pending.append(None)  # the firmware has no such query

    def _set_source(self, channel, argument):
        value = argument.strip()
        if value.endswith("V"):
            value = value[:-1]
        volts = float(value)
        self._source[channel] = volts
        self._measured[channel] = volts  # placeholder: the example's write-then-read loopback

    def read(self, *, timeout_s=None):
        if not self._pending:
            raise TimeoutError("no response is pending")
        reply = self._pending.pop(0)
        if reply is None:
            raise TimeoutError("the firmware does not answer this query")
        return reply

    def query(self, line, *, timeout_s=None):
        self.write(line, timeout_s=timeout_s)
        return self.read(timeout_s=timeout_s)

    def close(self):
        pass
