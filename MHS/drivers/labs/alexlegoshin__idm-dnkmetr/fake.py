"""Fake backend for the GPP-4323 driver: the upstream PowerSupply object without a VISA connection.

The fake keeps the state in plain attributes and answers only the methods of the upstream class
``drivers:PowerSupply`` (and its base ``ScpiInstrument``): ``set_voltage``, ``set_current_limit``,
``enable_output``, ``measure_voltage``, ``measure_current``, ``query_number``, ``idn`` and ``close``.
The readback names accepted by ``query_number`` are the two commands the hardware factory adds to the profile
(``VSET1?`` and ``ISET1?``).

Every number and string here is test data, marked ``# placeholder``; none is copied into a Fact, a Limit or the
reference.  Nothing here talks to an instrument.
"""


class FakeGpp4323:
    def __init__(self, **_options):
        self.voltage = 5.0              # placeholder: voltage setpoint in V
        self.current_limit = 0.5        # placeholder: current limit in A
        self.output_on = False
        self.load_ohms = 800.0          # placeholder: resistive load of the simulation
        self.written = []

    # -- writes of the upstream class -------------------------------------------------------------------------
    def set_voltage(self, volts):
        self.voltage = float(volts)
        self.written.append(("set_voltage", self.voltage))

    def set_current_limit(self, amps):
        self.current_limit = float(amps)
        self.written.append(("set_current_limit", self.current_limit))

    def enable_output(self, state=True):
        self.output_on = bool(state)
        self.written.append(("enable_output", self.output_on))

    # -- readings of the upstream class -----------------------------------------------------------------------
    def measure_voltage(self):
        return self.voltage if self.output_on else 0.0

    def measure_current(self):
        return self.voltage / self.load_ohms if self.output_on else 0.0

    def query_number(self, name, **kwargs):
        if name == "set_voltage_readback":
            return self.voltage
        if name == "current_limit_readback":
            return self.current_limit
        raise ValueError(f"the fake profile has no query named {name!r}")

    def idn(self):
        return "GW INSTEK,GPP-74323,SN:PLACEHOLDER,V1.22"  # placeholder

    def close(self):
        pass
