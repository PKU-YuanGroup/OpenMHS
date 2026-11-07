"""Fake serial transport of the GNSDO driver: an in-memory SCPI device, not a recording and not upstream code.

The bridge expects a pyserial-like object (``write``/``readline``/``read``/``reset_input_buffer``/``close``).  This
class implements the scalar commands the driver maps and updates its own state when the driver sends a setter.  It
does not import or run the upstream simulator (hard rule: the clone is read-only and is never imported), and it does
not talk to an instrument.  The class answers only the commands the driver sends; any other query gets no line, so
the bridge reports an unknown outcome exactly as it would for a device that does not answer.

Every number below is test data for the fake, not a device fact or a safety limit: the state values are marked
``# placeholder`` and none of them is copied into a Fact, a Limit or the reference.  Gate G7 (transport mode) checks
the command mnemonics the driver sends against the clone, not this class.
"""

from datetime import datetime, timedelta

#: Placeholder identity and state values for the fake; none is a fact about an instrument.
IDENTITY = "Jackson Labs, LN Rb GPSDO (PRE), Firmware Rev 1.17"    # placeholder
TINT_NORMAL_S = 1.2e-8                                           # placeholder
TINT_HOLDOVER_S = 8.5e-7                                         # placeholder
TRACKED_SATELLITES = 8                                           # placeholder
VISIBLE_SATELLITES = 12                                          # placeholder
PCB_TEMPERATURE_CEL = 42.5                                       # placeholder
TCXO_VOLTAGE_V = 1.66                                            # placeholder
POWER_SUPPLY_VOLTAGE_V = 11.7                                    # placeholder
CSAC_TEMPERATURE_CEL = 54.0                                      # placeholder
CSAC_LIFETIME_HOURS = 11247                                      # placeholder
LIFETIME_HOURS = 871                                             # placeholder
LEAP_SECONDS = 18                                                # placeholder
CSAC_SERIAL_NUMBER = "2209MX04906"                               # placeholder

#: Commands that change state; all of them answer with an empty line in the upstream server.
_SETTERS = {"SYNC:HOLD:INIT", "SYNC:HOLD:REC:INIT", "SYNC:SOUR:MODE", "PTIME:OUTPUT"}


