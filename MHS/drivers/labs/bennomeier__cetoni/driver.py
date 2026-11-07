"""OpenMHS driver for gh.bennomeier/cetoni: a Cetoni Nemesys V4 syringe pump over its serial frame protocol.

This is a direct Driver over ``cetoniSerial:Syringe``, not a SerialDriver: the upstream builds framed binary commands
(opcode, node id, CANopen object index/subindex, word count, CRC and DLE byte stuffing) instead of text lines, so a
command table cannot express the wire syntax (driver-authoring.md, "Choosing the shape").  The card's
``decision=family-config`` and ``helper=SerialDriver`` are therefore a deviation.

* reads: current and target position, the velocity register, the flow rate derived from it, the state register and
  the last commanded valve position;
* writes: velocity, flow rate, target position and valve position;
* action: ``cap.actuation.pump.v1`` aspirates (direction reverse) or dispenses (direction forward) a volume at a flow
  rate, through the upstream ``aspirate``/``dispense`` methods;
* safety: the native stop writes control word 0x06 to 0x6040 (the shutdown state the constructor itself uses before
  enabling the drive); the safe-state action ``x-cap.bennomeier.stop_pump.v1`` writes the same word.

Bounds of a configured pump are read from the drive at connect (0x607D, 0x607F) or depend on the installed syringe,
which is a constructor option, so no text of the clone states a numeric bound: every numeric write and action input is
``Limit.operator_required`` and the site supplies its envelope (``site-limits.example.json`` shows one).  The valve
allowed set is the one the upstream methods encode.

Every Fact and Limit cites a line of the clone at the pinned commit (b957067d56c2698ca4b77bfe2b445af4b1d92045).  This
package is model-authored and unreviewed; it is checked on the fake backend only and nothing here ran a device.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

SOURCE = "cetoniSerial.py"

VELOCITY_REASON = (
    "the upper bound is the drive's maximum profile velocity, read from 0x607F at connect, and no text of the clone "
    "states a numeric velocity range; the site sets the permitted range of its unit")
FLOW_REASON = (
    "setFlowRate bounds the flow rate by maxVolperS, which is derived at connect from 0x607F and the syringe "
    "cross-section (a constructor option); no text states a numeric range, so the site sets it")
POSITION_REASON = (
    "the travel range is read from 0x607D at connect (minimum position limit plus safety margin) and depends on the "
    "syringe and mechanics; no text states it, so the site sets the range")
VOLUME_REASON = (
    "the usable volume depends on the installed syringe, a constructor option, and no text of the clone states a "
    "volume bound; the site sets the range of its syringe")


class Cetoni(Driver):
    device_id = "cetoni"
    device_kind = "fluid.pump"
    mode = "hardware"
    risk = "R2"
    native = "cetoniSerial:Syringe"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeCetoni"}
    vendor, model = "Cetoni", "Nemesys V4 syringe pump"
    display_name = "Cetoni Nemesys V4 syringe pump"
    tags = ["syringe pump", "cetoni", "nemesys", "serial", "fluid"]
    facts = [
        Fact("The module controls Cetoni Nemesys V4 syringe pumps over a serial port", source="vendor_doc",
             ref="README.md:2"),
        Fact("The syringe volume is a constructor option in uL; a second syringe shares the serial object of the "
             "first and gets its own node id", source="upstream_code", ref=f"{SOURCE}:42-50"),
        Fact("A frame is DLE (0x90), STX (0x02), a little-endian payload and a CRC-16, with byte stuffing (DLE "
             "doubled)", source="upstream_code", ref=f"{SOURCE}:203-219"),
        Fact("read() sends opcode 0x60 with node id, object index, subindex and word count", source="upstream_code",
             ref=f"{SOURCE}:259-268"),
        Fact("write() sends opcode 0x68 with node id, object index, subindex, word count and a packed value",
             source="upstream_code", ref=f"{SOURCE}:292-304"),
        Fact("readStatus reads the state register 0x6041", source="upstream_code", ref=f"{SOURCE}:318-319"),
        Fact("readCurrentPosition reads 0x6064 and readTargetPosition reads 0x607a as signed 32-bit values; "
             "writeTargetPosition writes 0x607a", source="upstream_code", ref=f"{SOURCE}:358-365"),
        Fact("readVelocity reads 0x6081 and setVelocity accepts only 0 < velocity <= maxProfileVelocity",
             source="upstream_code", ref=f"{SOURCE}:348-356"),
        Fact("setFlowRate converts uL/s to the profile velocity register and asserts 0 <= flowRate <= maxVolperS",
             source="upstream_code", ref=f"{SOURCE}:455-464"),
        Fact("aspirate applies -volume and dispense +volume; both execute the relative move and wait until the state "
             "register reads 1079", source="upstream_code", ref=f"{SOURCE}:424-444"),
        Fact("The constructor asserts that the safety stop input (bit 28 of digital input 0x60fd) is off",
             source="upstream_code", ref=f"{SOURCE}:136-139"),
        Fact("The constructor shuts the drive down with control word 0x06 and enables it with 0x0f through control "
             "register 0x6040", source="upstream_code", ref=f"{SOURCE}:149-155"),
        Fact("toInput calls switchValves(1,0) and toOutput calls switchValves(0,1); switchValves drives 0x60fe and "
             "caches the bits in physicalOutputs", source="upstream_code", ref=f"{SOURCE}:321-346"),
        Fact("The minimum position limit and the safety margin come from 0x607D subindex 1 and subindex 2",
             source="upstream_code", ref=f"{SOURCE}:96-101"),
        Fact("The maximum profile velocity is read from 0x607F and maxVolperS is derived from it "
             "(maxProfileVelocity*0.001 = maxRPM)", source="upstream_code", ref=f"{SOURCE}:107-114"),
        Fact("The cross-section is volume/60 (all units mm and uL) and the position conversion factor is "
             "encoderResolution*gearFactor", source="upstream_code", ref=f"{SOURCE}:72-90"),
    ]
    safe_state = "drive disabled by writing control word 0x06 to control register 0x6040, so motion stops"

    # -- reads -------------------------------------------------------------------------------------------------
    @read("current_position", type="integer", unit="1",
          description="Current position in encoder increments (object 0x6064, signed 32-bit)")
    def current_position(self):
        return self.native.readCurrentPosition()

    @read("target_position", type="integer", unit="1",
          description="Target position register in encoder increments (object 0x607a, signed 32-bit)")
    def target_position(self):
        return self.native.readTargetPosition()

    @read("velocity", type="integer", unit="1",
          description="Profile velocity register (object 0x6081); the upstream conversion treats one unit as "
                      "0.001 rpm")
    def velocity(self):
        return self.native.readVelocity()

    @read("flow_rate", unit="uL/s",
          description="Flow rate derived from the velocity register with the upstream setFlowRate conversion")
    def flow_rate(self):
        velocity = self.native.readVelocity()
        return velocity * self.native.crossSection / (60 * self.native.gearFactor * 1000)

    @read("status", type="integer", description="State register (object 0x6041)")
    def status(self):
        return self.native.readStatus()

    @read("valve_position", type="string", enum=["input", "output", "closed"],
          description="Last valve position commanded through this driver; the upstream class caches it in "
                      "physicalOutputs and does not read the drive back")
    def valve_position(self):
        outputs = int(self.native.physicalOutputs)
        if outputs & (1 << 16):
            return "input"
        if outputs & (1 << 17):
            return "output"
        return "closed"

    # -- writes ------------------------------------------------------------------------------------------------
    @write("velocity", type="integer", unit="1",
           description="Profile velocity register (object 0x6081), in the 0.001 rpm unit of the upstream conversion",
           limit=Limit.operator_required(VELOCITY_REASON))
    def set_velocity(self, value):
        self.native.setVelocity(value)

    @write("flow_rate", unit="uL/s", description="Flow rate in uL/s, converted by the upstream setFlowRate",
           limit=Limit.operator_required(FLOW_REASON))
    def set_flow_rate(self, value):
        self.native.setFlowRate(value)

    @write("target_position", type="integer", unit="1",
           description="Target position register (object 0x607a) in encoder increments; writing it does not start "
                       "a move",
           limit=Limit.operator_required(POSITION_REASON))
    def set_target_position(self, value):
        self.native.writeTargetPosition(value)

    @write("valve_position", type="string",
           description="Valve position: input calls toInput(), output calls toOutput()",
           limit=Limit(allowed=["input", "output"], source="upstream_code", ref=f"{SOURCE}:342-346"))
    def set_valve_position(self, value):
        if value == "input":
            self.native.toInput()
        else:
            self.native.toOutput()

    # -- action ------------------------------------------------------------------------------------------------
    @action(cap="cap.actuation.pump.v1",
            description="Aspirate (direction reverse) or dispense (direction forward) a volume at a flow rate; "
                        "the valve position is set separately. A volume is required: this pump moves a volume, not "
                        "for a duration. dispensed_volume is the volume moved in the requested direction.",
            input={
                "flow_rate": Field(unit="uL/s", description="Flow rate in uL/s",
                                   limit=Limit.operator_required(FLOW_REASON)),
                "direction": Field(description="forward dispenses, reverse aspirates"),
                "volume": Field(unit="uL", description="Volume to move; required although the class makes it "
                                                       "optional",
                                limit=Limit.operator_required(VOLUME_REASON)),
            })
    def pump(self, flow_rate, direction, volume=None):
        if volume is None:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "the pump moves a volume: send volume with the command")
        self.native.setFlowRate(flow_rate)
        if direction == "reverse":
            self.native.aspirate(volume)
        elif direction == "forward":
            self.native.dispense(volume)
        else:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET", f"unknown direction {direction!r}")
        return {"dispensed_volume": float(volume)}

    # -- safety ------------------------------------------------------------------------------------------------
    @action(name="x-cap.bennomeier.stop_pump.v1", safe_state=True,
            description="Disable the drive with control word 0x06 (shutdown), the safe state; it takes no input",
            output={"stopped": Field("boolean", description="True once the control word was written")})
    def stop_pump(self):
        self.native.write(0x6040, 0, 4, 0x06)
        return {"stopped": True}

    @estop
    def stop(self):
        """Native stop: write control word 0x06 (shutdown) to 0x6040, as the constructor does before enabling."""
        self.native.write(0x6040, 0, 4, 0x06)

    def teardown(self):
        self.native.close()
