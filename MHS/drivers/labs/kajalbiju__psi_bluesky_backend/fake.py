"""Fake backend of the Mercury iTC driver: an in-memory stand-in for Bluesky4.mercury_itc:MercuryITC.

Gate G7: every public method defined here exists on the upstream class (``query``, ``write``, the six getters and
the four setters this driver uses in ``Bluesky4/mercury_itc.py``).  The fake keeps the same register names and reply
shapes the upstream methods parse: the temperature and TSET replies end in ``K`` and the loop replies end in the
numeric value.  The ``STAT:`` reply prefix and every starting value are test data; each number is marked
``# placeholder`` and none of them is used as a Fact, a Limit or a reference.  Nothing here talks to an instrument.
"""

#: The device address the upstream module fixes (Bluesky4/mercury_itc.py:6); the fake uses the same wire address.
DEVICE_ADDRESS = "STILL_DB6.T1"


class FakeMercuryITC:
    def __init__(self, **_options):
        self._temperature = 295.0            # placeholder
        self._temperature_setpoint = 295.0   # placeholder
        self._heater_setpoint = 0.0          # placeholder
        self._p_value = 10.0                 # placeholder
        self._i_value = 1.0                  # placeholder
        self._d_value = 0.0                  # placeholder

    # -- the two transport methods the upstream setters use ------------------------------------------------
    def write(self, command):
        text = str(command)
        upper = text.upper()
        value = text.rsplit(":", 1)[-1]
        if ":TEMP:LOOP:TSET:" in upper:
            self._temperature_setpoint = float(value)
        elif ":TEMP:LOOP:HSET:" in upper:
            self._heater_setpoint = float(value)
        elif ":TEMP:LOOP:P:" in upper:
            self._p_value = float(value)
        elif ":TEMP:LOOP:I:" in upper:
            self._i_value = float(value)
        elif ":TEMP:LOOP:D:" in upper:
            self._d_value = float(value)
        else:
            raise ValueError(f"fake: unsupported write {text!r}")

    def query(self, command):
        text = str(command)
        upper = text.upper()
        if ":TEMP:SIG:TEMP" in upper:
            return f"STAT:DEV:{DEVICE_ADDRESS}:TEMP:SIG:TEMP:{self._temperature}K"
        if ":TEMP:LOOP:TSET" in upper:
            return f"STAT:DEV:{DEVICE_ADDRESS}:TEMP:LOOP:TSET:{self._temperature_setpoint}K"
        if ":TEMP:LOOP:HSET" in upper:
            return f"STAT:DEV:{DEVICE_ADDRESS}:TEMP:LOOP:HSET:{self._heater_setpoint}"
        if ":TEMP:LOOP:P" in upper:
            return f"STAT:DEV:{DEVICE_ADDRESS}:TEMP:LOOP:P:{self._p_value}"
        if ":TEMP:LOOP:I" in upper:
            return f"STAT:DEV:{DEVICE_ADDRESS}:TEMP:LOOP:I:{self._i_value}"
        if ":TEMP:LOOP:D" in upper:
            return f"STAT:DEV:{DEVICE_ADDRESS}:TEMP:LOOP:D:{self._d_value}"
        raise ValueError(f"fake: unsupported query {text!r}")

    # -- the upstream getters ------------------------------------------------------------------------------
    def read_temperature(self):
        reply = self.query(f"READ:DEV:{DEVICE_ADDRESS}:TEMP:SIG:TEMP")
        return float(reply.split(":")[-1].strip().rstrip("K"))

    def get_gas_flow(self):
        reply = self.query(f"READ:DEV:{DEVICE_ADDRESS}:TEMP:LOOP:TSET")
        return float(reply.split(":")[-1].strip()[:-1])  # the upstream assumes a trailing unit character

    def get_heater_setpoint(self):
        reply = self.query(f"READ:DEV:{DEVICE_ADDRESS}:TEMP:LOOP:HSET")
        return float(reply.split(":")[-1])

    def get_p_value(self):
        reply = self.query(f"READ:DEV:{DEVICE_ADDRESS}:TEMP:LOOP:P")
        return float(reply.split(":")[-1])

    def get_i_value(self):
        reply = self.query(f"READ:DEV:{DEVICE_ADDRESS}:TEMP:LOOP:I")
        return float(reply.split(":")[-1])

    def get_d_value(self):
        reply = self.query(f"READ:DEV:{DEVICE_ADDRESS}:TEMP:LOOP:D")
        return float(reply.split(":")[-1])

    # -- the upstream setters ------------------------------------------------------------------------------
    def set_p_value(self, p_value):
        self.write(f"SET:DEV:{DEVICE_ADDRESS}:TEMP:LOOP:P:{p_value}")
        return self.query(f"READ:DEV:{DEVICE_ADDRESS}:TEMP:LOOP:P")

    def set_i_value(self, i_value):
        self.write(f"SET:DEV:{DEVICE_ADDRESS}:TEMP:LOOP:I:{i_value}")
        return self.query(f"READ:DEV:{DEVICE_ADDRESS}:TEMP:LOOP:I")

    def set_d_value(self, d_value):
        self.write(f"SET:DEV:{DEVICE_ADDRESS}:TEMP:LOOP:D:{d_value}")
        return self.query(f"READ:DEV:{DEVICE_ADDRESS}:TEMP:LOOP:D")

    def set_heater_setpoint(self, h_setpoint):
        self.write(f"SET:DEV:{DEVICE_ADDRESS}:TEMP:LOOP:HSET:{h_setpoint}")
        return self.query(f"READ:DEV:{DEVICE_ADDRESS}:TEMP:LOOP:HSET")
