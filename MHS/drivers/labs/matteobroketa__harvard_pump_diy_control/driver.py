"""OpenMHS driver for gh.matteobroketa/harvard_pump_diy_control: a Harvard PHD 2000 syringe pump.

A direct Driver over the upstream class
``refactored_pump_control.harvard_phd2000_driver:HarvardPHD2000Driver``.  The upstream class owns the Model 44
state machine: it prefixes every command with the one- or two-digit Pump Chain address, reads a terminal addressed
prompt, and normalizes the prompt character to a pump state (``harvard_phd2000_driver.py:143-152``, ``44-50``,
``36-43``).  A family config cannot reproduce that address prefix and prompt framing, so this package uses the
upstream object directly (driver-authoring.md, "Choosing the shape") and a native factory.

* reads: the flow rate in uL/h (converted from the unit the pump reports), the direction, whether the pump is
  running, the normalized status, the syringe inside diameter and the Pump Chain address;
* writes: flow rate, direction and syringe diameter.  No text file of the clone states a numeric rate or diameter
  range, so both numeric writes are ``Limit.operator_required`` and every write is refused with
  ``MHS.SAFETY.LIMITS_UNSET`` until the site supplies the range of its syringe and pump head
  (``site-limits.example.json`` shows the overlay);
* actions: run, pause and resume, plus the safe-state stop; the native stop (addressed ``STP``) is the e-stop.

Every Fact cites a line of the clone at the pinned commit (d4a888432a81d69dad963fddb9df5adf3bc94633).  This package
is model-authored and unreviewed: it is checked on the fake backend only (driver.lock.json).
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

CLONE = "refactored_pump_control"


def _hourly_uL(rate, units):
    """Convert one of the four rate units the clone names (harvard_phd2000_driver.py:212-225) to uL/h."""
    token = str(units).strip().lower()
    token = token.replace("/hr", "/h").replace("/min", "/m").replace("/mn", "/m")
    factors = {"ul/h": 1.0, "ul/m": 60.0, "ml/h": 1000.0, "ml/m": 60000.0}
    try:
        return float(rate) * factors[token]
    except KeyError:
        raise DriverFailed("MHS.DEVICE.FAULTED",
                           f"the pump reported the unknown rate unit {units!r}") from None


class HarvardPHD2000(Driver):
    device_id = "harvard-phd2000"
    device_kind = "fluid.pump"
    mode = "hardware"
    risk = "R2"
    native = "refactored_pump_control.harvard_phd2000_driver:HarvardPHD2000Driver"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeHarvardPHD2000"}
    vendor, model = "Harvard Apparatus", "PHD 2000 syringe pump"
    display_name = "Harvard PHD 2000 syringe pump (Model 44)"
    tags = ["syringe pump", "harvard", "phd 2000", "serial", "infusion", "withdrawal"]
    facts = [
        Fact("A Model 44 command is the pump address followed by the upper-case command word and optional "
             "arguments", source="upstream_code", ref=f"{CLONE}/harvard_phd2000_driver.py:143-152"),
        Fact("A complete response ends in a line-framed one- or two-digit address and one state character",
             source="upstream_code", ref=f"{CLONE}/harvard_phd2000_driver.py:44-50"),
        Fact("The prompt state characters are ':' stopped, '>' infusing, '<' withdrawing, '/' paused, '*' stalled "
             "and '^' trigger wait", source="upstream_code",
             ref=f"{CLONE}/harvard_phd2000_driver.py:36-43"),
        Fact("The pump address is an integer from 0 to 99", source="upstream_code",
             ref=f"{CLONE}/harvard_phd2000_driver.py:63-71"),
        Fact("The rate unit tokens the clone sends are UH (uL/h), UM (uL/m), MH (mL/h) and MM (mL/m)",
             source="upstream_code", ref=f"{CLONE}/harvard_phd2000_driver.py:212-225"),
        Fact("set_rate sends RAT when infusing and RFR when withdrawing, with the numeric rate and the unit token",
             source="upstream_code", ref=f"{CLONE}/harvard_phd2000_driver.py:256-270"),
        Fact("get_rate queries RAT or RFR and returns the rate and unit parsed from the reply",
             source="upstream_code", ref=f"{CLONE}/harvard_phd2000_driver.py:275-285"),
        Fact("set_direction sends DIR INF for infuse and DIR REF for withdraw", source="upstream_code",
             ref=f"{CLONE}/harvard_phd2000_driver.py:287-299"),
        Fact("start sends RUN and verifies the infusing or withdrawing state", source="upstream_code",
             ref=f"{CLONE}/harvard_phd2000_driver.py:301-314"),
        Fact("stop sends STP through the emergency transport path and confirms the stopped state",
             source="upstream_code", ref=f"{CLONE}/harvard_phd2000_driver.py:316-330"),
        Fact("query_state sends only the address (the addressed prompt request) and returns the state",
             source="upstream_code", ref=f"{CLONE}/harvard_phd2000_driver.py:332-333"),
        Fact("request_prompt queries the state with the address alone and never with a bare carriage return",
             source="upstream_code", ref=f"{CLONE}/harvard_phd2000_driver.py:172-174"),
        Fact("identify sends an addressed prompt request, VER and a second addressed prompt request",
             source="upstream_code", ref=f"{CLONE}/harvard_phd2000_driver.py:176-205"),
        Fact("get_syringe_info reads the diameter with DIA", source="upstream_code",
             ref=f"{CLONE}/harvard_phd2000_driver.py:227-238"),
        Fact("set_diameter writes DIA with four decimals and restores the cached rates and direction around it",
             source="upstream_code", ref=f"{CLONE}/harvard_phd2000_driver.py:240-254"),
        Fact("The canonical directions are infuse and withdraw, with aliases accepted by Direction.coerce",
             source="upstream_code", ref=f"{CLONE}/pump_models.py:8-21"),
        Fact("The Model 44 prompt states are normalized as stopped, infusing, refilling, paused, stalled and "
             "trigger wait", source="vendor_doc", ref="README.md:101-106"),
        Fact("A bare carriage return is the Model 44 chain-wide STOP ALL command, and the transports reject an "
             "empty command", source="vendor_doc", ref="README.md:50-54"),
        Fact("State polling uses the addressed prompt request '<address><CR>'", source="vendor_doc",
             ref="README.md:56"),
        Fact("Normal and emergency application stops use '<address>STP<CR>' independently for each selected pump",
             source="vendor_doc", ref="README.md:59-60"),
        Fact("A zero flow physically stops the pump", source="vendor_doc", ref="README.md:113"),
        Fact("PHD 2000 exposes the diameter through DIA and does not provide syringe manufacturer or model data",
             source="vendor_doc", ref="README.md:124-128"),
        Fact("The recommended PHD 2000 serial framing is 9600 baud, 8 data bits, no parity and 2 stop bits",
             source="vendor_doc", ref="README.md:33-39"),
        Fact("SerialTransport uses a carriage return as its terminator", source="upstream_code",
             ref=f"{CLONE}/serial_transport.py:48-50"),
        Fact("SerialTransport refuses an empty command instead of transmitting a bare carriage return",
             source="upstream_code", ref=f"{CLONE}/serial_transport.py:134-141"),
        Fact("emergency_transaction cancels queued noncritical updates and sends the stop at queue head",
             source="upstream_code", ref=f"{CLONE}/serial_transport.py:152-155"),
    ]
    safe_state = "pump stopped by the addressed STP command, confirmed by the stopped prompt"

    # -- reads --------------------------------------------------------------------------------------------------
    @read("flow_rate", unit="uL/h",
          description="Flow rate of the current direction, converted to microlitres per hour")
    def flow_rate(self):
        rate, units = self.native.get_rate()
        return _hourly_uL(rate, units)

    @read("direction", type="string", description="Current pumping direction: infuse or withdraw")
    def direction(self):
        value = self.native.direction
        return getattr(value, "value", value)

    @read("running", type="boolean",
          description="True while the pump reports the infusing or withdrawing state")
    def running(self):
        return bool(self.native.query_state().is_running)

    @read("status", type="string",
          description="Normalized pump state: stopped, infusing, withdrawing, paused, stalled, trigger_wait or "
                      "target_reached")
    def status(self):
        return self.native.get_status()

    @read("syringe_diameter_mm", unit="mm",
          description="Syringe inside diameter reported by the pump through DIA")
    def syringe_diameter_mm(self):
        return float(self.native.get_syringe_info()["diameter_mm"])

    @read("address", type="integer", description="Pump Chain address of this pump (0 to 99)")
    def address(self):
        return int(self.native.address)

    # -- writes -------------------------------------------------------------------------------------------------
    @write("flow_rate", unit="uL/h",
           description="Flow rate of the current direction; it is sent as RAT or RFR with the UH unit token",
           limit=Limit.operator_required(
               "the pump's accepted rate range depends on the installed syringe, and no text file of the clone "
               "states a numeric rate range; the site supplies the range for its syringe and syringe driver"))
    def set_flow_rate(self, value):
        self.native.set_rate(float(value), "ul/h")

    @write("direction", type="string",
           description="Pumping direction: infuse sends DIR INF, withdraw sends DIR REF",
           limit=Limit(allowed=["infuse", "withdraw"], source="upstream_code",
                       ref=f"{CLONE}/pump_models.py:8-21",
                       reason="Direction.coerce accepts infuse and withdraw (plus aliases); the driver sends the "
                              "canonical values to set_direction"))
    def set_direction(self, value):
        self.native.set_direction(value)

    @write("syringe_diameter_mm", unit="mm",
           description="Syringe inside diameter, written explicitly to DIA; the pump restores its cached rates",
           limit=Limit.operator_required(
               "the clone states no numeric syringe diameter range and the diameter must match the installed "
               "syringe; the site supplies the range for its syringe"))
    def set_syringe_diameter_mm(self, value):
        self.native.set_diameter(float(value))

    # -- actions ------------------------------------------------------------------------------------------------
    @action(name="x-cap.matteobroketa.run_pump.v1", description="Start the pump in the configured direction (RUN)",
            output={"status": Field("string", description="Normalized pump state after RUN")})
    def run_pump(self):
        self.native.run()
        return {"status": self.native.get_status()}

    @action(name="x-cap.matteobroketa.pause_pump.v1",
            description="Stop the pump and keep the configured rate for a later resume (the upstream pause is the "
                        "native stop)",
            output={"status": Field("string", description="Normalized pump state after the pause")})
    def pause_pump(self):
        self.native.pause()
        return {"status": self.native.get_status()}

    @action(name="x-cap.matteobroketa.resume_pump.v1",
            description="Resume pumping in the configured direction after a pause (the upstream resume is the "
                        "native start)",
            output={"status": Field("string", description="Normalized pump state after the resume")})
    def resume_pump(self):
        self.native.resume()
        return {"status": self.native.get_status()}

    @action(name="x-cap.matteobroketa.stop_pump.v1", safe_state=True,
            description="Stop the pump with the addressed STP command (the native stop, the safe state); it takes "
                        "no input",
            output={"status": Field("string", description="Normalized pump state after the stop")})
    def stop_pump(self):
        self.native.stop()
        return {"status": self.native.get_status()}

    # -- safety -------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: the runtime latches first, then sends STP on the emergency transport path."""
        self.native.stop()

    def teardown(self):
        self.native.transport.disconnect()      # serial_transport.py:93-98
