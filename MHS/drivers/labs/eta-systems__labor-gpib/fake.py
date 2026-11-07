"""Fake backend for the NGMO2 channel A driver: an in-memory stand-in for ``devices.rohde_schwarz_ngmo2:device``.

The upstream class is a text command writer over a GPIB transport, so the fake reproduces the two objects the driver
uses: the device object with ``send_command`` and the query methods, and a small bus with ``write``,
``read_until_char`` and ``request`` in the shape of ``src/interface/prologix_gpib.py:45-99``.  Every public method of
``FakeNgmo2`` exists on the upstream ``device`` class (src/devices/rohde_schwarz_ngmo2.py:16-236); the nested
``FakeChannel``, ``FakeDisplay`` and ``FakeFormat`` methods likewise exist on the upstream ``Channel``, ``Display``
and ``Format`` classes.  The driver sends the same command strings the upstream methods assemble, for example
``:SOUR:A:VOLT`` (line 408) and ``:OUT:A OFF`` (line 395), so G7 does not need a transport command table here.

The fake keeps one plain state dictionary per channel.  A measurement follows the set point while the output is on and
is zero while it is off; that is test behaviour, not a claim about an instrument.  Every number and reply below is
placeholder test data for this stand-in, never a Fact, a Limit or a reference, and each one is marked
``# placeholder``.  Nothing here talks to a device.
"""


class FakeBus:
    """The Prologix-like transport of the stand-in: text lines and one pending reply queue."""

    def __init__(self, owner):
        self.owner = owner
        self.address = 1  # placeholder test data
        self.pending = []

    def set_address(self, address):
        self.address = int(address)

    def write(self, address, message):
        self.set_address(address)
        self.owner._bus_write(str(message).strip())
        return len(str(message))  # placeholder test data: a write length, not a device reply

    def read_until_char(self, address, char):
        self.set_address(address)
        if not self.pending:
            raise TimeoutError("no reply is pending")
        return self.pending.pop(0)

    def read(self, address):
        return self.read_until_char(address, "10")

    def read_eoi(self, address):
        return self.read_until_char(address, "10")

    def request(self, address, message):
        self.write(address, message)
        return self.read_until_char(address, "10")

    def clr(self):
        self.owner._reset_state()

    def trg(self):
        self.owner._bus_write("*TRG")

    def spoll(self):
        return "0"  # placeholder test data

    def loc(self):
        return None

    def close(self):
        return None


