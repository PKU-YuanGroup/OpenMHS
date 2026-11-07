"""OpenMHS driver for gh.nsls-ii-chx/syringe_pump_controller: a multi-pump syringe controller over serial.

The upstream clone is one Python 2 module (``pump_controler.py:48`` is a ``print`` statement) with one device
class, ``pump`` (``pump_controler.py:10``), which opens a pyserial port in its constructor
(``pump_controler.py:11-12``) and writes CR-terminated text commands.  It is a Python 2 program, so this package
does not import or install it; ``native.py`` is an independent Python 3 port of the same wire protocol and
``native`` names the upstream class for provenance.

The card proposes a ``SerialDriver`` (family ``serial``).  A command table cannot reproduce these lines: every
command is built from the pump address and a keyword (``<address>DIR<INF|WDR>``, ``<address>RAT<rate><unit>``,
``<address>VOL <volume>``), so adding a space to make the token visible to G7 would change the wire syntax
(driver-authoring.md, "Choosing the shape").  This is a direct ``Driver`` over the upstream class, and the
deviation from the card is recorded in ``RESULT.json``.

* reads: flow rate (``<address>RAT``, sign from ``<address>DIR``), direction, dispense volume and the forward
  dispensed volume;
* writes: flow rate (``<address>DIR`` + ``<address>RAT``) and dispense volume (``<address>VOL <volume>``);
* action: the catalogue pump class runs the pump at a flow rate for a volume or duration and stops it;
* stop: the safe-state action and the e-stop write the CR-terminated ``STP`` command, which the clone sends
  without waiting for a reply (``pump_controler.py:163-169``).

Every Fact and Limit cites a line of the clone at the pinned commit
``cbda9ca1c20127a220eb91a61b6420a366ae5cf8``.  No text file of the clone states a flow-rate, volume or duration
range, so every numeric write and action input is ``Limit.operator_required`` and is refused until the site
supplies the bound in ``site-limits.json``.  The device dispenses liquid, so it is at least R2
(MHS/spec/04-safety.md); no text file documents an independent hardware e-stop, so the independent stop is the
``safe_state=True`` action below and the e-stop.
"""

import re
import time

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

PUMP = "pump_controler.py"


