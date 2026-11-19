"""Fake SCPI transport of the DHO824 driver: the instrument settings as plain state.

The state starts from canned values (every number here is test data, marked ``# placeholder``) and nothing else:
this is not a recording of an instrument.  A write changes the answer of its own query, so the resource state shows
what was written, and ``:STOP`` makes the e-stop observable in the trigger status.
It does not model probe-dependent scale/offset changes, state-dependent setting rejection, or acquisition timing.
Those gaps mean a successful fake write is no evidence that a live setting is valid.

Gate G7 (transport mode) checks the command mnemonics the driver sends against the upstream clone, not this class.
Nothing here talks to an instrument.
"""

#: Canned identity in the shape the clone documents ('RIGOL TECHNOLOGIES,<model>,<serial>,<version>').
_IDENTITY = "RIGOL TECHNOLOGIES,DHO824,DHO8A000000000,00.01.04"  # placeholder
#: An empty error queue answers the number zero and "No error".
_NO_ERROR = '0,"No error"'  # placeholder
#: Canned starting settings; the manual's defaults are noted, the values remain test data.
_CHANNEL1_DISPLAY = True       # placeholder (manual default: ON)
_CHANNEL1_COUPLING = "DC"      # placeholder (manual default: DC)
_CHANNEL1_SCALE = 0.05         # placeholder (manual default: 50 mV/div)
_CHANNEL1_OFFSET = 0.0         # placeholder
_CHANNEL1_PROBE = 1.0          # placeholder (manual default: 1X)
_CHANNEL1_INVERT = False       # placeholder (manual default: OFF)
_CHANNEL1_BANDWIDTH_LIMIT = "OFF"  # placeholder (manual default: OFF)
_TIMEBASE_SCALE = 5e-9         # placeholder (manual default: 5 ns/div)
_TIMEBASE_OFFSET = 0.0         # placeholder
_ACQUISITION_STATUS = "STOP"   # placeholder: the scope starts stopped
_DVM_ENABLED = False           # placeholder (manual default: OFF)
_DVM_VOLTAGE = 0.0             # placeholder
_DVM_MODE = "ACRM"             # placeholder (manual default: ACRMs)


class FakeRigolDho824:
    """A stand-in SCPI instrument: ``write``/``read``/``query`` of text lines, as the bridge's transport."""

    def __init__(self, **_options):
        self.written = []
        self.errors = []
        self._pending = []
        self.channel1_display = _CHANNEL1_DISPLAY
        self.channel1_coupling = _CHANNEL1_COUPLING
        self.channel1_scale = _CHANNEL1_SCALE
        self.channel1_offset = _CHANNEL1_OFFSET
        self.channel1_probe = _CHANNEL1_PROBE
        self.channel1_invert = _CHANNEL1_INVERT
        self.channel1_bandwidth_limit = _CHANNEL1_BANDWIDTH_LIMIT
        self.timebase_scale = _TIMEBASE_SCALE
        self.timebase_offset = _TIMEBASE_OFFSET
        self.acquisition_status = _ACQUISITION_STATUS
        self.dvm_enabled = _DVM_ENABLED
        self.dvm_voltage = _DVM_VOLTAGE
        self.dvm_mode = _DVM_MODE

    def _answers(self, line):
        return {
            "*IDN?": lambda: _IDENTITY,
            ":CHAN1:DISP?": lambda: "1" if self.channel1_display else "0",
            ":CHAN1:COUP?": lambda: self.channel1_coupling,
            ":CHAN1:SCAL?": lambda: f"{self.channel1_scale:.6E}",
            ":CHAN1:OFFS?": lambda: f"{self.channel1_offset:.6E}",
            ":CHAN1:PROB?": lambda: f"{self.channel1_probe:g}",
            ":CHAN1:INV?": lambda: "1" if self.channel1_invert else "0",
            ":CHAN1:BWL?": lambda: self.channel1_bandwidth_limit,
            ":TIM:MAIN:SCAL?": lambda: f"{self.timebase_scale:.6E}",
            ":TIM:MAIN:OFFS?": lambda: f"{self.timebase_offset:.6E}",
            ":TRIG:STAT?": lambda: self.acquisition_status,
            ":DVM:ENABle?": lambda: "1" if self.dvm_enabled else "0",
            ":DVM:CURRent?": lambda: f"{self.dvm_voltage:.6E}",
            ":DVM:MODE?": lambda: self.dvm_mode,
            ":SYSTem:ERRor?": lambda: self.errors.pop(0) if self.errors else _NO_ERROR,
        }.get(line)

    def write(self, line, *, timeout_s=None):
        self.written.append(line)
        if line.endswith("?"):
            answer = self._answers(line)
            if answer is None:
                # Like an instrument that does not know the query: the read times out.
                raise TimeoutError(f"the stand-in instrument does not answer {line!r}")
            self._pending.append(answer())
            return
        self._apply(line)

    def read(self, *, timeout_s=None):
        if not self._pending:
            raise TimeoutError("no response is pending")
        return self._pending.pop(0)

    def query(self, line, *, timeout_s=None):
        self.write(line, timeout_s=timeout_s)
        return self.read(timeout_s=timeout_s)

    def close(self):
        pass

    @staticmethod
    def _on(argument):
        return argument.strip().upper() in ("1", "ON", "TRUE")

    def _apply(self, line):
        command, _, argument = line.partition(" ")
        argument = argument.strip()
        if command == ":CHAN1:DISP":
            self.channel1_display = self._on(argument)
        elif command == ":CHAN1:COUP":
            self.channel1_coupling = argument
        elif command == ":CHAN1:SCAL":
            self.channel1_scale = float(argument)
        elif command == ":CHAN1:PROB":
            self.channel1_probe = float(argument)
        elif command == ":CHAN1:INV":
            self.channel1_invert = self._on(argument)
        elif command == ":CHAN1:BWL":
            self.channel1_bandwidth_limit = argument
        elif command == ":TIM:MAIN:SCAL":
            self.timebase_scale = float(argument)
        elif command == ":DVM:ENABle":
            self.dvm_enabled = self._on(argument)
        elif command == ":DVM:MODE":
            self.dvm_mode = argument
        elif command == ":RUN":
            self.acquisition_status = "RUN"
        elif command == ":STOP":
            self.acquisition_status = "STOP"
        elif command == ":SING":
            self.acquisition_status = "WAIT"
