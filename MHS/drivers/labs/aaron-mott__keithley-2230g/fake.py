"""Fake SCPI transport for the Keithley 2230G driver.

The fake is a stateful text transport, not a replay of an instrument session.  It answers the commands the
driver's command map sends, keeps the per-channel setpoints and output states, and returns a simple analytic
load model for the measurements.  Gate G7 (transport mode) checks the command mnemonics against the clone, not
this class.  Nothing here talks to an instrument, and the numeric replies are test data, not device facts.
"""

#: Canned identity reply.  The clone never shows an identity string, so this is test data only.  # placeholder
IDENTITY = "Keithley Instruments,2230G,0000000,1.0"  # placeholder

#: The fake's load resistance, used only to make the measured current respond to the voltage setpoint.  # placeholder
LOAD_OHMS = 10.0  # placeholder


class FakeKeithley2230g:
    """A pyserial-like/SCPI-like transport: ``write``, ``read``, ``query`` and ``close``.

    ``write`` queues the reply of a query; ``read`` pops it.  The bridge writes a query and then reads it as two
    steps when the transport has a ``read`` method.
    """

    def __init__(self, **_options):
        self._channels = {
            number: {"voltage": 0.0, "current": 0.0, "output": False}  # placeholder start state
            for number in (1, 2, 3)
        }
        self._selected = 1
        self._pending = []
        self.written = []

    # -- transport surface -------------------------------------------------
    def write(self, line, *, timeout_s=None):
        self.written.append(line)
        self._handle(line.strip())

    def read(self, *, timeout_s=None):
        if not self._pending:
            raise TimeoutError("no response is pending")
        return self._pending.pop(0)

    def query(self, line, *, timeout_s=None):
        self.write(line, timeout_s=timeout_s)
        return self.read(timeout_s=timeout_s)

    def close(self):
        pass

    def interrupt(self):
        pass

    # -- command handling --------------------------------------------------
    def _handle(self, line):
        if line == "*IDN?":
            self._pending.append(IDENTITY)
            return
        parts = [part.strip() for part in line.split(";") if part.strip()]
        if not parts:
            raise ValueError("empty command")
        selected = self._selected
        path = ""
        for part in parts:
            # SCPI preserves the parent header at a semicolon. A leading colon
            # starts at the root, as specified in the Series 2230 manual 4-8.
            absolute = part.startswith(":")
            header, separator, argument = part.lstrip(":").partition(" ")
            header = header.upper()
            full_header = header if absolute or header.startswith("*") else path + header
            command = full_header + (separator + argument if separator else "")
            if not header.startswith("*"):
                parent = full_header.rpartition(":")[0]
                path = parent + ":" if parent else ""
            if full_header == "INST:NSEL":
                selected = self._select(command, selected)
            else:
                self._execute(command, selected)

    def _select(self, part, selected):
        upper = part.upper()
        if not upper.startswith("INST:NSEL"):
            raise ValueError(f"unsupported command {part!r}")
        try:
            number = int(upper.split(None, 1)[1])
        except (IndexError, ValueError) as exc:
            raise ValueError(f"bad channel selection {part!r}") from exc
        if number not in self._channels:
            raise ValueError(f"channel {number} does not exist")
        self._selected = number
        return number

    def _execute(self, part, selected):
        upper = part.upper()
        if upper == "OUTP OFF":
            for channel in self._channels.values():
                channel["output"] = False
            return
        if upper == "OUTP ON":
            for channel in self._channels.values():
                channel["output"] = True
            return
        if upper == "OUTP?":
            self._pending.append(",".join("1" if item["output"] else "0"
                                          for item in self._channels.values()))
            return
        if upper == "VOLT?":
            self._pending.append(_number(self._channels[selected]["voltage"]))
            return
        if upper == "CURR?":
            self._pending.append(_number(self._channels[selected]["current"]))
            return
        if upper == "CHAN:OUTP?":
            self._pending.append("1" if self._channels[selected]["output"] else "0")
            return
        if upper.startswith("VOLT "):
            self._channels[selected]["voltage"] = _value(part)
            return
        if upper.startswith("CURR "):
            self._channels[selected]["current"] = _value(part)
            return
        if upper.startswith("CHAN:OUTP "):
            self._channels[selected]["output"] = _boolean(part)
            return
        if upper.startswith("MEAS:VOLT?"):
            number = _channel(part)
            self._pending.append(_number(self._measured_voltage(number)))
            return
        if upper.startswith("MEAS:CURR?"):
            number = _channel(part)
            self._pending.append(_number(self._measured_current(number)))
            return
        if upper.startswith("SYST:ERR?"):
            self._pending.append('0,"No error"')  # placeholder
            return
        raise ValueError(f"unsupported command {part!r}")

    # -- analytic load model (test data only) ------------------------------
    def _measured_voltage(self, number):
        channel = self._channels[number]
        return channel["voltage"] if channel["output"] else 0.0  # placeholder model

    def _measured_current(self, number):
        channel = self._channels[number]
        if not channel["output"] or channel["voltage"] <= 0:
            return 0.0  # placeholder model
        return min(channel["current"], channel["voltage"] / LOAD_OHMS)  # placeholder model


def _value(part):
    try:
        return float(part.split(None, 1)[1])
    except (IndexError, ValueError) as exc:
        raise ValueError(f"bad numeric value {part!r}") from exc


def _boolean(part):
    value = part.split(None, 1)[1].strip().upper()
    if value in ("ON", "1", "TRUE"):
        return True
    if value in ("OFF", "0", "FALSE"):
        return False
    raise ValueError(f"bad boolean value {part!r}")


def _channel(part):
    value = part.split(None, 1)[1].strip().upper() if " " in part else ""
    if value.startswith("CH"):
        value = value[2:]
    try:
        number = int(value)
    except ValueError as exc:
        raise ValueError(f"bad channel argument {part!r}") from exc
    if number not in (1, 2, 3):
        raise ValueError(f"channel {number} does not exist")
    return number


def _number(value):
    return format(float(value), ".12g")
