"""Fake SCPI transport of the Siglent SDG 2042X driver: an in-memory stand-in for ``func_gen_test:func_gen``.

The upstream clone has no simulator and no recorded session: it is two PyVISA debug scripts.  This transport answers
the queries the driver sends (``*IDN?``, ``C2:OUTP?`` and ``C2:BaSic_WaVe?``) from its own state, and a write of a
setting changes the answer of the query for that setting.  The start values are test data, not a fact or a limit of
any device; every one is marked ``# placeholder``.  Nothing here talks to an instrument.

Gate G7 (transport mode) checks the command mnemonics the driver sends against the clone, not this class.
"""


class FakeSdg2042x:
    """A fresh in-memory generator per endpoint; every starting value is a placeholder."""

    #: The identity the guide's *IDN? format shows (GUIDE page 14); the serial is a placeholder.
    IDENTITY = "Siglent Technologies,SDG2042X,FAKE000000,6.01.01.28"  # placeholder

    def __init__(self, **_options):
        self.output = "OFF"          # placeholder: fails safe
        self.waveform = "SQUARE"     # placeholder
        self.frequency = 1000.0      # placeholder, Hz
        self.amplitude = 1.0         # placeholder, Vpp
        self.offset = 0.0            # placeholder, V
        self.duty_cycle = 50.0       # placeholder, percent
        self.written = []
        self._pending = []

    def _wave_reply(self):
        period = 1.0 / self.frequency if self.frequency > 0 else 0.0
        return (f"C2:BSWV WVTP,{self.waveform},FRQ,{self.frequency:g}HZ,PERI,{period:g}S,"
                f"AMP,{self.amplitude:g}V,OFST,{self.offset:g}V,DUTY,{self.duty_cycle:g}")

    def write(self, line, *, timeout_s=None):
        self.written.append(line)
        text = line.strip()
        if text == "*IDN?":
            self._pending.append(self.IDENTITY)
            return
        if text == "C2:OUTP?":
            self._pending.append(f"C2:OUTP {self.output},LOAD,HZ,PLRT,NOR")
            return
        if text == "C2:BaSic_WaVe?":
            self._pending.append(self._wave_reply())
            return
        if text.startswith("C2:OUTP "):
            token = text[len("C2:OUTP "):].split(",", 1)[0].strip().upper()
            if token in ("ON", "OFF"):
                self.output = token
            return
        if text.startswith("C2:BaSic_WaVe "):
            parts = [item.strip() for item in text[len("C2:BaSic_WaVe "):].split(",")]
            if len(parts) < 2:
                return
            parameter, value = parts[0].upper(), parts[1]
            if parameter == "WVTP":
                self.waveform = value.upper()
            elif parameter == "FRQ":
                self.frequency = float(value)
            elif parameter == "AMP":
                self.amplitude = float(value)
            elif parameter == "OFST":
                self.offset = float(value)
            elif parameter == "DUTY":
                self.duty_cycle = float(value)

    def read(self, *, timeout_s=None):
        if not self._pending:
            raise TimeoutError("no response is pending")
        return self._pending.pop(0)

    def query(self, line, *, timeout_s=None):
        self.write(line, timeout_s=timeout_s)
        return self.read(timeout_s=timeout_s)

    def close(self):
        pass