class FakeNgmo2:
    """In-memory ``rohde_schwarz_ngmo2.device`` for the fake backend."""

    def __init__(self, **_options):
        self.address = 7  # placeholder test data: the constructor default is not a device fact
        self.armed = False  # placeholder test data
        self.display_on = True  # placeholder test data
        self.display_channel = "A"  # placeholder test data
        self.byte_order = "NORMal"  # placeholder test data
        self.format_value = "ASC"  # placeholder test data
        self._channels = {
            "A": {"voltage": 0.0, "current": 0.0, "interval": 0.2, "averaging": 1,  # placeholder test data
                  "sense": "VOLT", "range": "AUTO", "output": False, "impedance": 0.0,  # placeholder test data
                  "bandwidth": "HIGH"},  # placeholder test data
            "B": {"voltage": 0.0, "current": 0.0, "interval": 0.2, "averaging": 1,  # placeholder test data
                  "sense": "VOLT", "range": "AUTO", "output": False, "impedance": 0.0,  # placeholder test data
                  "bandwidth": "HIGH"},  # placeholder test data
        }
        self.commands = []  # text this stand-in was given, in order; not a device fact
        self.bus = FakeBus(self)
        self.channel_a = FakeChannel(self, "A")
        self.channel_b = FakeChannel(self, "B")
        self.display = FakeDisplay(self)
        self.format = FakeFormat(self)
        self.status = FakeStatus(self)

    # -- helpers ------------------------------------------------------------------------------------------------
    def _channel(self, letter):
        letter = str(letter).strip().upper()
        if letter not in self._channels:
            raise ValueError("channel must be A or B")
        return self._channels[letter]

    def _reset_state(self):
        """Placeholder state used when this stand-in sees *RST, and by the fake bus clear.

        The clone's comment on ``rst`` says the supply returns to the ``*RST`` default conditions
        (src/devices/rohde_schwarz_ngmo2.py:80) and does not state them.  Every number below, including
        output off, is placeholder test data, not that default.
        """
        for state in self._channels.values():
            state["voltage"] = 0.0  # placeholder test data
            state["current"] = 0.0  # placeholder test data
            state["interval"] = 0.2  # placeholder test data
            state["averaging"] = 1  # placeholder test data
            state["sense"] = "VOLT"  # placeholder test data
            state["range"] = "AUTO"  # placeholder test data
            state["output"] = False  # placeholder test data
            state["impedance"] = 0.0  # placeholder test data
            state["bandwidth"] = "HIGH"  # placeholder test data
        self.armed = False  # placeholder test data
        self.display_on = True  # placeholder test data
        self.display_channel = "A"  # placeholder test data
        self.byte_order = "NORMal"  # placeholder test data
        self.format_value = "ASC"  # placeholder test data
        self.bus.pending.clear()

    def _measurement(self, letter):
        state = self._channel(letter)
        if not state["output"]:
            return "0.0"  # placeholder test data
        return f"{state['current'] if state['sense'] == 'CURR' else state['voltage']:.6E}"  # placeholder test data

    def _bus_write(self, text):
        """Apply one upstream command or queue the reply to one upstream query."""
        self.commands.append(text)
        channel = None
        if text.startswith(":OUT:") or text.startswith(":OUTP:") or text.startswith(":SOUR:") \
                or text.startswith(":SENS:") or text.startswith(":MEAS:"):
            pieces = text.split(":")
            if len(pieces) > 2:
                candidate = pieces[2].split()[0].rstrip("?")
                if candidate in ("A", "B"):
                    channel = candidate
        if text == "*IDN?":
            self.bus.pending.append("ROHDE&SCHWARZ,NGMO2,0,0.0 /A:0:0.0,B:0:0.0")  # placeholder test data
        elif text == "*STB?":
            self.bus.pending.append("0")  # placeholder test data
        elif text == "*CLS":
            return
        elif text == "*RST":
            self._reset_state()
        elif text == "*ARM":
            self.armed = True  # placeholder test data
        elif text == "*TRG":
            return
        elif text == ":FORMat:DATA?":
            self.bus.pending.append(self.format_value)
        elif text.startswith(":FORMat:DATA "):
            token = text.split(" ", 1)[1].strip().upper()
            if token in ("ASC", "ASCII"):
                self.format_value = "ASC"  # placeholder test data
            elif token == "LONG":
                self.format_value = "LONG"  # placeholder test data
            elif token in ("SRE", "SREAL"):
                self.format_value = "SRE"  # placeholder test data
            elif token in ("DRE", "DREAL"):
                self.format_value = "DRE"  # placeholder test data
            else:
                raise ValueError(f"unsupported data format {token!r}")
        elif text.startswith(":FORMat:BORDer "):
            token = text.split(" ", 1)[1].strip().upper()
            if token not in ("NORM", "NORMAL", "SWAP", "SWAPPED"):
                raise ValueError(f"unsupported byte order {token!r}")
            self.byte_order = "NORMal" if token.startswith("NORM") else "SWAPped"  # placeholder test data
        elif text == ":DISP:ENAB?":
            self.bus.pending.append("ON" if self.display_on else "OFF")  # placeholder test data
        elif text.startswith(":DISP:ENAB "):
            token = text.split(" ", 1)[1].strip().upper()
            if token not in ("ON", "OFF"):
                raise ValueError(f"unsupported display state {token!r}")
            self.display_on = token == "ON"  # placeholder test data
        elif text == ":DISP:CHAN?":
            self.bus.pending.append(self.display_channel)
        elif text.startswith(":OUT:") and text.endswith((" ON", " OFF")):
            state = self._channel(channel)
            state["output"] = text.endswith(" ON")  # placeholder test data
        elif text.startswith(":OUTP:") and text.endswith(":STAT?"):
            state = self._channel(channel)
            self.bus.pending.append("ON" if state["output"] else "OFF")  # placeholder test data
        elif text.startswith(":OUTP:") and text.endswith(":BAND?"):
            state = self._channel(channel)
            self.bus.pending.append(state["bandwidth"])
        elif text.startswith(":OUTP:") and text.endswith(":BAND:HIGH"):
            state = self._channel(channel)
            state["bandwidth"] = "HIGH"  # placeholder test data
        elif text.startswith(":OUTP:") and text.endswith(":BAND:LOW"):
            state = self._channel(channel)
            state["bandwidth"] = "LOW"  # placeholder test data
        elif text.startswith(":OUTP:") and ":IMP:" in text:
            state = self._channel(channel)
            token = text.rsplit(":IMP:", 1)[1]
            if token in ("MAX", "max"):
                state["impedance"] = 1.00  # placeholder test data
            elif token in ("MIN", "min"):
                state["impedance"] = 0.00  # placeholder test data
            else:
                state["impedance"] = round(float(token), 2)  # placeholder test data
        elif text.startswith(":SOUR:") and ":VOLT " in text:
            state = self._channel(channel)
            state["voltage"] = round(float(text.split(" ", 1)[1]), 3)  # placeholder test data
        elif text.startswith(":SOUR:") and ":CURR:LIM " in text:
            state = self._channel(channel)
            state["current"] = round(float(text.split(" ", 1)[1]), 3)  # placeholder test data
        elif text.startswith(":SENS:") and ":FUNC " in text:
            state = self._channel(channel)
            token = text.split(" ", 1)[1].strip().upper()
            values = {"VOLT": "VOLT", "CURR": "CURR", "DVM": "DVM", "AVER": "AVER", "PEAK": "PEAK",
                      "MIN": "MIN", "HIGH": "HIGH", "LOW": "LOW", "RMS": "RMS"}
            if token not in values:
                raise ValueError(f"unsupported sense function {token!r}")
            state["sense"] = values[token]  # placeholder test data
        elif text.startswith(":SENS:") and text.endswith(":FUNC?"):
            state = self._channel(channel)
            self.bus.pending.append(state["sense"])
        elif text.startswith(":SENS:") and ":CURR:RANG:UPP:" in text:
            state = self._channel(channel)
            token = text.rsplit(":", 1)[1].strip().upper()
            if token not in ("AUTO", "HIGH", "MED", "MIN"):
                raise ValueError(f"unsupported current range {token!r}")
            state["range"] = token  # placeholder test data
        elif text.startswith(":SENS:") and text.endswith(":CURR:DC:RANG:UPP?"):
            state = self._channel(channel)
            self.bus.pending.append(state["range"])
        elif text.startswith(":SENS:") and text.endswith(":MEAS:INT?"):
            state = self._channel(channel)
            self.bus.pending.append(f"{state['interval']:g}")
        elif text.startswith(":SENS:") and ":MEAS:INT " in text:
            state = self._channel(channel)
            state["interval"] = round(float(text.split(" ", 1)[1]), 5)  # placeholder test data
        elif text.startswith(":SENS:") and ":MEAS:AVER:COUN " in text:
            state = self._channel(channel)
            state["averaging"] = int(float(text.split(" ", 1)[1]))  # placeholder test data
        elif text.startswith(":MEAS:") and text.endswith("?"):
            self.bus.pending.append(self._measurement(channel))
        else:
            raise ValueError(f"the fake stand-in does not model the command {text!r}")

    # -- device surface -------------------------------------------------------------------------------------------
    def send_command(self, command):
        self.bus.write(self.address, command)

    def get_idn(self):
        return self.bus.request(self.address, "*IDN?")

    def idn(self):
        return self.bus.request(self.address, "*IDN?")

    def get_status(self):
        return self.bus.request(self.address, "*STB?")

    def get_output_format(self):
        return self.format.get_data()

    def set_output_format(self, form):
        self.format.data(form)

    def set_output_byte_order(self, order):
        order = str(order).lower()
        if order in ("normal", "msbfirst"):
            self.send_command(":FORMat:BORDer NORMal")
        elif order in ("swapped", "lsbfirst"):
            self.send_command(":FORMat:BORDer SWAPped")
        else:
            raise ValueError(f"Unknown byte order: {order!r}")

    def arm(self):
        self.send_command("*ARM")

    def reset(self):
        self.send_command("*RST")
        self.send_command("*CLS")

    def rst(self):
        self.send_command("*RST")

    def clear(self):
        self.rst()

    def cls(self):
        self.send_command("*CLS")

    def channel(self, char_val="A"):
        return self.channel_a if str(char_val).upper() == "A" else self.channel_b

    def output(self, char_val="A"):
        return self.channel(char_val)