class SyringePumpController(Driver):
    """One pump address on the CHX syringe-pump controller, addressed as configured on its panel."""

    device_id = "nsls-ii-chx-syringe-pump"
    device_kind = "fluid.pump"
    mode = "hardware"
    #: A pump that dispenses liquid is at least R2 (MHS/spec/04-safety.md); the card's floor is R0.
    risk = "R2"
    native = "pump_controler:pump"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakePump"}
    vendor, model = "NSLS-II CHX", "syringe pump controller"
    display_name = "NSLS-II CHX syringe pump controller"
    tags = ["syringe pump", "serial", "nsls-ii", "chx", "fluid"]
    facts = [
        Fact("The project is a Python program that controls a syringe pump system developed at CHX",
             source="vendor_doc", ref="README.md:2"),
        Fact("The controller is one class, pump, which opens the serial port in its constructor",
             source="upstream_code", ref=f"{PUMP}:10-12"),
        Fact("The constructor defaults to port COM10, 19200 baud and a one-second timeout",
             source="upstream_code", ref=f"{PUMP}:11"),
        Fact("A command is the text plus a carriage return (0x0D) written to the serial port",
             source="upstream_code", ref=f"{PUMP}:14-16"),
        Fact("Pump discovery writes '<address>ADR' for each address in range(tot_range) and keeps the addresses "
             "that answer", source="upstream_code", ref=f"{PUMP}:18-27"),
        Fact("The direction query is '<address>DIR'; a WDR reply means withdraw",
             source="upstream_code", ref=f"{PUMP}:29-37"),
        Fact("set_direction writes '<address>DIR<INF|WDR>', where INF is in and WDR is withdraw",
             source="upstream_code", ref=f"{PUMP}:39-48"),
        Fact("set_rate first writes '<address>DIR<INF|WDR>', chosen by the sign of the flow rate",
             source="upstream_code", ref=f"{PUMP}:50-58"),
        Fact("set_rate then writes '<address>RAT<the first five characters of the absolute rate><unit>' and its "
             "default unit token is UM*", source="upstream_code", ref=f"{PUMP}:50-61"),
        Fact("set_diameter writes '<address>DIA<diameter>' and get_diameter writes '<address>DIA' and returns "
             "reply[4:-1]; the clone states no unit for this value",
             source="upstream_code", ref=f"{PUMP}:66-81"),
        Fact("set_volume writes '<address>VOL <volume>' with a space after VOL and ignores its unit argument",
             source="upstream_code", ref=f"{PUMP}:83-91"),
        Fact("get_volume writes '<address>VOL', parses the value from reply[4:-3] and the unit from reply[-3:-1]",
             source="upstream_code", ref=f"{PUMP}:94-103"),
        Fact("get_dispense writes '<address>DIS' and parses the INF value from reply[5:10], the WDR value from "
             "reply[11:16] and the unit from reply[-3:-1]", source="upstream_code", ref=f"{PUMP}:105-117"),
        Fact("reset_dispense writes '<address>CLD <direction>' with a space after CLD",
             source="upstream_code", ref=f"{PUMP}:120-125"),
        Fact("get_rate queries '<address>DIR' and '<address>RAT'; a WDR direction gives a negative sign and a UM "
             "reply unit is labelled ul/min", source="upstream_code", ref=f"{PUMP}:128-151"),
        Fact("run sends 'RUN' with an optional string pump prefix; its docstring says the pump is '00' or '01', "
             "set by setup on the controller panel", source="upstream_code", ref=f"{PUMP}:155-161"),
        Fact("stop sends 'STP' with an optional string pump prefix; the same docstring applies",
             source="upstream_code", ref=f"{PUMP}:163-169"),
        Fact("The other per-pump commands format the pump number with %i (an integer, no zero padding)",
             source="upstream_code", ref=f"{PUMP}:31"),
        Fact("The module opens COM10 at import time through the module-level variable s",
             source="upstream_code", ref=f"{PUMP}:177"),
        Fact("Line 48 is a Python 2 print statement, so the module does not import under Python 3",
             source="upstream_code", ref=f"{PUMP}:48"),
    ]
    safe_state = "every pump stopped by the CR-terminated STP command"

    def _address_int(self) -> int:
        """The pump address for the commands that format it with ``%i`` (the upstream's integer methods)."""
        raw = self.options.get("address", "00")
        try:
            return int(str(raw))
        except (TypeError, ValueError) as exc:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               f"the pump address option must be an integer, got {raw!r}") from exc

    def _address_text(self) -> str:
        """The pump address for ``run``/``stop``, which concatenate a string prefix (the panel's '00' or '01')."""
        return str(self.options.get("address", "00"))

    # -- serial helpers -----------------------------------------------------------------------------------------
    def _read_rate_umin(self) -> float:
        """The rate from the clone's ``get_rate``, converted to uL/min; WDR is negative."""
        text = str(self.native.get_rate(pump=self._address_int())).strip()
        match = re.search(r"([+-]?\d+(?:\.\d+)?)\s*(ul/min|ul/hour|ml/hour)?", text)
        if match is None:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"cannot parse the rate reply {text!r}")
        value = float(match.group(1))
        unit = match.group(2)
        if unit == "ul/min":
            return value
        if unit == "ul/hour":
            return value / 60.0
        raise DriverFailed(
            "MHS.DEVICE.PRECONDITION_UNMET",
            f"the pump reports {text!r}; this driver converts only uL/min and uL/hour and does not guess the "
            "clone's MH/NH labels (pump_controler.py:141-150)",
        )

    def _read_direction(self) -> str:
        sign = self.native.get_direction(pump=self._address_int())
        if sign == "+":
            return "forward"
        if sign == "-":
            return "reverse"
        raise DriverFailed("MHS.DEVICE.FAULTED", f"the pump returned an unknown direction sign {sign!r}")

    def _read_volume(self) -> float:
        value, unit = self.native.get_volume(pump=self._address_int())
        if unit != "UL":
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               f"the pump reports the volume unit {unit!r}; this driver exposes uL only")
        return float(value)

    def _read_dispensed(self) -> float:
        value, unit = self.native.get_dispense(direction="INF", pump=self._address_int())
        if unit != "UL":
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               f"the pump reports the dispense unit {unit!r}; this driver exposes uL only")
        return float(value)

    # -- reads --------------------------------------------------------------------------------------------------
    @read("flow_rate", unit="uL/min", description="Current flow rate (RAT); negative means withdraw (WDR)")
    def flow_rate(self):
        return self._read_rate_umin()

    @read("direction", type="string", description="Direction of the current flow: forward (INF) or reverse (WDR)")
    def direction(self):
        return self._read_direction()

    @read("volume", unit="uL", description="Dispense volume the pump is set to (VOL)")
    def volume(self):
        return self._read_volume()

    @read("dispensed_volume", unit="uL", description="Forward (INF) volume dispensed since the last CLD")
    def dispensed_volume(self):
        return self._read_dispensed()

    # -- writes -------------------------------------------------------------------------------------------------
    @write("flow_rate", unit="uL/min", description="Set the flow rate; a negative value selects withdraw (WDR)",
           limit=Limit.operator_required(
               "no text file of the clone states a flow-rate range; set_rate writes the rate with the UM* unit and "
               "the site sets the range of its syringe and tubing"))
    def set_flow_rate(self, value):
        self.native.set_rate(float(value), pump=self._address_int())

    @write("volume", unit="uL", description="Set the dispense volume (VOL)",
           limit=Limit.operator_required(
               "no text file of the clone states a usable volume range; set_volume writes the value and the site "
               "sets the range of its syringe"))
    def set_volume(self, value):
        self.native.set_volume(float(value), pump=self._address_int())

    # -- actions ------------------------------------------------------------------------------------------------
    @action(cap="cap.actuation.pump.v1", long_running=True, cancellable=True,
            description="Run one pump at a flow rate for a volume or duration and stop it",
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
            })
    def dispense(self, flow_rate, direction, volume=None, duration_s=None):
        rate = float(flow_rate)
        if rate < 0.0:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET", "flow_rate must not be negative")
        if duration_s is None:
            if volume is None:
                raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                                   "give duration_s or volume; this pump has no timed or volumetric run of its own")
            if rate == 0.0:
                raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                                   "cannot derive a duration from volume at a zero flow rate")
            duration = float(volume) / rate
            moved = float(volume)
        else:
            duration = float(duration_s)
            moved = rate * duration
        if duration < 0.0:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET", "duration_s must not be negative")
        address = self._address_int()
        self.check_cancelled()
        if rate == 0.0:
            self.native.set_rate(0.0, pump=address)
            self.native.stop(pump=self._address_text())
            return {"dispensed_volume": 0.0, "duration_s": duration}
        # The action input is uL/s (the catalogue unit); the clone's RAT command is the state's uL/min.
        signed_rate = (-rate if direction == "reverse" else rate) * 60.0
        try:
            self.native.set_rate(signed_rate, pump=address)
            self.native.set_volume(moved, pump=address)
            self.native.reset_dispense(direction="INF" if direction == "forward" else "WDR", pump=address)
            self.native.run(pump=self._address_text())
            if self.is_hardware:
                remaining = duration
                while remaining > 0.0:
                    self.check_cancelled()
                    step = min(0.05, remaining)
                    time.sleep(step)
                    remaining -= step
        finally:
            # A cancelled dispense still stops this pump; the stop must not be skipped by cancellation.
            self.native.stop(pump=self._address_text())
        return {"dispensed_volume": moved, "duration_s": duration}

    @action(name="x-cap.nsls-ii-chx.stop_pump.v1", safe_state=True,
            description="Stop every pump with the CR-terminated STP command; takes no input",
            output={"stopped": Field("boolean", description="True once STP was sent")})
    def stop_pump(self):
        self.native.stop()
        return {"stopped": True}

    # -- safety -------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The broadcast stop: written without a reply, so it never waits for a running transaction."""
        self.native.stop()
