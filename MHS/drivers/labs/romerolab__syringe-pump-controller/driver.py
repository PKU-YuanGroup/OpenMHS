"""OpenMHS driver for gh.romerolab/syringe-pump-controller: a New Era NE-500/501 syringe pump over serial.

The upstream repository is a Python 2 PyQt4 GUI (``pump_control.py:14``) that opens one serial port at
19200 baud (``pump_control.py:22``) and sends the CR-terminated ASCII commands of ``new_era.py``.  It has no
device class: the protocol is a set of module functions.  The only upstream class is the GUI itself, so
``native`` names that class (it owns the serial link, ``self.ser``) and this package is a direct Driver whose
``self.native`` is the pyserial-like object the GUI owns.  The commands are the exact lines of ``new_era.py``,
including the per-pump address prefix; a SerialDriver command table cannot build that prefix, and adding a
space to make the token visible to G7 would change the wire syntax.

* reads: flow rate (``<n>RAT``, sign from ``<n>DIR``), direction and syringe diameter (``<n>DIA``);
* writes: flow rate (``<n>DIR`` + ``<n>RAT``) and syringe diameter (``<n>DIA``);
* actions: run at a rate for a volume or duration (the catalogue pump class), prime (the upstream
  ``DIRINF`` + ``RAT10.0MH`` + ``RUN`` sequence) and stop all pumps (the safe state, ``*STP``);
* the e-stop sends the broadcast ``*STP`` without waiting for a reply.

Every Fact cites a line of the clone at the pinned commit.  No text file states a flow-rate, diameter,
volume or duration range, so those are ``Limit.operator_required``: every write is refused until the site
supplies its bounds in ``site-limits.json`` (``site-limits.example.json`` shows the overlay).  This package is
model-authored and unreviewed, and it is checked on the fake backend only; no hardware run was made.
"""

import time

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

#: The clone's serial protocol module and its GUI (the only class; the serial link is ``self.ser``).
NEW_ERA = "new_era.py"
PUMP_CONTROL = "pump_control.py"

#: The split of ``new_era.set_rates``: below 5000 the rate is sent in UH, at 5000 and above in MH.
RATE_UNIT_SPLIT_UH = 5000


