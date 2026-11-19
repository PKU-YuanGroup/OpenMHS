"""Local SCPI emulator for the pinned ``rigol_mcp.mho98.session:Session`` class.

This is an analytic protocol fake, not a recording and not the upstream simulator. It exposes only
the public surface of ``Session``: ``idn()``, ``is_healthy``, ``query_error()``, ``query()``,
``write()``, ``binary_query()`` and ``close()``. The state, the identity, the sample arrays and
every reply below are placeholder test data, never a measurement or a device bound. Unknown
commands raise, so a new wire command cannot silently pass with a made-up reply.
"""


class FakeSession:
    def __init__(self, **_options):
        self._closed = False
        self._faulted = False
        self._error = None
        self._ignore_stop = bool(_options.get("ignore_stop", False))  # test-only ignored-command fault
        self._reject_command = _options.get("reject_command")  # test-only SCPI rejection
        self._trigger_status = "RUN"  # placeholder; STOP changes this only when the command is honored
        self._ascii_reply = _options.get("ascii_reply")  # test-only malformed/nonfinite data
        self._idn = "RIGOL TECHNOLOGIES,MHO98,FAKE0001,00.00.00"  # placeholder identity
        self._timebase_scale = 0.001  # placeholder
        self._timebase_offset = 0.0  # placeholder
        self._ch1_scale = 0.5  # placeholder
        self._ch1_offset = 0.0  # placeholder
        self._source = "CHAN1"  # placeholder
        self._mode = "NORM"  # placeholder
        self._format = "ASC"  # placeholder
        self._start = 1  # placeholder
        self._stop = 8  # placeholder
        self._points = int(_options.get("waveform_points", 8))  # placeholder; supports oversized-reply tests
        self._cursor_mode = "MAN"  # placeholder
        self._cursor_type = "TIME"  # placeholder
        self._cursor_source = "CHAN1"  # placeholder
        self._cursor_a = 0.001  # placeholder
        self._cursor_b = 0.002  # placeholder
        # Placeholder BYTE samples: the values the emulator returns after the preamble conversion.
        self._samples = [10, 20, 30, 40, 50, 60, 70, 80]  # placeholder

    # -- Session surface -----------------------------------------------------------------------------------
    @property
    def is_healthy(self):
        return not self._faulted and not self._closed

    def idn(self):
        if self._closed or self._faulted:
            raise RuntimeError("MHO98 session is not healthy")
        return self._idn

    def query_error(self):
        if self._closed or self._faulted:
            raise RuntimeError("MHO98 session is not healthy")
        error = self._error
        self._error = None  # upstream drains the queue
        return error

    def query(self, command):
        if self._closed or self._faulted:
            raise RuntimeError("MHO98 session is not healthy")
        if not isinstance(command, str) or not command.strip():
            raise ValueError("command must be a non-empty string")
        command = command.strip()
        answers = {
            "*IDN?": self._idn,
            ":TRIGger:STATus?": self._trigger_status,
            ":TIMebase:MAIN:SCALe?": self._number(self._timebase_scale),
            ":TIMebase:MAIN:OFFSet?": self._number(self._timebase_offset),
            ":CHANnel1:SCALe?": self._number(self._ch1_scale),
            ":CHANnel1:OFFSet?": self._number(self._ch1_offset),
            ":WAVeform:SOURce?": self._source,
            ":WAVeform:MODE?": self._mode,
            ":WAVeform:FORMat?": self._format,
            ":WAVeform:POINts?": str(self._points),
            ":WAVeform:STARt?": str(self._start),
            ":WAVeform:STOP?": str(self._stop),
            ":WAVeform:PREamble?": self._preamble(),
            ":CURSor:MODE?": self._cursor_mode,
            ":CURSor:MANual:CAX?": self._number(self._cursor_a),
            ":CURSor:MANual:CBX?": self._number(self._cursor_b),
            ":SYSTem:ERRor?": "0,\"No error\"",  # placeholder
        }
        if command == ":WAVeform:DATA?":
            if self._format != "ASC":
                raise RuntimeError("the ASCII payload query is valid only in ASC format")
            if self._ascii_reply is not None:
                return self._ascii_reply
            return ",".join(self._number(value) for value in self._amplitudes())
        try:
            return answers[command]
        except KeyError:
            raise RuntimeError(f"fake MHO98 does not answer {command!r}") from None

    def write(self, command):
        if self._closed or self._faulted:
            raise RuntimeError("MHO98 session is not healthy")
        if not isinstance(command, str) or not command.strip():
            raise ValueError("command must be a non-empty string")
        command = command.strip()
        name, _, argument = command.partition(" ")
        if name == self._reject_command:
            self._error = '-222,"Data out of range"'  # placeholder rejection; write itself returns normally
            return
        if not argument and name in (":RUN", ":STOP"):
            if name == ":RUN":
                self._trigger_status = "RUN"  # placeholder
            elif not self._ignore_stop:
                self._trigger_status = "STOP"  # placeholder
            return
        if not argument:
            raise RuntimeError(f"fake MHO98 does not accept {command!r}")
        if name == ":TIMebase:MAIN:SCALe":
            value = self._float(argument)
            if value <= 0:
                raise ValueError("scale must be positive")
            self._timebase_scale = value
        elif name == ":TIMebase:MAIN:OFFSet":
            self._timebase_offset = self._float(argument)
        elif name == ":CHANnel1:SCALe":
            value = self._float(argument)
            if value <= 0:
                raise ValueError("scale must be positive")
            self._ch1_scale = value
        elif name == ":CHANnel1:OFFSet":
            self._ch1_offset = self._float(argument)
        elif name == ":WAVeform:SOURce":
            self._source = self._choice(argument, ("CHAN1", "CHAN2", "CHAN3", "CHAN4",
                                                   "MATH1", "MATH2", "MATH3", "MATH4"))
        elif name == ":WAVeform:MODE":
            self._mode = self._choice(argument, ("NORM", "MAX", "RAW"))
        elif name == ":WAVeform:FORMat":
            self._format = self._choice(argument, ("ASC", "BYTE", "WORD"))
        elif name == ":WAVeform:STARt":
            self._start = int(self._float(argument))
            self._points = self._stop - self._start + 1
        elif name == ":WAVeform:STOP":
            self._stop = int(self._float(argument))
            self._points = self._stop - self._start + 1
        elif name == ":WAVeform:POINts":
            self._points = int(self._float(argument))
        elif name == ":CURSor:MODE":
            token = self._choice(argument, ("OFF", "MAN", "MANUAL", "TRAC", "TRACK", "XY"))
            self._cursor_mode = "MAN" if token in ("MAN", "MANUAL") else token
        elif name == ":CURSor:MANual:TYPE":
            self._cursor_type = self._choice(argument, ("TIME", "AMPL"))
        elif name == ":CURSor:MANual:SOURce":
            self._cursor_source = self._choice(argument, ("CHAN1", "CHAN2", "CHAN3", "CHAN4",
                                                          "MATH1", "MATH2", "MATH3", "MATH4", "NONE"))
        elif name == ":CURSor:MANual:CAX":
            self._cursor_a = self._float(argument)
        elif name == ":CURSor:MANual:CBX":
            self._cursor_b = self._float(argument)
        else:
            raise RuntimeError(f"fake MHO98 does not accept {command!r}")

    def binary_query(self, command, max_bytes=64 * 1024 * 1024):
        if self._closed or self._faulted:
            raise RuntimeError("MHO98 session is not healthy")
        if command.strip() != ":WAVeform:DATA?":
            raise RuntimeError(f"fake MHO98 does not answer {command!r} as a binary block")
        if self._format != "BYTE":
            raise RuntimeError("the binary waveform query is valid only in BYTE format")
        data = bytes(self._samples[: self._points])
        if len(data) > max_bytes:
            raise ValueError("binary response is above max_bytes")
        return data

    def close(self):
        self._closed = True

    # -- placeholder state helpers -------------------------------------------------------------------------
    @staticmethod
    def _number(value):
        return format(float(value), ".15g")

    @staticmethod
    def _float(text):
        try:
            return float(str(text).strip())
        except (TypeError, ValueError):
            raise ValueError(f"not a number: {text!r}") from None

    @staticmethod
    def _choice(text, allowed):
        token = str(text).strip().upper()
        if token not in allowed:
            raise ValueError(f"unknown choice: {text!r}")
        return token

    def _preamble(self):
        # Ten fields, format code 2=ASC, 0=BYTE, 1=WORD; all values placeholder.
        code = {"BYTE": 0, "WORD": 1, "ASC": 2}[self._format]  # placeholder
        return ",".join((str(code), "0", str(self._points), "1",
                         "1.0e-3", "-4.0e-3", "0.0", "1.0e-2", "-0.5", "0.0"))  # placeholder fields

    def _amplitudes(self):
        return [(sample - (-0.5) - 0.0) * 1.0e-2 for sample in self._samples[: self._points]]  # placeholder
