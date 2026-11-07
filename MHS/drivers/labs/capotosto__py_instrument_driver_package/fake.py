"""In-memory fake SCPI transport for the Keysight E4980A driver.

The fake is a recording, stateful stand-in for the instrument behind the upstream wrapper: it accepts the exact
command words of ``instrument_module/keysight_E4980A.py`` and keeps the settings the read queries return.  Every
number below is test data, not a device fact: the starting values are marked ``# placeholder`` and must never be
copied into a Fact, a Limit or the reference.  The fetch replies are placeholders too.

The class is a transport (``write``/``read``/``query``/``close``), not the upstream class and not a subclass of it.
Gate G7 for a SCPI family checks the command mnemonics the driver sends against the clone; this file talks to no
instrument.
"""

import threading


class FakeKeysightE4980A:
    def __init__(self, **_options):
        self._lock = threading.Lock()
        self._pending: list[str] = []
        self.written: list[str] = []
        self._reset_state()

    def _reset_state(self) -> None:
        # Every value in this method is placeholder test data.
        self.measurement_function = "CPD"        # placeholder
        self.frequency = 1000.0                  # placeholder
        self.voltage_level = 1.0                 # placeholder
        self.current_level = 0.01                # placeholder
        self.alc = True                          # placeholder
        self.aperture_mode = "MEDIUM"            # placeholder
        self.aperture_averages = 1               # placeholder
        self.dc_bias_state = False               # placeholder
        self.dc_bias_voltage = 0.0               # placeholder
        self.dc_bias_autorange = True            # placeholder
        self.cable_length = 0.0                  # placeholder
        self.correction_method = "SINGLE"        # placeholder
        self.data_format = "ASCII"               # placeholder
        self.ascii_long = False                  # placeholder
        self.exponent_digits = 2                 # placeholder
        self.trigger_source = "INTERNAL"         # placeholder
        self.trigger_delay = 0.0                 # placeholder
        self.initiate_continuous = True          # placeholder
        self.impedance_range = 100.0             # placeholder
        self.impedance_autorange = True          # placeholder

    # -- transport ---------------------------------------------------------
    def write(self, line, *, timeout_s=None):
        text = str(line).strip()
        with self._lock:
            self.written.append(text)
            if "?" in text:
                reply = self._query_reply(text)
                if reply is None:
                    raise TimeoutError(f"the fake instrument does not answer {text!r}")
                self._pending.append(reply)
                return
            self._apply_write(text)

    def read(self, *, timeout_s=None):
        with self._lock:
            if not self._pending:
                raise TimeoutError("no response is pending")
            return self._pending.pop(0)

    def query(self, line, *, timeout_s=None):
        self.write(line, timeout_s=timeout_s)
        return self.read(timeout_s=timeout_s)

    def close(self):
        pass

    # -- commands ----------------------------------------------------------
    @staticmethod
    def _on_off(argument: str) -> bool:
        value = argument.strip().upper()
        if value in ("1", "ON"):
            return True
        if value in ("0", "OFF"):
            return False
        raise ValueError(f"not an ON/OFF state: {argument!r}")

    @staticmethod
    def _number(argument: str) -> float:
        return float(argument.strip())

    @staticmethod
    def _integer(argument: str) -> int:
        return int(argument.strip())

    def _apply_write(self, text: str) -> None:
        command, _, argument = text.partition(" ")
        command = command.upper()
        argument = argument.strip()
        if command == ":FREQUENCY":
            self.frequency = self._number(argument)
        elif command == ":VOLTAGE:LEVEL":
            self.voltage_level = self._number(argument)
        elif command == ":CURRENT:LEVEL":
            self.current_level = self._number(argument)
        elif command == ":AMPLITUDE:ALC":
            self.alc = self._on_off(argument)
        elif command == ":APERTURE":
            mode, _, averages = argument.partition(",")
            spelling = mode.strip().upper()
            if spelling in ("SHORT", "SHOR"):
                self.aperture_mode = "SHORT"
            elif spelling in ("MEDIUM", "MED"):
                self.aperture_mode = "MEDIUM"
            elif spelling == "LONG":
                self.aperture_mode = "LONG"
            else:
                raise ValueError(f"not an aperture mode: {mode!r}")
            self.aperture_averages = self._integer(averages)
        elif command == ":BIAS:STATE":
            self.dc_bias_state = self._on_off(argument)
        elif command == ":BIAS:VOLTAGE:LEVEL":
            self.dc_bias_voltage = self._number(argument)
        elif command == ":BIAS:RANGE:AUTO":
            self.dc_bias_autorange = self._on_off(argument)
        elif command == ":FUNCTION:IMPEDANCE":
            self.measurement_function = argument.strip('"').upper()
        elif command == ":FUNCTION:IMPEDANCE:RANGE:AUTO":
            self.impedance_autorange = self._on_off(argument)
        elif command == ":FUNCTION:IMPEDANCE:RANGE":
            self.impedance_range = self._number(argument)
        elif command == ":CORRECTION:LENGTH":
            self.cable_length = self._number(argument)
        elif command == ":CORRECTION:METHOD":
            spelling = argument.strip().upper()
            if spelling in ("SINGLE", "SING"):
                self.correction_method = "SINGLE"
            elif spelling in ("MULTIPLE", "MULT"):
                self.correction_method = "MULTIPLE"
            else:
                raise ValueError(f"not a correction method: {argument!r}")
        elif command == ":FORMAT:DATA":
            spelling = argument.strip().upper()
            if spelling == "ASCII":
                self.data_format = "ASCII"
            elif spelling in ("REAL,64", "REAL64", "REAL"):
                self.data_format = "REAL,64"
            else:
                raise ValueError(f"not a data format: {argument!r}")
        elif command == ":FORMAT:ASCII:LONG":
            self.ascii_long = self._on_off(argument)
        elif command == ":FORMAT:EXPONENT:DIGIT":
            self.exponent_digits = self._integer(argument)
        elif command == ":TRIGGER:SOURCE":
            spelling = argument.strip().upper()
            if spelling in ("INTERNAL", "INT"):
                self.trigger_source = "INTERNAL"
            elif spelling == "HOLD":
                self.trigger_source = "HOLD"
            elif spelling in ("EXTERNAL", "EXT"):
                self.trigger_source = "EXTERNAL"
            elif spelling == "BUS":
                self.trigger_source = "BUS"
            else:
                raise ValueError(f"not a trigger source: {argument!r}")
        elif command == ":TRIGGER:TDEL":
            self.trigger_delay = self._number(argument)
        elif command == ":INITIATE:CONTINUOUS":
            self.initiate_continuous = self._on_off(argument)
        elif command == ":ABORT":
            pass
        elif command == "*RST":
            self._reset_state()
        else:
            raise ValueError(f"the fake instrument does not implement {text!r}")

    def _query_reply(self, text: str):
        command = text.strip().upper()
        if command == "*IDN?":
            return "KEYSIGHT TECHNOLOGIES,E4980A,PLACEHOLDER,PLACEHOLDER"  # placeholder
        if command == ":SYSTEM:ERROR?":
            return '0,"No error"'  # placeholder
        if command == ":FUNCTION:IMPEDANCE?":
            return self.measurement_function
        if command == ":FREQUENCY?":
            return str(self.frequency)
        if command == ":VOLTAGE:LEVEL?":
            return str(self.voltage_level)
        if command == ":CURRENT:LEVEL?":
            return str(self.current_level)
        if command == ":AMPLITUDE:ALC?":
            return "1" if self.alc else "0"
        if command == ":APERTURE?":
            spelling = {"SHORT": "SHORt", "MEDIUM": "MEDium", "LONG": "LONG"}[self.aperture_mode]
            return f"{spelling},{self.aperture_averages}"
        if command == ":BIAS:STATE?":
            return "1" if self.dc_bias_state else "0"
        if command == ":BIAS:VOLTAGE:LEVEL?":
            return str(self.dc_bias_voltage)
        if command == ":BIAS:RANGE:AUTO?":
            return "1" if self.dc_bias_autorange else "0"
        if command == ":CORRECTION:LENGTH?":
            return str(self.cable_length)
        if command == ":CORRECTION:METHOD?":
            return "SINGle" if self.correction_method == "SINGLE" else "MULTiple"
        if command == ":FORMAT:DATA?":
            return "ASCii" if self.data_format == "ASCII" else "REAL,64"
        if command == ":FORMAT:ASCII:LONG?":
            return "1" if self.ascii_long else "0"
        if command == ":FORMAT:EXPONENT:DIGIT?":
            return str(self.exponent_digits)
        if command == ":TRIGGER:SOURCE?":
            return {"INTERNAL": "INternal", "HOLD": "HOLD", "EXTERNAL": "EXternal",
                    "BUS": "BUS"}[self.trigger_source]
        if command == ":TRIGGER:TDEL?":
            return str(self.trigger_delay)
        if command == ":INITIATE:CONTINUOUS?":
            return "1" if self.initiate_continuous else "0"
        if command == ":FUNCTION:IMPEDANCE:RANGE?":
            return str(self.impedance_range)
        if command == ":FUNCTION:IMPEDANCE:RANGE:AUTO?":
            return "1" if self.impedance_autorange else "0"
        if command == ":FETCH:IMPEDANCE:FORMATTED?":
            return "1000.0,0.5,0"  # placeholder
        if command == ":FETCH:IMPEDANCE:CORRECTED?":
            return "10.0,5.0"  # placeholder
        if command == ":FETCH:SMONITOR:VAC?":
            return "1.0"  # placeholder
        if command == ":FETCH:SMONITOR:IAC?":
            return "0.01"  # placeholder
        if command == ":FETCH:SMONITOR:VDC?":
            return "0.0"  # placeholder
        if command == ":FETCH:SMONITOR:IDC?":
            return "0.0"  # placeholder
        return None
