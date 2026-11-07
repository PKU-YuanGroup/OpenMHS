"""OpenMHS driver for gh.beniroquai/opentrons-microscope-platereader: the NEJE laser 2 serial controller.

DEVIATION FROM THE CARD: the card names the serial family and SerialDriver.  The upstream does not send text
lines: ``PYTHON.opentrons_neje_laser2_controler:pyGraver`` writes binary frames assembled at run time (a 0xFF
prefix, a command payload, and a 0x55 terminator, source line 67 and 74) and reads replies up to the 0x55
terminator (source line 128).  A command table cannot reproduce frames built from parts, so this is a direct
Driver over the upstream class with a ``native.py`` factory (driver-authoring.md, "Choosing the shape").

* reads: the carving progress the controller last parsed from a reply (``carvingPercentProgress``);
* actions: move the head to an absolute XY target (``moveXY``), set the laser power and idle bytes (``setPWD``),
  pause the current job (``pauseCarving``), and stop carving (``stopCarving``, the safe state);
* the native stop is ``stopCarving``; the runtime latches first and then sends that stop frame.

Every numeric action input is ``Limit.operator_required``: the clone encodes x and y as two bytes and the laser
power and idle as one byte each, but it states no travel range and no laser power range.  Until the site supplies
those ranges, every call that sets one is refused with ``MHS.SAFETY.LIMITS_UNSET`` (``site-limits.example.json``
shows the overlay shape; its numbers are examples, not device limits).

The clone does not state the laser class.  The controller drives a laser output, and the Grbl laser documentation
in the clone warns that lasers can cause fires and permanently damage vision
(``ARDUINO/library/grbl-master/doc/markdown/laser_mode.md:3``).  An engraving laser burns material, which only a
class 4 source does, so a model review declared the device R3 (MHS/spec/04-safety.md), above the card's R1 floor.  This package is model-authored and unreviewed, and it never ran on hardware (README.md).

The upstream module has a module-level test block (source lines 239-257) that would open a serial port on import;
``native.py`` loads only the class definition and the constants it uses from that file, never the test block.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read

UPSTREAM = "PYTHON/opentrons_neje_laser2_controler.py"

MOVE_REASON = ("the clone encodes x and y as two bytes each (source lines 198-199) but states no travel range of "
               "the machine; the site declares the usable travel")
LASER_REASON = ("the clone sends the laser power and idle as one byte each (source line 209) but states no optical "
                "power range; the site declares the settings its laser may use")


class NejeLaser2(Driver):
    device_id = "neje-laser2"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R3"
    native = "PYTHON.opentrons_neje_laser2_controler:pyGraver"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakePyGraver"}
    vendor, model = "beniroquai", "NEJE laser 2 controller (pyGraver)"
    display_name = "NEJE laser 2 engraver controller (pyGraver serial protocol)"
    tags = ["laser", "engraver", "neje", "serial", "motion"]
    facts = [
        Fact("pyGraver opens the controller's serial port at 57600 baud", source="upstream_code",
             ref=f"{UPSTREAM}:32"),
        Fact("A three-byte command is sent as 0xFF followed by the three command bytes", source="upstream_code",
             ref=f"{UPSTREAM}:67"),
        Fact("A command array is sent as 0xFF followed by the array", source="upstream_code",
             ref=f"{UPSTREAM}:74"),
        Fact("A reply is read up to the 0x55 terminator", source="upstream_code", ref=f"{UPSTREAM}:128"),
        Fact("Byte 2 of a reply selects the parser: 8 upload info, 11 status, 14 carving progress, 16 after upload",
             source="upstream_code", ref=f"{UPSTREAM}:136-143"),
        Fact("A carving-progress reply carries a percentage in byte 6 and stores it in carvingPercentProgress",
             source="upstream_code", ref=f"{UPSTREAM}:158-169"),
        Fact("moveXY sends an absolute XY target with each coordinate split into high and low bytes",
             source="upstream_code", ref=f"{UPSTREAM}:195-200"),
        Fact("setPWD sends the laser power p and the idle value i as single bytes", source="upstream_code",
             ref=f"{UPSTREAM}:205-209"),
        Fact("stopCarving sends the stop-carving frame 0xAA 0x08 0x02 0x01 0x01 0x02 0x55",
             source="upstream_code", ref=f"{UPSTREAM}:211-215"),
        Fact("pauseCarving sends the pause frame 0xAA 0x08 0x02 0x01 0x01 0x00 0x55", source="upstream_code",
             ref=f"{UPSTREAM}:217-221"),
        Fact("MAX_WIDTH and MAX_HEIGHT are 490", source="upstream_code", ref=f"{UPSTREAM}:15-16"),
        Fact("The class starts with location at [MAX_WIDTH//2, MAX_HEIGHT//2]", source="upstream_code",
             ref=f"{UPSTREAM}:33"),
        Fact("The module-level test block opens pyGraver on COM7 and runs a 10 by 10 move loop when the module is "
             "imported", source="upstream_code", ref=f"{UPSTREAM}:239-257"),
    ]
    safe_state = "carving stopped with the controller's stopCarving frame (the controller is told to stop the job)"

    @read("carving_progress", type="integer", unit="%",
          description="Carving progress the controller last parsed from a reply (0 to 100 %)")
    def carving_progress(self):
        return int(self.native.carvingPercentProgress)

    @action(name="x-cap.beniroquai.move_xy.v1",
            description="Move the engraver head to an absolute XY target (moveXY frame)",
            input={
                "x": Field("integer", unit="1",
                           description="X target in the controller's integer step units",
                           limit=Limit.operator_required(MOVE_REASON)),
                "y": Field("integer", unit="1",
                           description="Y target in the controller's integer step units",
                           limit=Limit.operator_required(MOVE_REASON)),
            },
            output={
                "x": Field("integer", unit="1", description="X target sent to the controller"),
                "y": Field("integer", unit="1", description="Y target sent to the controller"),
            })
    def move_xy(self, x, y):
        self.native.moveXY(int(x), int(y))
        return {"x": int(x), "y": int(y)}

    @action(name="x-cap.beniroquai.set_laser.v1", risk="R3",
            description="Set the laser power and idle bytes (setPWD frame)",
            input={
                "power": Field("integer", unit="1",
                               description="Laser power byte sent in the setPWD frame",
                               limit=Limit.operator_required(LASER_REASON)),
                "idle": Field("integer", unit="1",
                              description="Laser idle byte sent in the setPWD frame",
                              limit=Limit.operator_required(LASER_REASON)),
            },
            output={
                "power": Field("integer", unit="1", description="Laser power byte sent to the controller"),
                "idle": Field("integer", unit="1", description="Laser idle byte sent to the controller"),
            })
    def set_laser(self, power, idle):
        self.native.setPWD(int(power), int(idle))
        return {"power": int(power), "idle": int(idle)}

    @action(name="x-cap.beniroquai.pause_carving.v1",
            description="Pause the current carving job (pauseCarving frame)",
            output={"paused": Field("boolean", description="True once the pause frame was sent")})
    def pause_carving(self):
        self.native.pauseCarving()
        return {"paused": True}

    @action(name="x-cap.beniroquai.stop_carving.v1", safe_state=True,
            description="Stop carving with the controller's stop frame (the safe state; the stop command takes no "
                        "deceleration input)",
            output={"stopped": Field("boolean", description="True once the stop frame was sent")})
    def stop_carving(self):
        self.native.stopCarving()
        return {"stopped": True}

    @estop
    def stop(self):
        """The native stop: the runtime latches first, then sends the stopCarving frame."""
        self.native.stopCarving()

    def teardown(self):
        self.native.close()