class FakeChannel:
    """In-memory ``rohde_schwarz_ngmo2.Channel``: the same command names as the upstream class."""

    def __init__(self, owner, letter):
        self.owner = owner
        self.letter = str(letter).upper()

    def _state(self):
        return self.owner._channel(self.letter)

    def on(self):
        self.owner.send_command(f":OUT:{self.letter} ON")

    def off(self):
        self.owner.send_command(f":OUT:{self.letter} OFF")

    def is_on(self):
        return self.owner.bus.request(self.owner.address, f":OUTP:{self.letter}:STAT?")

    def voltage(self, voltage=0.0):
        if not 0 <= float(voltage) <= 15:  # placeholder test data: fake check, not a limit
            raise ValueError("voltage out of range")
        self.owner.send_command(f":SOUR:{self.letter}:VOLT {round(float(voltage), 3)}")  # placeholder test data

    def current(self, current=0.000):
        if not 0 <= float(current) <= 5:  # placeholder test data: fake check, not a limit
            raise ValueError("current out of range")
        value = round(float(current), 3)  # placeholder test data
        self.owner.send_command(f":SOUR:{self.letter}:CURR:LIM {value:.2E}")  # placeholder test data

    def sense(self, meas_type="VOLT"):
        token = str(meas_type).lower()
        mapping = {"volt": "VOLT", "curr": "CURR", "current": "CURR", "amp": "CURR", "dv": "DVM", "dvm": "DVM",
                   "dvmeter": "DVM", "avg": "AVER", "aver": "AVER", "average": "AVER", "peak": "PEAK", "min": "MIN",
                   "high": "HIGH", "low": "LOW", "rms": "RMS"}
        if token not in mapping:
            raise ValueError(f"Unknown sense function: {meas_type!r}")
        self.owner.send_command(f":SENS:{self.letter}:FUNC {mapping[token]}")  # placeholder test data

    def get_sense(self):
        return self.owner.bus.request(self.owner.address, f":SENS:{self.letter}:FUNC?")

    def current_range(self, char_val):
        token = str(char_val).lower()
        mapping = {"auto": "AUTO", "min": "AUTO", "high": "HIGH", "hi": "HIGH", "5": "HIGH", "5a": "HIGH",
                   "def": "HIGH", "default": "HIGH", "medium": "MED", "med": "MED", "0.5": "MED", "0.5a": "MED",
                   "500ma": "MED", "max": "MIN", "low": "MIN", "0.005": "MIN", "0.005a": "MIN", "5ma": "MIN"}
        if token not in mapping:
            raise ValueError("Unknown Sense Current Limit Setting")
        self.owner.send_command(f":SENS:{self.letter}:CURR:RANG:UPP:{mapping[token]}")  # placeholder test data

    def get_current_range(self):
        return self.owner.bus.request(self.owner.address, f":SENS:{self.letter}:CURR:DC:RANG:UPP?")

    def interval(self, val):
        self.measure_interval(val)

    def measure_interval(self, val):
        value = float(val)
        if not 0.00001 <= value <= 1.0:  # placeholder test data: fake check, not a limit
            raise ValueError("sample interval out of range")
        self.owner.send_command(f":SENS:{self.letter}:MEAS:INT {round(value, 5):.2E}")  # placeholder test data

    def get_interval(self):
        return float(self.owner.bus.request(self.owner.address, f":SENS:{self.letter}:MEAS:INT?"))

    def set_averaging_samples(self, val):
        value = 1 if val in ("min", "def", "default") else 10 if val == "max" else int(val)  # placeholder test data
        if not 1 <= value <= 10:  # placeholder test data: fake check, not a limit
            raise ValueError("Measure average count out of range 1 - 10")
        self.owner.send_command(f":SENS:{self.letter}:MEAS:AVER:COUN {value}")  # placeholder test data

    def band_width(self, char_val):
        token = str(char_val).lower()
        if token in ("high", "max", "def", "default"):
            self.owner.send_command(f":OUTP:{self.letter}:BAND:HIGH")
        elif token in ("min", "low"):
            self.owner.send_command(f":OUTP:{self.letter}:BAND:LOW")
        else:
            raise ValueError(f"Unknown bandwidth setting: {char_val!r}")

    def get_bandwidth(self):
        return self.owner.bus.request(self.owner.address, f":OUTP:{self.letter}:BAND?")

    def impedance(self, val=0.00):
        if isinstance(val, str):
            if val == "max":
                self.owner.send_command(f":OUTP:{self.letter}:IMP:MAX")
                return
            if val in ("min", "def", "default"):
                self.owner.send_command(f":OUTP:{self.letter}:IMP:MIN")
                return
            raise ValueError("Unknown impedance setting")
        value = round(float(val), 2)  # placeholder test data
        if not 0.00 <= value <= 1.00:  # placeholder test data: fake check, not a limit
            raise ValueError("Impedance out of range")
        self.owner.send_command(f":OUTP:{self.letter}:IMP:{value}")  # placeholder test data

    def get_impedance(self):
        return self.get_bandwidth()

    def read_voltage(self):
        self.sense("volt")
        self.owner.send_command(f":MEAS:{self.letter}?")
        return self.owner.bus.read_until_char(self.owner.address, "10")

    def read_current(self):
        self.sense("current")
        self.owner.send_command(f":MEAS:{self.letter}?")
        return self.owner.bus.read_until_char(self.owner.address, "10")


