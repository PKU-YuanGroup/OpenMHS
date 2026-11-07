"""Fake SCPI transport of the keyoscacquire driver: the instrument settings as plain state.

The state starts from canned values (every number here is test data, marked ``# placeholder``) and nothing else:
this is not a recording of an instrument.  A write changes the answer of its own query, so the resource state
shows what was written, and ``:STOP`` makes the e-stop observable in the operation condition register.

Gate G7 (transport mode) checks the command mnemonics the driver sends against the upstream clone, not this
class.  Nothing here talks to an instrument.
"""

#: Canned identity in the shape the clone documents ('KEYSIGHT TECHNOLOGIES,MSO9104A,MY12345678,06.30.00609').
_IDENTITY = "KEYSIGHT TECHNOLOGIES,DSO-X 3024A,MY0000000,07.20.00000"  # placeholder
#: Canned initial settings and status of the stand-in instrument.
_ACQ_TYPE = "HRES"  # placeholder
_NUM_AVERAGES = 8  # placeholder
_POINTS_MODE = "RAW"  # placeholder
_NUM_POINTS = 1000  # placeholder
_WAV_FORMAT = "WORD"  # placeholder
_OPERATION_RUNNING = 8  # placeholder: bit 3 set, the instrument is running
_NO_ERROR = '0,"No error"'  # placeholder: an empty error queue answers +0

#: The queries this transport answers, and the settings that answer them.
_QUERIES = {
    "*IDN?": lambda fake: _IDENTITY,
    ":ACQuire:TYPE?": lambda fake: fake.acq_type,
    ":ACQuire:COUNt?": lambda fake: str(fake.num_averages),
    ":WAVeform:POINts:MODE?": lambda fake: fake.points_mode,
    ":WAVeform:POINTs?": lambda fake: str(fake.num_points),
    ":WAVeform:FORMat?": lambda fake: fake.wav_format,
    ":OPERegister:CONDition?": lambda fake: str(fake.operation_condition),
    ":SYSTem:ERRor?": lambda fake: fake.errors.pop(0) if fake.errors else _NO_ERROR,
}


class FakeKeyoscacquire:
    """A stand-in SCPI instrument: ``write``/``read``/``query`` of text lines, as the bridge's transport."""

    def __init__(self, **_options):
        self.written = []
        self.errors = []
        self._pending = []
        self.acq_type = _ACQ_TYPE
        self.num_averages = _NUM_AVERAGES
        self.points_mode = _POINTS_MODE
        self.num_points = _NUM_POINTS
        self.wav_format = _WAV_FORMAT
        self.operation_condition = _OPERATION_RUNNING

    def write(self, line, *, timeout_s=None):
        self.written.append(line)
        if not line.endswith("?"):
            self._apply(line)
            return
        answer = _QUERIES.get(line)
        if answer is None:
            # Like an instrument that does not know the query: the read times out.
            raise TimeoutError(f"the stand-in instrument does not answer {line!r}")
        self._pending.append(answer(self))

    def read(self, *, timeout_s=None):
        if not self._pending:
            raise TimeoutError("no response is pending")
        return self._pending.pop(0)

    def query(self, line, *, timeout_s=None):
        self.write(line, timeout_s=timeout_s)
        return self.read(timeout_s=timeout_s)

    def close(self):
        pass

    def _apply(self, line):
        command, _, argument = line.partition(" ")
        argument = argument.strip()
        if command == ":ACQuire:TYPE":
            self.acq_type = argument
        elif command == ":ACQuire:COUNt":
            self.num_averages = int(argument)
        elif command == ":WAVeform:POINts:MODE":
            self.points_mode = argument
        elif command == ":WAVeform:POINts":
            self.num_points = int(argument)
        elif command == ":WAVeform:FORMat":
            self.wav_format = argument
        elif command == ":STOP":
            self.operation_condition = 0  # placeholder: bit 3 cleared, the acquisition stopped
        elif command == ":RUN":
            self.operation_condition = _OPERATION_RUNNING