class SyringePump(Driver):
    """One New Era NE-500/501 pump on a serial line, addressed by its configured pump number."""

    device_id = "new-era-syringe-pump"
    device_kind = "fluid.pump"
    mode = "hardware"
    #: A pump that dispenses liquid is at least R2 (MHS/spec/04-safety.md); the card's floor is R0.
    risk = "R2"
    native = "pump_control:PumpControl"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakePumpLink"}
    vendor, model = "New Era Pump Systems", "NE-500/501 syringe pump"
    display_name = "New Era NE-500/501 syringe pump"
    tags = ["syringe pump", "new era", "ne-500", "ne-501", "serial", "fluid"]
    facts = [
        Fact("The project is a Python GUI that operates New Era syringe pumps such as the NE-500/501",
             source="vendor_doc", ref="README.md:2"),
        Fact("The upstream runs on Python 2 and requires PyQt4 and the serial module", source="vendor_doc",
             ref="README.md:6"),
        Fact("The GUI opens the serial port at 19200 baud with a 0.1-second timeout", source="upstream_code",
             ref=f"{PUMP_CONTROL}:22"),
        Fact("Pump discovery writes the CR-terminated query '<address>ADR' and accepts a non-empty reply",
             source="upstream_code", ref=f"{NEW_ERA}:7-10"),
        Fact("The broadcast stop is the CR-terminated command '*STP'", source="upstream_code",
             ref=f"{NEW_ERA}:20"),
        Fact("A rate is set by a per-pump '<address>DIR<INF|WDR>' line followed by one '<address>RAT<value><UH|MH>' "
             "line; several pump rates are chained with '*' and the line ends with CR", source="upstream_code",
             ref=f"{NEW_ERA}:42-53"),
        Fact("Rates below 5000 are sent in UH; at 5000 and above the rate is divided by 1000 and sent in MH",
             source="upstream_code", ref=f"{NEW_ERA}:48-52"),
        Fact("A rate is read by '<address>DIR' and '<address>RAT'; a WDR direction gives a negative sign and an MH "
             "reply is multiplied by 1000 to obtain UH", source="upstream_code", ref=f"{NEW_ERA}:60-74"),
        Fact("The syringe diameter is written by '<address>DIA<millimetres>' and read by '<address>DIA'",
             source="upstream_code", ref=f"{NEW_ERA}:81-94"),
        Fact("Prime sends '<address>DIRINF', '<address>RAT10.0MH' and '<address>RUN', each CR-terminated",
             source="upstream_code", ref=f"{NEW_ERA}:98-112"),
        Fact("The GUI shows the current flow rate with the unit 'ul/hr'", source="upstream_code",
             ref=f"{PUMP_CONTROL}:131"),
        Fact("The clone lists no maximum or minimum rate, diameter, volume or duration; set_rates only switches "
             "the unit at 5000 UH", source="upstream_code", ref=f"{NEW_ERA}:48-52"),
    ]
    safe_state = "all pumps stopped by the broadcast *STP command"
    #: R2 hardware: the safe-state action below is an independent stop, so no separate hardware e-stop is claimed.
    estop_latency_ms = 200

    # -- serial helpers -----------------------------------------------------------------------------------------
    def _address(self) -> int:
        raw = self.options.get("address", 0)
        try:
            return int(raw)
        except (TypeError, ValueError) as exc:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               f"the pump address option must be an integer, got {raw!r}") from exc

    def _exchange(self, command: str) -> str:
        """Write one CR-terminated line and return the reply without its CR/LF."""
        self.native.write((command + "\r").encode("ascii"))
        raw = self.native.readline()
        if not raw:
            raise DriverFailed("MHS.DEVICE.NOT_READY", f"the pump did not answer {command!r}",
                               native_code="timeout")
        reply = raw.decode("ascii", "replace") if isinstance(raw, (bytes, bytearray)) else str(raw)
        reply = reply.strip("\r\n")
        if "?" in reply:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"the pump rejected {command!r}: {reply}",
                               native_code=reply)
        return reply

    def _write_only(self, command: str) -> None:
        """Send a stop without waiting for a reply (the e-stop and the safe-state action)."""
        self.native.write((command + "\r").encode("ascii"))

    @staticmethod
    def _direction_of(reply: str) -> str:
        return "reverse" if len(reply) >= 7 and reply[4:7] == "WDR" else "forward"

    @staticmethod
    def _rate_line(address: int, rate_uh: float) -> str:
        """The upstream rate line: UH below 5000, otherwise MH at one thousandth, five characters as in the clone."""
        if rate_uh < RATE_UNIT_SPLIT_UH:
            return f"{address}RAT{str(rate_uh)[:5]}UH"
        return f"{address}RAT{str(rate_uh / 1000.0)[:5]}MH"

    def _read_rate(self) -> float:
        direction = self._direction_of(self._exchange(f"{self._address()}DIR"))
        reply = self._exchange(f"{self._address()}RAT")
        units = reply[-2:]
        try:
            value = float(reply[4:-3].strip())
        except ValueError as exc:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"cannot parse the rate reply {reply!r}") from exc
        if units == "MH":
            value *= 1000.0
        elif units != "UH":
            raise DriverFailed("MHS.DEVICE.FAULTED", f"unknown rate unit in reply {reply!r}")
        return -value if direction == "reverse" else value

    # -- reads --------------------------------------------------------------------------------------------------
    @read("flow_rate", unit="uL/hr", description="Current flow rate; negative means withdraw (WDR)")
    def flow_rate(self):
        return self._read_rate()

    @read("direction", type="string", description="Direction of the current flow: forward (INF) or reverse (WDR)")
    def direction(self):
        return self._direction_of(self._exchange(f"{self._address()}DIR"))

    @read("diameter", unit="mm", description="Syringe diameter the pump uses for volume conversion")
    def diameter(self):
        reply = self._exchange(f"{self._address()}DIA")
        try:
            return float(reply[4:].strip())
        except ValueError as exc:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"cannot parse the diameter reply {reply!r}") from exc

    # -- writes -------------------------------------------------------------------------------------------------
    @write("flow_rate", unit="uL/hr", description="Set the flow rate; a negative value selects the WDR direction",
           limit=Limit.operator_required(
               "no text file of the clone states a flow-rate range; set_rates only switches from UH to MH at 5000, "
               "so the site sets the range of its syringe and tubing"))
    def set_flow_rate(self, value):
        address = self._address()
        self._exchange(f"{address}DIR{'WDR' if value < 0 else 'INF'}")
        self._exchange(self._rate_line(address, abs(float(value))))

    @write("diameter", unit="mm", description="Syringe diameter in millimetres",
           limit=Limit.operator_required(
               "the clone lists syringe diameters only as GUI menu choices (pump_control.py:8-11) and states no "
               "allowed range; the site sets the range of its syringe"))
    def set_diameter(self, value):
        self._exchange(f"{self._address()}DIA{value}")

    # -- actions ------------------------------------------------------------------------------------------------
    @action(cap="cap.actuation.pump.v1", long_running=True, cancellable=True,
            description="Run the pump at a flow rate for a volume or duration and stop it",
            input={
                "flow_rate": Field("number", unit="uL/s", description="Flow rate of the pump",
                                   limit=Limit.operator_required(
                                       "no text file of the clone states a flow-rate range; the site sets the "
                                       "range of its syringe and tubing")),
                "direction": Field("string", enum=["forward", "reverse"],
                                   description="Pump forward (INF) or reverse (WDR)"),
                "volume": Field("number", unit="uL",
                                description="Volume to move; used when duration_s is absent",
                                limit=Limit.operator_required(
                                    "the clone has no volumetric run; the site sets the usable volume")),
                "duration_s": Field("number", unit="s",
                                    description="Run time; when present it takes precedence over volume",
                                    limit=Limit.operator_required(
                                        "the clone has no timed run; the site sets a maximum run time")),
            },
            )
    def dispense(self, flow_rate, direction, volume=None, duration_s=None):
        if flow_rate <= 0:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET", "flow_rate must be greater than zero")
        if duration_s is None:
            if volume is None:
                raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                                   "give duration_s or volume; this pump has no timed or volumetric run of its own")
            duration_s = float(volume) / float(flow_rate)
        duration_s = float(duration_s)
        moved = float(flow_rate) * duration_s
        rate_uh = abs(float(flow_rate)) * 3600.0
        address = self._address()
        self.check_cancelled()
        self._exchange(f"{address}DIR{'INF' if direction == 'forward' else 'WDR'}")
        self._exchange(self._rate_line(address, rate_uh))
        self._exchange(f"{address}RUN")
        try:
            if self.is_hardware:
                remaining = duration_s
                while remaining > 0.0:
                    self.check_cancelled()
                    step = min(0.05, remaining)
                    time.sleep(step)
                    remaining -= step
        finally:
            # A cancelled dispense still stops the pump; this stop must not be skipped by the cancellation.
            self._write_only(f"{address}STP")
        return {"dispensed_volume": moved, "duration_s": duration_s}

    @action(name="x-cap.romerolab.prime_pump.v1",
            description="Prime the pump: INF direction, 10.0 MH, run (the upstream prime sequence)",
            output={"priming": Field("boolean", description="True once the prime commands were sent")})
    def prime(self):
        address = self._address()
        self.check_cancelled()
        self._exchange(f"{address}DIRINF")
        self._exchange(f"{address}RAT10.0MH")
        self._exchange(f"{address}RUN")
        return {"priming": True}

    @action(name="x-cap.romerolab.stop_pump.v1", safe_state=True,
            description="Stop all pumps with the broadcast *STP command; takes no input",
            output={"stopped": Field("boolean", description="True once *STP was sent")})
    def stop_all(self):
        self._write_only("*STP")
        return {"stopped": True}

    # -- safety -------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The broadcast stop: written without a reply, so it never waits for a running transaction."""
        self._write_only("*STP")

    def teardown(self):
        self.native.close()
