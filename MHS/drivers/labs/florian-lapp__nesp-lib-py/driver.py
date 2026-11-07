"""OpenMHS driver for gh.florian-lapp/nesp-lib-py: a New Era syringe pump over its serial protocol.

A direct Driver (decorated methods) over the upstream class nesp_lib.pump:Pump (nesp_lib/pump.py:14), the high level
interface to the New Era syringe pumps (README.md:3-7), which are also sold as Aladdin by World Precision Instruments
and LA by Landgraf Laborsysteme.  The class talks to the pump over a nesp_lib.port:Port, a pyserial connection
(nesp_lib/port.py:6-35), and is constructed from that port as the README shows (README.md:62-65);
``native.py`` opens the port and the pump.

DEVIATION FROM THE CARD: the card is family-config with the SerialDriver helper (reason family:serial).  A command
table cannot express this pump.  A request is assembled from parts, the address and the command name plus formatted
arguments (``str(address) + name.value + arguments``, nesp_lib/pump.py:490-493), and in safe mode it is a binary frame
with a start byte, a length byte, a CCITT CRC and an end byte (nesp_lib/pump.py:527-543); replies are frames in both
modes (nesp_lib/pump.py:545-576).  So this package is a direct Driver over the upstream class, with a native.py
factory, as "Choosing the shape" of the authoring guide prescribes.

* reads: the model number and firmware version, the status (a Status name), whether the pump is running, the syringe
  diameter, the configured pumping direction, volume and rate, the infused and withdrawn volume counters and the safe
  mode timeout;
* writes: the syringe diameter (bounded by the class's own minimum and maximum, 0.1 to 80.0 mm), the pumping
  direction (INFUSE or WITHDRAW), the safe mode timeout (0 to 255 s) and the pumping volume and rate.  The volume and
  rate bounds depend on the syringe fitted -- the pump's rate limits are dictated by the syringe diameter
  (nesp_lib/pump.py:255) and the class setter only states a protocol envelope with an open upper edge
  (nesp_lib/pump.py:226-227, 262-263) -- so those two are ``Limit.operator_required``: every call that sets them is
  refused MHS.SAFETY.LIMITS_UNSET until the site supplies the range of its syringe (site-limits.example.json shows the
  overlay an operator writes);
* actions: x-cap.florian-lapp.run_pump.v1 starts the pump with the configured direction, volume and rate
  (``Pump.run(False)``, non-blocking as the README shows, README.md:103-106), x-cap.florian-lapp.purge.v1 runs it at
  the maximum rate until it is stopped (``Pump.run_purge``), and x-cap.florian-lapp.stop_pump.v1 is the safe state;
* the native stop is ``Pump.stop(False)`` (STP without waiting, nesp_lib/pump.py:321-330), used by @estop and by the
  safe-state action.

There is no upstream simulator and no recording in the clone (the card's mock_strategy.preferred is transcript and it
has neither hints nor tests), so fake.py is an in-memory stand-in for the Pump object: the pump's serial protocol is
not replayed and the wire frames are not produced by this package.

Every Fact cites a line of the clone at the pinned commit (c16abc82c9feb7c356f06c30b0dff0d4d421cfe3).  This package is
model-authored and unreviewed: it is checked on the fake backend only, and nothing here ran on a pump.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

#: The upstream module of the native class, relative to the clone root.
PUMP = "nesp_lib/pump.py"

#: Why the pumping volume needs the site's range (see site-limits.example.json).
VOLUME_REASON = (
    "the volume a pump can move is set by the syringe fitted: the class setter only states a protocol envelope of "
    "0.001/1000.0 mL to 10_000.0 mL with an open upper edge (nesp_lib/pump.py:226-227), not a bound of the device; the "
    "site states the volumes its syringe allows")
#: Why the pumping rate needs the site's range (see site-limits.example.json).
RATE_REASON = (
    "the pumping rate limits are dictated by the syringe diameter fitted (nesp_lib/pump.py:255) and the class setter "
    "only states a protocol envelope of 0.001/60_000.0 mL/min to 10_000.0 mL/min (nesp_lib/pump.py:262-263); the site "
    "states the rates its syringe allows")


class NespPump(Driver):
    device_id = "nesp-pump"
    device_kind = "fluid.pump"
    mode = "hardware"
    #: R2, above the card's floor: a pump that dispenses liquid is R2, like the tecancavro pump (MHS/spec/04-safety.md).  The model review raised it; the hardware backend
    #: of this model-written package stays refused until a human signs reviewed_by.
    risk = "R2"
    native = "nesp_lib.pump:Pump"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeNespPump"}
    vendor, model = "New Era Pump Systems", "syringe pump (NESP-Lib)"
    display_name = "New Era syringe pump (nesp-lib Pump)"
    tags = ["syringe-pump", "fluid", "infuse", "withdraw", "serial"]
    facts = [
        Fact("Pump is the high level interface to the New Era syringe pumps, also sold as Aladdin by World "
             "Precision Instruments and LA by Landgraf Laborsysteme", source="vendor_doc", ref="README.md:3-7"),
        Fact("A pump is constructed from a Port of the pyserial connection: pump = Pump(port)", source="vendor_doc",
             ref="README.md:62-65"),
        Fact("Port opens a pyserial serial port and BAUD_RATE_DEFAULT is 9_600", source="upstream_code",
             ref="nesp_lib/port.py:9-10"),
        Fact("Port.__init__ opens serial.Serial(port=name, baudrate=baud_rate)", source="upstream_code",
             ref="nesp_lib/port.py:30-35"),
        Fact("Pump.__init__ sets the safe mode timeout and reads the model number, firmware version and firmware "
             "upgrade from the pump on construction", source="upstream_code", ref=f"{PUMP}:71-79"),
        Fact("syringe_diameter_mm is in millimetres and its values are SYRINGE_DIAMETER_MINIMUM_MM (0.1 mm) to "
             "SYRINGE_DIAMETER_MAXIMUM_MM (80.0 mm)", source="upstream_code", ref=f"{PUMP}:30-33"),
        Fact("safe_mode_timeout_s is in seconds within SAFE_MODE_TIMEOUT_DISABLED (0 s) and "
             "SAFE_MODE_TIMEOUT_LIMIT_S (255 s)", source="upstream_code", ref=f"{PUMP}:25-28"),
        Fact("A safe mode timeout of zero sets the communication to basic mode and a non-zero value sets it to safe "
             "mode", source="upstream_code", ref=f"{PUMP}:130-133"),
        Fact("PumpingDirection has the members INFUSE and WITHDRAW; pumping_direction is set as one of them and a "
             "value the direction tables do not know raises ValueError", source="upstream_code",
             ref=f"{PUMP}:195-201"),
        Fact("The pumping volume setter refuses a value below 0.001/1000.0 mL and a value at or above 10_000.0 mL",
             source="upstream_code", ref=f"{PUMP}:226-227"),
        Fact("The pumping rate limits are dictated by the syringe diameter of the pump", source="upstream_code",
             ref=f"{PUMP}:255"),
        Fact("The pumping rate setter refuses a value below 0.001/60_000.0 mL/min and a value at or above "
             "10_000.0 mL/min", source="upstream_code", ref=f"{PUMP}:262-263"),
        Fact("pumping_volume_ml and pumping_rate_ml_per_min are read from a value and a unit the pump reports and "
             "converted to millilitres and millilitres per minute (VOL with ML/UL, RAT with MM/MH/UM/UH)",
             source="upstream_code", ref=f"{PUMP}:411-427"),
        Fact("volume_infused_ml and volume_withdrawn_ml read the dispensation counters of the pump, the DIS reply "
             '"I" <infused> "W" <withdrawn> <units>', source="upstream_code", ref=f"{PUMP}:280-300"),
        Fact("run(wait_while_running=True) sends RUN and waits while the pump is running; run(False) returns after "
             "starting it and wait_while_running polls the status every PUMPING_POLL_DELAY_S",
             source="upstream_code", ref=f"{PUMP}:302-335"),
        Fact("run_purge sends PUR: the pump runs at maximum rate in the configured direction until it is stopped",
             source="upstream_code", ref=f"{PUMP}:313-319"),
        Fact("stop(wait_while_running=True) sends STP and waits while the pump is running", source="upstream_code",
             ref=f"{PUMP}:321-330"),
        Fact("The status property reads the Status of the pump and running is true while the status is INFUSING, "
             "WITHDRAWING or PURGING", source="upstream_code", ref=f"{PUMP}:140-149"),
        Fact("Status has the members INFUSING, WITHDRAWING, PURGING, STOPPED, PAUSED, SLEEPING and WAITING",
             source="upstream_code", ref="nesp_lib/status.py:3-19"),
        Fact("The command names are an empty name for the status and SAF, VER, DIA, DIR, VOL, RAT, DIS, CLD, RUN, "
             "PUR and STP", source="upstream_code", ref=f"{PUMP}:342-354"),
        Fact("A request is the address, the command name and the formatted arguments, str(address) + name.value + "
             "arguments", source="upstream_code", ref=f"{PUMP}:490-493"),
        Fact("In safe mode a request is framed as STX, a length byte, the request bytes, the CCITT CRC "
             "(binascii.crc_hqx) and ETX; in basic mode it is the request text with a carriage return",
             source="upstream_code", ref=f"{PUMP}:527-543"),
        Fact("A reply is an STX ... ETX frame in basic mode and carries a length byte and a checksum in safe mode",
             source="upstream_code", ref=f"{PUMP}:545-576"),
        Fact("The reply begins with a two character address that must equal the pump's address", source="upstream_code",
             ref=f"{PUMP}:500-505"),
        Fact("The pump address defaults to ADDRESS_DEFAULT 0 and may not exceed ADDRESS_LIMIT 99", source="upstream_code",
             ref=f"{PUMP}:20-23"),
        Fact("The README prints model_number (1000 for NE-1000) and firmware_version ((3, 928) for 3.928)",
             source="vendor_doc", ref="README.md:82-87"),
    ]
    safe_state = "pump stopped (STP, Pump.stop without waiting): no pumping continues until a new run"

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("model_number", type="integer", unit="1", description="Model number the pump reports (1000 for NE-1000)")
    def model_number(self):
        return int(self.native.model_number)

    @read("firmware_version", type="string",
          description="Firmware version the pump reports as the major version and the minor version, major.minor")
    def firmware_version(self):
        major, minor = self.native.firmware_version
        return f"{int(major)}.{int(minor)}"

    @read("status", type="string",
          description="Status the pump reports: INFUSING, WITHDRAWING, PURGING, STOPPED, PAUSED, SLEEPING or WAITING")
    def status(self):
        return str(self.native.status.name)

    @read("running", type="boolean",
          description="True while the pump reports INFUSING, WITHDRAWING or PURGING")
    def running(self):
        return bool(self.native.running)

    @read("syringe_diameter_mm", unit="mm", description="Syringe diameter the pump is configured with")
    def syringe_diameter_mm(self):
        return float(self.native.syringe_diameter_mm)

    @read("pumping_direction", type="string",
          description="Configured pumping direction: INFUSE (towards the outlet) or WITHDRAW (into the syringe)")
    def pumping_direction(self):
        return str(self.native.pumping_direction.name)

    @read("pumping_volume_ml", unit="mL", description="Configured pumping volume")
    def pumping_volume_ml(self):
        return float(self.native.pumping_volume_ml)

    @read("pumping_rate_ml_per_min", unit="mL/min", description="Configured pumping rate")
    def pumping_rate_ml_per_min(self):
        return float(self.native.pumping_rate_ml_per_min)

    @read("volume_infused_ml", unit="mL",
          description="Volume the pump reports infused since its dispensation counter was last cleared")
    def volume_infused_ml(self):
        return float(self.native.volume_infused_ml)

    @read("volume_withdrawn_ml", unit="mL",
          description="Volume the pump reports withdrawn since its dispensation counter was last cleared")
    def volume_withdrawn_ml(self):
        return float(self.native.volume_withdrawn_ml)

    @read("safe_mode_timeout_s", type="integer", unit="s",
          description="Safe mode timeout of the communication: 0 is basic mode, a non-zero value is safe mode")
    def safe_mode_timeout_s(self):
        return int(self.native.safe_mode_timeout_s)

    # -- writes ---------------------------------------------------------------------------------------------------
    @write("syringe_diameter_mm", unit="mm",
           description="Syringe diameter to set; it dictates the minimum and maximum pumping rate of the pump",
           limit=Limit(min=0.1, max=80.0, source="upstream_code", ref=f"{PUMP}:30-33",
                       reason="SYRINGE_DIAMETER_MINIMUM_MM is 0.1 mm and SYRINGE_DIAMETER_MAXIMUM_MM is 80.0 mm"))
    def set_syringe_diameter_mm(self, value):
        self.native.syringe_diameter_mm = float(value)

    @write("pumping_direction", type="string", enum=["INFUSE", "WITHDRAW"],
           description="Pumping direction to set: INFUSE (towards the outlet) or WITHDRAW (into the syringe)")
    def set_pumping_direction(self, value):
        current = self.native.pumping_direction
        try:
            member = type(current)[str(value)]
        except (KeyError, TypeError):
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                               f"the pump has no pumping direction named {value!r}")
        self.native.pumping_direction = member

    @write("pumping_volume_ml", unit="mL", description="Pumping volume to set",
           limit=Limit.operator_required(VOLUME_REASON))
    def set_pumping_volume_ml(self, value):
        self.native.pumping_volume_ml = float(value)

    @write("pumping_rate_ml_per_min", unit="mL/min", description="Pumping rate to set",
           limit=Limit.operator_required(RATE_REASON))
    def set_pumping_rate_ml_per_min(self, value):
        self.native.pumping_rate_ml_per_min = float(value)

    @write("safe_mode_timeout_s", type="integer", unit="s",
           description="Safe mode timeout to set: 0 disables safe mode, a non-zero value enables it",
           limit=Limit(min=0, max=255, source="upstream_code", ref=f"{PUMP}:25-28",
                       reason="SAFE_MODE_TIMEOUT_DISABLED is 0 s and SAFE_MODE_TIMEOUT_LIMIT_S is 255 s"))
    def set_safe_mode_timeout_s(self, value):
        self.native.safe_mode_timeout_s = int(value)

    # -- actions --------------------------------------------------------------------------------------------------
    @action(name="x-cap.florian-lapp.run_pump.v1",
            description="Start the pump with the configured direction, volume and rate (Pump.run without waiting); "
                        "it returns after starting the pump, and the state reports whether it is running",
            output={"status": Field("string", description="Status the pump reports after the command"),
                    "running": Field("boolean", description="True while the pump reports that it is pumping")})
    def run_pump(self):
        self.native.run(False)
        return {"status": str(self.native.status.name), "running": bool(self.native.running)}

    @action(name="x-cap.florian-lapp.purge.v1",
            description="Run the pump at its maximum rate in the configured direction until it is stopped "
                        "(Pump.run_purge); it returns after starting the purge",
            output={"status": Field("string", description="Status the pump reports after the command"),
                    "running": Field("boolean", description="True while the pump reports that it is pumping")})
    def purge(self):
        self.native.run_purge()
        return {"status": str(self.native.status.name), "running": bool(self.native.running)}

    @action(name="x-cap.florian-lapp.stop_pump.v1", safe_state=True,
            description="Stop the pump without waiting for the run to end (Pump.stop without waiting); it takes no "
                        "input",
            output={"status": Field("string", description="Status the pump reports after the command"),
                    "running": Field("boolean", description="True while the pump reports that it is pumping")})
    def stop_pump(self):
        self.native.stop(False)
        return {"status": str(self.native.status.name), "running": bool(self.native.running)}

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop(native="stop")
    def stop(self):
        """The native stop: the runtime latches first, then sends STP without waiting for the pump."""
        self.native.stop(False)
