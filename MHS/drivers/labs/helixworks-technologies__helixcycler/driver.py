"""OpenMHS driver for gh.helixworks-technologies/helixcycler: the HelixCycler OT thermocycler.

A direct Driver over the card's entry class ``tc_send_code:HardwareController`` (tc_send_code.py:6), the serial
controller that the HelixCycler and HelixShaker windows use.  The class builds each M-code command from parts -- a
command letter plus an `` S`` target, an optional `` H`` hold time and an optional `` V`` well volume
(tc_send_code.py:139-146) -- and frames it with CRLF on both sides (tc_send_code.py:63-64), so the card's
``PythonObjectDriver`` cannot carry the wire syntax; this package is a direct Driver, a deviation recorded in
RESULT.json notes.

* reads: the lid sensor temperature, the plate sensor temperature, and the plate reply's hold-time field;
* writes: the lid target (37 to 105 Cel), the plate target (4 to 99 Cel) and the shake speed.  The two temperature
  ranges are the target ranges the clone's README states (README.md:97-98).  No text file of the clone states a shake
  speed range, so the shake write is ``Limit.operator_required`` and is refused ``MHS.SAFETY.LIMITS_UNSET`` until the
  site supplies the range of its unit (``site-limits.example.json`` shows the overlay);
* the catalogue class cap.thermal.setpoint.v1 sets the plate target and reports the setpoint; the x-cap actions open
  and close the lid;
* the safe state and the e-stop both run the native ``deactivate_shaker`` (G28 and M106) and ``deactivate_all``
  (M18): the first command stops the shaker and deactivates heating (tc_send_code.py:148-150), the second turns off
  heating and cooling for the plate and the lid (README.md:99).  The clone documents no independent hardware e-stop,
  so ``estop_physical_ref`` is not set and the safe-state action satisfies SAFE-045 for this R2 hardware driver.

Every Fact cites a line of the clone at the pinned commit 29bcd934a8d5289021fb774de17ecdf578ff92f7.  This package is
model-authored and unreviewed: the hardware backend has never run, and the loader refuses it until a human signs
``reviewed_by`` in driver.lock.json (the loader does this at R2 and R3).
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write

_SHAKE_REASON = (
    "no text file of the clone states a shake speed range: the README documents the shaker control but gives no "
    "minimum or maximum RPM, and the controller sends M3 S<target> without a readback (tc_send_code.py:152-153). "
    "The site supplies the range of its unit"
)


class HelixCycler(Driver):
    device_id = "helixcycler"
    device_kind = "lab.thermal_block"
    mode = "hardware"
    risk = "R2"
    native = "tc_send_code:HardwareController"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeHardwareController"}
    vendor, model = "HelixWorks Technologies", "HelixCycler OT thermocycler"
    display_name = "HelixCycler OT thermocycler (tc_send_code.HardwareController)"
    tags = ["thermocycler", "pcr", "thermal block", "serial", "heater", "shaker"]
    facts = [
        Fact("HardwareController is the low-level serial communication class for the Opentrons hardware",
             source="upstream_code", ref="tc_send_code.py:6-9"),
        Fact("The lid set command is M140 and the plate set command is M104",
             source="upstream_code", ref="tc_send_code.py:14-17"),
        Fact("The lid read command is M141 and the plate read command is M105",
             source="upstream_code", ref="tc_send_code.py:15-18"),
        Fact("deactivate_all is M18 and the shake set command is M3",
             source="upstream_code", ref="tc_send_code.py:20-22"),
        Fact("open_lid is M126 and close_lid is M127",
             source="upstream_code", ref="tc_send_code.py:11-12"),
        Fact("Each command is framed by CRLF on both sides",
             source="upstream_code", ref="tc_send_code.py:63-64"),
        Fact("The controller opens the serial port at 115200 baud with 2 s read and write timeouts",
             source="upstream_code", ref="tc_send_code.py:44"),
        Fact("get_lid_temperature sends the lid read command and parses the C: field after a T line",
             source="upstream_code", ref="tc_send_code.py:92-101"),
        Fact("get_plate_info sends the plate read command and parses the C: temperature and H: seconds from a T line",
             source="upstream_code", ref="tc_send_code.py:115-124"),
        Fact("get_plate_info returns the plate temperature and the seconds left as a two-element list",
             source="upstream_code", ref="tc_send_code.py:137"),
        Fact("set_lid_temperature appends S and the target to the lid set command",
             source="upstream_code", ref="tc_send_code.py:139-140"),
        Fact("set_plate_temperature appends S target and optional H duration and V well volume to the plate set "
             "command", source="upstream_code", ref="tc_send_code.py:142-146"),
        Fact("set_shake_speed appends S and the target to the shake command",
             source="upstream_code", ref="tc_send_code.py:152-153"),
        Fact("deactivate_all sends the deactivate-all command",
             source="upstream_code", ref="tc_send_code.py:161-162"),
        Fact("deactivate_shaker sends the deactivate-shake and deactivate-heating commands",
             source="upstream_code", ref="tc_send_code.py:148-150"),
        Fact("The controller returns False instead of raising when the serial port cannot be opened",
             source="upstream_code", ref="tc_send_code.py:43-49"),
        Fact("The GUI emergency stop calls deactivate_all",
             source="upstream_code", ref="helixcycler.py:466-471"),
        Fact("The HelixShaker deactivate-all button calls deactivate_shaker",
             source="upstream_code", ref="helixshaker.py:130-131"),
        Fact("The lid target temperature entry accepts 37 to 105 Cel",
             source="vendor_doc", ref="README.md:97"),
        Fact("The plate target temperature entry accepts 4 to 99 Cel",
             source="vendor_doc", ref="README.md:98"),
        Fact("The lid heats passively and cools ambiently; it has no active cooling",
             source="vendor_doc", ref="README.md:97"),
        Fact("Deactivate all stops heating and cooling for both the lid and the plate",
             source="vendor_doc", ref="README.md:99"),
        Fact("The actual lid and plate temperatures are updated automatically every few seconds while idle",
             source="vendor_doc", ref="README.md:101"),
        Fact("A STEP hold time is in seconds and a blank hold time means an infinite hold",
             source="vendor_doc", ref="README.md:145"),
    ]
    safe_state = ("the shaker stopped and all heating and cooling off for the plate and the lid "
                  "(the native deactivate_shaker, G28 and M106, then deactivate_all, M18)")

    # -- reads -------------------------------------------------------------------------------------------------
    @read("lid_temperature", unit="Cel", description="Temperature the lid sensor reports")
    def lid_temperature(self):
        return self.native.get_lid_temperature()

    @read("plate_temperature", unit="Cel", description="Temperature the plate (sample block) sensor reports")
    def plate_temperature(self):
        return self.native.get_plate_info()[0]

    @read("plate_hold_remaining", type="string",
          description="Hold time remaining as the device reports it in the H: field of the plate reply; the "
                      "controller passes the device text through without converting it")
    def plate_hold_remaining(self):
        return self.native.get_plate_info()[1]

    # -- writes ------------------------------------------------------------------------------------------------
    @write("lid_setpoint", unit="Cel",
           description="Lid target temperature, sent as M140 S<value>; the lid heats passively and cools ambiently",
           limit=Limit(min=37, max=105, source="vendor_doc", ref="README.md:97"))
    def set_lid_setpoint(self, value):
        self.native.set_lid_temperature(value)
        return value

    @write("plate_setpoint", unit="Cel",
           description="Plate (sample block) target temperature, sent as M104 S<value> with no hold time",
           limit=Limit(min=4, max=99, source="vendor_doc", ref="README.md:98"))
    def set_plate_setpoint(self, value):
        self.native.set_plate_temperature(value)
        return value

    @write("shake_speed", unit="/min",
           description="Shake speed, sent as M3 S<value>; the controller has no shake readback, so the state "
                       "reports the last value written",
           limit=Limit.operator_required(_SHAKE_REASON))
    def set_shake_speed(self, value):
        self.native.set_shake_speed(value)
        return value

    # -- catalogue action --------------------------------------------------------------------------------------
    @action(cap="cap.thermal.setpoint.v1",
            description="Set the plate (sample block) target temperature and report the setpoint",
            input={"target_temperature": Field(
                "number", unit="Cel",
                description="Plate target temperature",
                limit=Limit(min=4, max=99, source="vendor_doc", ref="README.md:98"))})
    def set_plate_target(self, target_temperature):
        self.native.set_plate_temperature(target_temperature)
        self.check_cancelled()
        return {"setpoint": target_temperature}

    # -- lid actions -------------------------------------------------------------------------------------------
    @action(name="x-cap.helixworks-technologies.open_lid.v1",
            description="Open the lid (the native M126 command)",
            output={"opened": Field("boolean",
                                    description="True once the native open-lid command was sent")})
    def open_lid(self):
        self.native.open_lid()
        self.check_cancelled()
        return {"opened": True}

    @action(name="x-cap.helixworks-technologies.close_lid.v1",
            description="Close the lid (the native M127 command)",
            output={"closed": Field("boolean",
                                    description="True once the native close-lid command was sent")})
    def close_lid(self):
        self.native.close_lid()
        self.check_cancelled()
        return {"closed": True}

    # -- safety ------------------------------------------------------------------------------------------------
    @action(name="x-cap.helixworks-technologies.deactivate_all.v1", safe_state=True,
            description="Stop the shaker and turn off heating and cooling for the plate and the lid (the native "
                        "deactivate_shaker, G28 and M106, then deactivate_all, M18); it takes no input",
            output={"deactivated": Field("boolean",
                                         description="True once both native deactivate commands were sent")})
    def deactivate_all(self):
        self.native.deactivate_shaker()
        self.native.deactivate_all()
        return {"deactivated": True}

    @estop
    def stop(self):
        """The native safe state: stop the shaker, then send the deactivate-all command."""
        self.native.deactivate_shaker()
        self.native.deactivate_all()

    # -- lifecycle ---------------------------------------------------------------------------------------------
    def teardown(self):
        self.native.disconnect()