class FakeDisplay:
    """In-memory ``rohde_schwarz_ngmo2.Display``."""

    def __init__(self, owner):
        self.owner = owner

    def enable(self, on=True):
        self.owner.send_command(":DISP:ENAB ON" if on else ":DISP:ENAB OFF")

    def enabled(self):
        value = self.owner.bus.request(self.owner.address, ":DISP:ENAB?")
        if "on" in value.lower():
            return True
        if "off" in value.lower():
            return False
        raise RuntimeError(f"Unhandled value from NGMO2: {value!r}")

    def set_channel(self, channel):
        name = str(channel).lower()
        if name in ("a", "min"):
            self.owner.display_channel = "A"  # placeholder test data
        elif name in ("b", "max"):
            self.owner.display_channel = "B"  # placeholder test data
        elif name in ("dvm a", "dvm b", "def"):
            self.owner.display_channel = name.upper()  # placeholder test data
        else:
            raise ValueError(f"Unknown channel setting: {channel!r}")

    def selected_channel(self):
        return self.owner.bus.request(self.owner.address, ":DISP:CHAN?")

    def view(self, mode=""):
        return None


class FakeFormat:
    """In-memory ``rohde_schwarz_ngmo2.Format``."""

    def __init__(self, owner):
        self.owner = owner

    def data(self, char_val):
        token = str(char_val).lower()
        if token in ("asc", "ascii", "min", "def"):
            cmd = "ASCii"
        elif token == "long":
            cmd = "LONG"
        elif token in ("short", "sre", "sreal"):
            cmd = "SREal"
        elif token in ("double", "dre", "dreal", "max"):
            cmd = "DREal"
        else:
            raise ValueError(f"Unknown data format: {char_val!r}")
        self.owner.send_command(f":FORMat:DATA {cmd}")

    def get_data(self):
        return self.owner.bus.request(self.owner.address, ":FORMat:DATA?")

    def border(self, char_val):
        token = str(char_val).lower()
        if token in ("norm", "normal", "min", "def"):
            cmd = "NORMal"
        elif token in ("swap", "swapped", "max"):
            cmd = "SWAPped"
        else:
            raise ValueError(f"Unknown border format: {char_val!r}")
        self.owner.send_command(f":FORMat:BORDer {cmd}")


class FakeStatus:
    """In-memory ``rohde_schwarz_ngmo2.Status``; the upstream class defines no status methods."""

    def __init__(self, owner):
        self.owner = owner
