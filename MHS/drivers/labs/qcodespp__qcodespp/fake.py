"""Fake backend of the Keithley 2450 driver: a source-shaped stand-in for the QCoDeS instrument.

The upstream ``Keithley_2450`` class builds its QCoDeS Parameters with ``add_parameter`` from literal SCPI
commands (Keithley_2450.py:13-120) and its measurement paths are the private methods and parsers of the same class
(Keithley_2450.py:125-183, 208-216, 231-242).  This fake implements only those methods the driver calls:
``_get_volt``, ``_set_volt``, ``_get_current``, ``_set_current``, ``_get_resistance``, ``_set_mode_and_sense``,
``_volt_parser``, ``_curr_parser``, ``_resistance_parser``, plus the inherited VISA ``write``, ``ask`` and ``close``.
It sends and understands the same command strings as the upstream Parameters; nothing here imports QCoDeS or PyVISA.

The initial state is a valid measurement configuration (source current, sense voltage, output on); every value is a
placeholder chosen so that the three parser methods agree with one another.  They are test data, not facts about a
Keithley 2450, and they are marked ``# placeholder`` below.  The fake does not model instrument timing, auto-range,
the SCPI error queue, or the QCoDeS validators and value wrappers, so a first supervised run must check those.

Fidelity gap: one set of values is served for every range; the fake applies no range, compliance or mode rounding and
does not model the output relay.  The upstream ``_get_*`` methods raise when the output is off and when source/sense
are not configured for the requested measurement, and the fake reproduces those preconditions.
"""


class FakeKeithley2450:
    def __init__(self, **_options):
        self._written = []
        self._closed = False
        self._output = True                    # placeholder
        self._source = "CURR"                  # placeholder
        self._sense = '"VOLT"'                 # placeholder, quoted as :SENS:FUNC? reports it
        self._voltage = 1.0                    # placeholder, V
        self._current = 0.001                  # placeholder, A
        self._compliancev = 10.0               # placeholder, V
        self._compliancei = 0.1                # placeholder, A

    # -- the upstream measurement and setter methods -------------------------
    def _get_volt(self):
        if not self._output:
            raise RuntimeError("placeholder: output not turned on")
        if self._sense.startswith('"VOLT'):
            return self.ask("READ?")
        if self._source == "VOLT":
            return self.ask("SOUR:VOLT?")
        raise RuntimeError("placeholder: not set to source or sense voltage")

    def _set_volt(self, value):
        if not self._output:
            raise RuntimeError("placeholder: output not turned on")
        if self._source != "VOLT":
            raise RuntimeError("placeholder: not set to source voltage")
        self.write(f":SOUR:VOLT:LEV {float(value):.8f}")

    def _get_current(self):
        if not self._output:
            raise RuntimeError("placeholder: output not turned on")
        if self._sense.startswith('"CURR'):
            return self.ask("READ?")
        if self._source == "CURR":
            return self.ask("SOUR:CURR?")
        raise RuntimeError("placeholder: not set to either source or sense current")

    def _set_current(self, value):
        if not self._output:
            raise RuntimeError("placeholder: output not turned on")
        if self._source != "CURR":
            raise RuntimeError("placeholder: not set to source current")
        self.write(f":SOUR:CURR:LEV {float(value):.16f}")

    def _get_resistance(self):
        if not self._output:
            raise RuntimeError("placeholder: output not turned on")
        if self._sense.startswith('"CURR') and self._source == "VOLT":
            return self.ask("READ?")
        if self._source == "CURR" and self._sense.startswith('"VOLT'):
            return self.ask("READ?")
        raise RuntimeError("placeholder: not set to measure resistance")

    def _set_mode_and_sense(self, msg):
        if msg == "VOLT":
            self.write(':SENS:FUNC "CURR"')
        elif msg == "CURR":
            self.write(':SENS:FUNC "VOLT"')
        else:
            raise AttributeError("placeholder: mode does not exist")
        self.write(f":SOUR:FUNC {msg}")

    def _volt_parser(self, msg):
        return [float(x) for x in msg.split(",")][0]

    def _curr_parser(self, msg):
        return [float(x) for x in msg.split(",")][1]

    def _resistance_parser(self, msg):
        fields = [float(x) for x in msg.split(",")]
        return fields[0] / fields[1]

    # -- the VISA methods the upstream class inherits -------------------------
    def write(self, cmd):
        """QCoDeS VisaInstrument.write: send one command line, no reply."""
        self._written.append(cmd)
        head, _, argument = cmd.partition(" ")
        if head == ":OUTP:STAT":
            self._output = bool(int(argument))
        elif head == ":SOUR:FUNC":
            self._source = argument
        elif head == ":SENS:FUNC":
            self._sense = argument
        elif head == ":SOUR:VOLT:LEV":
            self._voltage = float(argument)             # placeholder update
        elif head == ":SOUR:CURR:LEV":
            self._current = float(argument)             # placeholder update
        elif head == "SOUR:CURR:VLIM:LEV":
            self._compliancev = float(argument)         # placeholder update
        elif head == "SOUR:VOLT:ILIM:LEV":
            self._compliancei = float(argument)         # placeholder update
        elif cmd == ":*RST":
            self._output = False                        # placeholder reset behaviour
        else:
            raise RuntimeError(f"placeholder: the fake Keithley 2450 does not implement {cmd!r}")

    def ask(self, cmd):
        """QCoDeS VisaInstrument.ask: send one query and return its reply."""
        if cmd == ":OUTP:STAT?":
            return "1" if self._output else "0"
        if cmd == ":SOUR:FUNC?":
            return self._source
        if cmd == ":SENS:FUNC?":
            return self._sense
        if cmd == "SOUR:VOLT?":
            return f"{self._voltage:.8f}"
        if cmd == "SOUR:CURR?":
            return f"{self._current:.16f}"
        if cmd == "SOUR:CURR:VLIM:LEV?":
            return f"{self._compliancev:.16f}"
        if cmd == "SOUR:VOLT:ILIM:LEV?":
            return f"{self._compliancei:.16f}"
        if cmd == "READ?":
            # placeholder: voltage, current, resistance, time and status as a comma-separated reply
            return f"{self._voltage:.8f},{self._current:.16f},{self._voltage / self._current:.8f},0.0,0"
        raise RuntimeError(f"placeholder: the fake Keithley 2450 does not answer {cmd!r}")

    def close(self):
        """QCoDeS VisaInstrument.close: close the VISA session."""
        self._closed = True
