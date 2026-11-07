"""OpenMHS driver for gh.azdagkas/kinesis-piezo: a Thorlabs TPZ001 piezo controller with a TSG001 strain gauge reader.

A direct Driver (decorated methods) over the upstream class ``piezo:PiezoController``.  The upstream object is a thin
wrapper around the Thorlabs Kinesis .NET API through pythonnet: it connects and enables the controller, keeps a
strain gauge reader object when one is configured, and exposes the controller value, the loop mode, jog steps, the
native home command and a percentage-to-reader calibration (piezo.py:178-192, 227-340).

* reads: the controller value (percentage travel in closed loop, output voltage in open loop), the unit of that
  value, the loop mode, the strain gauge reading and its unit, and whether the reader is zeroing;
* writes: ``value`` (the native set_value) and ``closed_loop`` (the native set_closed_loop/set_open_loop);
* actions: home (the native move_to_home, also the safe-state action), up and down jog steps, the reader zeroing,
  the native calibration, and a calibrated move to a reader position.  The catalogue motion classes fix inputs in
  radians and the calibration class does not list ``motion.axis``, so the motion actions are ``x-cap`` extensions;
* limits: no text file of the clone states a travel/voltage range for an installed stage, so the numeric write and
  the calibrated position input are ``Limit.operator_required``.  Until the site overlay fills them every such call
  is refused ``MHS.SAFETY.LIMITS_UNSET`` (site-limits.example.json shows the shape);
* safety: the native ``move_to_home`` drives the travel to zero and is the e-stop and the safe-state action.  The
  clone documents no independent hardware e-stop, so this package claims no ``estop_physical_ref``.

Every Fact cites a line of the clone at the pinned commit ecfe0586cef37d83e287a1fee3496a3eb67f4acd.  This package
is model-authored and unreviewed: it is checked on the fake backend only, the hardware factory was never imported or
run, and no hardware test was performed.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write


class KinesisPiezo(Driver):
    device_id = "kinesis-piezo"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R1"
    native = "piezo:PiezoController"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeKinesisPiezo"}
    vendor, model = "Thorlabs", "TPZ001 piezo driver with TSG001 strain gauge reader"
    display_name = "Thorlabs TPZ001 piezo controller (piezo.PiezoController)"
    tags = ["thorlabs", "piezo", "stage", "motion", "kinesis", "strain-gauge"]
    facts = [
        Fact("The repository contains code for the control of the Thorlabs TPZ001 piezo driver and TSG001 strain "
             "gauge reader with the Kinesis API", source="vendor_doc", ref="README.md:4-5"),
        Fact("The module imports pythonnet's clr and the Thorlabs Kinesis .NET assemblies", source="upstream_code",
             ref="piezo.py:5-18"),
        Fact("The README lists pythonnet as a requirement", source="vendor_doc", ref="README.md:23-25"),
        Fact("The Kinesis DLLs the module references must be placed in libs/kinesis", source="vendor_doc",
             ref="libs/kinesis/info.txt:1-13"),
        Fact("PiezoController takes the controller serial number and an optional strain gauge reader serial number",
             source="upstream_code", ref="piezo.py:178-182"),
        Fact("initialize creates a StrainReader from the reader serial number when one is configured",
             source="upstream_code", ref="piezo.py:224-225"),
        Fact("initialize sets the output voltage range maximum to 75 and both the voltage and percentage jog step "
             "sizes to 1 before loading the settings into the device", source="upstream_code",
             ref="piezo.py:218-222"),
        Fact("connect_enable connects the device, waits for the settings, starts 250 ms polling, sleeps 500 ms and "
             "enables the device", source="upstream_code", ref="piezo.py:55-94"),
        Fact("get_units returns '%' in closed loop and 'V' in open loop", source="upstream_code",
             ref="piezo.py:227-232"),
        Fact("get_value returns the percentage travel in closed loop and the output voltage in open loop",
             source="upstream_code", ref="piezo.py:234-239"),
        Fact("set_value writes the percentage travel in closed loop and the output voltage in open loop",
             source="upstream_code", ref="piezo.py:241-245"),
        Fact("moveup and movedown call Jog(1) and Jog(2)", source="upstream_code", ref="piezo.py:247-251"),
        Fact("move_to_home writes 0 percentage travel in closed loop and 0 output voltage in open loop",
             source="upstream_code", ref="piezo.py:253-257"),
        Fact("is_closed_loop returns the device status flag IsClosedLoop", source="upstream_code",
             ref="piezo.py:260-261"),
        Fact("set_closed_loop selects the software voltage source and position control mode 2",
             source="upstream_code", ref="piezo.py:263-277"),
        Fact("set_open_loop selects the software voltage source and position control mode 1",
             source="upstream_code", ref="piezo.py:279-293"),
        Fact("calibrate_pos drives 10 and 70 percent of travel, reads the strain gauge position at each point, and "
             "fits percentage = a*position + b", source="upstream_code", ref="piezo.py:295-325"),
        Fact("move_to_pos converts a reader position to percentage travel with the calibration slope and offset",
             source="upstream_code", ref="piezo.py:327-329"),
        Fact("move_pos_up moves 1 reader unit up while the reading is below 19 and move_pos_down moves 1 unit down "
             "while it is above 1", source="upstream_code", ref="piezo.py:331-337"),
        Fact("move_pos_to_home calls move_to_pos(0)", source="upstream_code", ref="piezo.py:339-340"),
        Fact("The reader position is the strain gauge status reading converted from a .NET Decimal to double",
             source="upstream_code", ref="piezo.py:134-136"),
        Fact("set_zero calls SetZero and is_zeroing returns the status flag IsZeroing", source="upstream_code",
             ref="piezo.py:138-142"),
        Fact("The reader get_units maps display mode 1 to micrometre, 2 to volt, 3 to newton and anything else to "
             "an error string", source="upstream_code", ref="piezo.py:144-153"),
    ]
    safe_state = "piezo travel driven to zero (percentage travel 0 or output voltage 0 V)"

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("value", unit="1",
          description="Controller value: percentage of full travel in closed loop or output voltage in open loop; "
                      "the units read says which")
    def value(self):
        return float(self.native.get_value())

    @read("units", type="string", description="Unit of the controller value: '%' in closed loop or 'V' in open loop")
    def units(self):
        return self.native.get_units()

    @read("closed_loop", type="boolean", description="True when position control is closed loop")
    def closed_loop(self):
        return bool(self.native.is_closed_loop())

    @read("reader_reading", unit="1",
          description="Strain gauge reader reading in the unit reported by reader_units (micrometre, volt or newton)")
    def reader_reading(self):
        return float(self.native.reader.get_pos())

    @read("reader_units", type="string",
          description="Unit of the strain gauge reading: micrometre, volt, newton or the reader's error string")
    def reader_units(self):
        return self.native.reader.get_units()

    @read("zeroing", type="boolean", description="True while the strain gauge reader reports zeroing")
    def zeroing(self):
        return bool(self.native.reader.is_zeroing())

    # -- writes ---------------------------------------------------------------------------------------------------
    @write("value", unit="1",
           description="Controller value: percentage of full travel in closed loop or output voltage in open loop; "
                       "the units read says which",
           limit=Limit.operator_required(
               "no text file of the clone states the permitted travel range in percentage or the permitted output "
               "voltage of an installed stage; the 75 V maximum the upstream sets is an output-range setting "
               "(piezo.py:219), not a safe travel bound, so the site supplies the bound in the unit of the mode in "
               "use"))
    def set_value(self, value):
        self.native.set_value(value)

    @write("closed_loop", type="boolean",
           description="Select closed-loop position control (True) or open-loop output voltage (False)")
    def set_closed_loop(self, value):
        if value:
            self.native.set_closed_loop()
        else:
            self.native.set_open_loop()

    # -- actions --------------------------------------------------------------------------------------------------
    @action(name="x-cap.azdagkas.kinesis_piezo.move_to_home.v1", safe_state=True,
            description="Drive the piezo travel to zero with the native move_to_home (the safe state)",
            output={"value": Field("number", description="Controller value after the move; read units for the unit")})
    def move_to_home(self):
        self.native.move_to_home()
        return {"value": float(self.native.get_value())}

    @action(name="x-cap.azdagkas.kinesis_piezo.jog_up.v1",
            description="Step the controller value up by one configured jog step (the native moveup)",
            output={"value": Field("number", description="Controller value after the step; read units for the unit")})
    def jog_up(self):
        self.native.moveup()
        return {"value": float(self.native.get_value())}

    @action(name="x-cap.azdagkas.kinesis_piezo.jog_down.v1",
            description="Step the controller value down by one configured jog step (the native movedown)",
            output={"value": Field("number", description="Controller value after the step; read units for the unit")})
    def jog_down(self):
        self.native.movedown()
        return {"value": float(self.native.get_value())}

    @action(name="x-cap.azdagkas.kinesis_piezo.calibrate_position.v1",
            description="Run the native calibration: drive 10 and 70 percent and fit percentage travel to the "
                        "strain gauge reader",
            output={"calibrated": Field("boolean", description="True when the native calibration returned")})
    def calibrate_position(self):
        if self.native.reader is None:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "no strain gauge reader is configured, so the position calibration cannot run")
        if not self.native.is_closed_loop():
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "the calibration uses percentage travel and requires closed-loop control")
        self.native.calibrate_pos()
        return {"calibrated": True}

    @action(name="x-cap.azdagkas.kinesis_piezo.move_to_position.v1",
            description="Move to a strain gauge reader position with the stored calibration (the native move_to_pos)",
            input={"position": Field(
                "number", unit="1",
                description="Target position in the strain gauge reader's current display unit (read reader_units)",
                limit=Limit.operator_required(
                    "no text file of the clone states the travel range of the installed stage; the two convenience "
                    "steps guard only at 19 and 1 reader units (piezo.py:332,336), not a travel bound, so the site "
                    "supplies the permitted position range in the reader display unit"))},
            output={"position": Field(
                "number", unit="1",
                description="Strain gauge reading after the move, in the reader display unit")})
    def move_to_position(self, position):
        if self.native.reader is None:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "no strain gauge reader is configured, so a reader position cannot be used")
        if not self.native.is_closed_loop():
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "a calibrated position move uses percentage travel and requires closed-loop control")
        if self.native.a is None or self.native.b is None:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "the controller has no position calibration yet; run calibrate_position first")
        self.native.move_to_pos(position)
        return {"position": float(self.native.reader.get_pos())}

    @action(name="x-cap.azdagkas.kinesis_piezo.zero_reader.v1",
            description="Zero the strain gauge reader with the native reader set_zero",
            output={"zeroing": Field("boolean",
                                     description="True when the reader reports that zeroing is in progress")})
    def zero_reader(self):
        if self.native.reader is None:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "no strain gauge reader is configured, so there is nothing to zero")
        self.native.reader.set_zero()
        return {"zeroing": bool(self.native.reader.is_zeroing())}

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop path: drive the piezo travel to zero (the runtime latches first)."""
        self.native.move_to_home()