class FakeGnsdoScpiSimulator:
    def __init__(self, **_options):
        # Controlled fixture time; no wall-clock progress is inferred from reads.
        self._clock = datetime(2000, 1, 1, 12, 0, 0)             # placeholder
        self.is_open = True
        self.timeout = 0.1                                       # placeholder
        self.written: list[str] = []
        self._buffer = bytearray()
        self.sync_locked = True
        self.holdover = False
        self.holdover_started_at = None
        self.sync_source_mode = "GPS"
        self.ptime_output_enabled = False
        self.tint = TINT_NORMAL_S
        self.satellites_tracked = TRACKED_SATELLITES
        self.satellites_visible = VISIBLE_SATELLITES
        self.pcb_temperature = PCB_TEMPERATURE_CEL
        self.tcxo_voltage = TCXO_VOLTAGE_V
        self.power_supply_voltage = POWER_SUPPLY_VOLTAGE_V
        self.csac_temperature = CSAC_TEMPERATURE_CEL
        self.csac_lifetime = CSAC_LIFETIME_HOURS
        self.lifetime = LIFETIME_HOURS
        self.leap_seconds = LEAP_SECONDS
        self.csac_serial_number = CSAC_SERIAL_NUMBER

    def advance_time(self, seconds: float) -> None:
        """Advance this fake's clock explicitly; this is not a device command."""
        self._clock += timedelta(seconds=seconds)

    # -- pyserial-like transport -------------------------------------------------
    def write(self, data: bytes) -> int:
        line = data.decode("ascii", "replace").replace("\r", "").replace("\n", "").strip().upper()
        self.written.append(line)
        if line.endswith("?"):
            reply = self._query(line)
            if reply is not None:
                self._buffer.extend(reply.encode("ascii") + b"\r\n")
            return len(data)
        command, _, argument = line.partition(" ")
        argument = argument.strip()
        if command in _SETTERS:
            self._set(command, argument)
            # The upstream server answers a recognised setter with an empty line.
            self._buffer.extend(b"\r\n")
        return len(data)

    def readline(self) -> bytes:
        newline = self._buffer.find(b"\n")
        if newline < 0:
            chunk = bytes(self._buffer)
            self._buffer.clear()
            return chunk
        chunk = bytes(self._buffer[: newline + 1])
        del self._buffer[: newline + 1]
        return chunk

    def read(self, size: int = 1) -> bytes:
        chunk = bytes(self._buffer[:size])
        del self._buffer[:size]
        return chunk

    def reset_input_buffer(self) -> None:
        self._buffer.clear()

    def close(self) -> None:
        self.is_open = False

    # -- device behaviour --------------------------------------------------------
    def _query(self, line: str):
        if line == "SYNC:LOCKED?":
            return "1" if self.sync_locked else "0"
        if line == "SYNC:TINT?":
            return f"{self.tint:.3E}"
        if line == "SYNC:HEALTH?":
            return self._health()
        if line == "SYNC:HOLD:DUR?":
            return self._holdover_duration()
        if line == "GPS:SAT:TRAC:COUN?":
            return str(self.satellites_tracked)
        if line == "GPS:SAT:VIS:COUN?":
            return str(self.satellites_visible)
        if line == "MEAS:TEMP?":
            return str(self.pcb_temperature)
        if line == "MEAS:VOLT?":
            return str(self.tcxo_voltage)
        if line == "MEAS:POW?":
            return str(self.power_supply_voltage)
        if line == "CSAC:TEMP?":
            return str(self.csac_temperature)
        if line == "CSAC:STATUS?":
            return "0" if self.sync_locked else "1"
        if line == "CSAC:SN?":
            return self.csac_serial_number
        if line == "CSAC:LIFE?":
            return str(self.csac_lifetime)
        if line == "DIAG:LIFE:COUN?":
            return str(self.lifetime)
        if line == "PTIME:LEAP:ACC?":
            return str(self.leap_seconds)
        if line == "PTIME:OUTPUT?":
            return "1" if self.ptime_output_enabled else "0"
        if line == "PTIME:DATE?":
            now = self._clock
            return f"{now.year},{now.month},{now.day}"
        if line == "PTIME:TIME?":
            now = self._clock
            return f"{now.hour},{now.minute},{now.second}"
        if line == "*IDN?":
            return IDENTITY
        return None

    def _set(self, command: str, argument: str) -> None:
        if command == "SYNC:HOLD:INIT":
            self.holdover = True
            self.sync_locked = False
            self.holdover_started_at = self._clock
            self.tint = TINT_HOLDOVER_S
        elif command == "SYNC:HOLD:REC:INIT":
            self.holdover = False
            self.sync_locked = True
            self.holdover_started_at = None
            self.tint = TINT_NORMAL_S
        elif command == "SYNC:SOUR:MODE" and argument:
            self.sync_source_mode = argument
        elif command == "PTIME:OUTPUT":
            self.ptime_output_enabled = argument == "ON"

    def _health(self) -> str:
        health = 0
        if self.tint > 210e-9:                                   # placeholder threshold, see SYNC:HEALTH?
            health |= 0x4
        if self.holdover and self.holdover_started_at is not None:
            if (self._clock - self.holdover_started_at).total_seconds() > 60:    # placeholder threshold
                health |= 0x10
        return f"0x{health:X}"

    def _holdover_duration(self) -> str:
        if not self.holdover or self.holdover_started_at is None:
            return "0,0"
        seconds = (self._clock - self.holdover_started_at).total_seconds()
        return f"{seconds:.1f},1"
