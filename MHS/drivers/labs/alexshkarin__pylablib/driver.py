"""OpenMHS driver for gh.alexshkarin/pylablib: a Thorlabs Kinesis motor controller stage.

A direct Driver (decorated methods) over the upstream class
``pylablib.devices.Thorlabs.kinesis:KinesisMotor`` (pylablib/devices/Thorlabs/kinesis.py:1171), the first entry symbol
of the card.  The card is a driver pack (five device classes in one library): this package covers the motor controller
only, and facts.md names the other four camera classes as not covered.

The upstream class speaks the Thorlabs APT protocol over an FTDI virtual serial port; the driver calls its public
methods and never touches the wire format.  Every position and velocity is asked for with ``scale=False``, so the
values are the device's own encoder/motor steps (kinesis.py:444, kinesis.py:523) whatever stage scale the controller
was opened with; this package therefore works in device internal units.

* reads: position (steps), moving, homed, the status strings, the maximum velocity (steps/s), the controller model
  number and the number of motor channels;
* one write: the maximum velocity of the axis.  No text file of the clone states the velocity or travel range of the
  stage that is mounted on a controller, so it is ``Limit.operator_required``: every write is refused
  ``MHS.SAFETY.LIMITS_UNSET`` until the site supplies the range of its stage (``site-limits.example.json`` shows the
  overlay);
* actions: stop the motion (``cap.motion.stop.v1``, the safe state, which also runs during an e-stop), home the axis
  and an absolute move in encoder steps.  Homing and the move are extensions: ``cap.motion.home.v1`` speaks named robot
  axes and joint positions in rad and its speed scale has no equivalent in the APT homing command, and no class carries
  the position of a linear stage in encoder steps;
* the native stop (MOT_STOP with the immediate flag, kinesis.py:509) is the e-stop.

Every Fact cites a line of the clone at the pinned commit (96d9504d3e668f18beb3b75503c01b93152dbcd5).  This package
is model-authored and unreviewed: it is checked on the fake backend only.
"""

import time

from mhs.driver import Cancelled, Driver, Fact, Field, Limit, action, estop, read, write


class KinesisMotorStage(Driver):
    device_id = "kinesis-motor"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R1"
    native = "pylablib.devices.Thorlabs.kinesis:KinesisMotor"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeKinesisMotor"}
    vendor, model = "Thorlabs", "Kinesis (APT) motor controller"
    display_name = "Thorlabs Kinesis motor controller (pylablib KinesisMotor)"
    tags = ["motor", "stage", "thorlabs", "apt", "kinesis", "motion"]
    facts = [
        Fact("KinesisMotor is the Thorlabs motor controller class; it implements FTDI chip connectivity via pyft232 "
             "(virtual serial interface)", source="upstream_code",
             ref="pylablib/devices/Thorlabs/kinesis.py:1173-1175"),
        Fact("The physical units are encoder steps for position (ratio to m or degrees depends on the connected "
             "stage), steps/sec for velocity, and steps/sec^2 for acceleration", source="upstream_code",
             ref="pylablib/devices/Thorlabs/kinesis.py:1177-1178"),
        Fact("get_position(scale=False) returns the position in the device internal units (steps)",
             source="upstream_code", ref="pylablib/devices/Thorlabs/kinesis.py:440-444"),
        Fact("move_to(position, scale=False) sends MOT_MOVE_TO (0x0453) with the position as a 32-bit signed integer",
             source="upstream_code", ref="pylablib/devices/Thorlabs/kinesis.py:469-475"),
        Fact("stop(immediate=True, sync=False) sends MOT_STOP (0x0465) with parameter 1 (abrupt stop); "
             "immediate=False sends parameter 2", source="upstream_code",
             ref="pylablib/devices/Thorlabs/kinesis.py:501-509"),
        Fact("is_moving is true when any of moving_fw, moving_bk, jogging_fw, jogging_bk or active is set",
             source="upstream_code", ref="pylablib/devices/Thorlabs/kinesis.py:491-496"),
        Fact("home(sync=False) sends MOT_HOME (0x0443); is_homing and is_homed read the homing and homed status bits",
             source="upstream_code", ref="pylablib/devices/Thorlabs/kinesis.py:388-407"),
        Fact("get_status returns the status strings of the status_bits table, which names the hardware and software "
             "limit switches, the motion bits, homing, interlock, overtemperature and error", source="upstream_code",
             ref="pylablib/devices/Thorlabs/kinesis.py:338-344"),
        Fact("get_velocity_parameters(scale=False) returns (min_velocity, acceleration, max_velocity) in device "
             "internal units; according to the documentation the minimal velocity is always zero",
             source="upstream_code", ref="pylablib/devices/Thorlabs/kinesis.py:517-530"),
        Fact("setup_velocity(max_velocity=..., scale=False) writes the velocity parameters and uses the current "
             "values for the ones given as None", source="upstream_code",
             ref="pylablib/devices/Thorlabs/kinesis.py:531-546"),
        Fact("get_device_info returns (serial_no, model_no, fw_ver, hw_type, hw_ver, mod_state, nchannels, notes) and "
             "get_number_of_channels returns nchannels", source="upstream_code",
             ref="pylablib/devices/Thorlabs/kinesis.py:224-241"),
        Fact("get_scale_units reports the scale units in use (deg, m, step, user_step, user or internal); this driver "
             "asks every value with scale=False and so always works in device internal units",
             source="upstream_code", ref="pylablib/devices/Thorlabs/kinesis.py:1335-1346"),
    ]
    safe_state = "motion stopped (native MOT_STOP with the immediate flag, kinesis.py:509)"

    # -- reads ------------------------------------------------------------------------------------------------
    @read("position", unit="1", description="Axis position in device encoder steps")
    def position(self):
        return self.native.get_position(scale=False)

    @read("moving", type="boolean", description="True while a move, jog or homing is in progress")
    def moving(self):
        return self.native.is_moving()

    @read("homed", type="boolean", description="True once the axis is homed")
    def homed(self):
        return self.native.is_homed()

    @read("status", type="array", items="string",
          description="Status strings of the controller (limit switches, motion, homing, interlock, error bits)")
    def status(self):
        return list(self.native.get_status())

    @read("max_velocity", unit="1/s", description="Maximum velocity of the axis in device encoder steps per second")
    def max_velocity(self):
        return self.native.get_velocity_parameters(scale=False).max_velocity

    @read("controller_model", type="string", description="Controller model number reported by the device")
    def controller_model(self):
        return self.native.get_device_info().model_no

    @read("channel_count", type="integer", description="Number of motor channels of the controller")
    def channel_count(self):
        return self.native.get_number_of_channels()

    # -- the one write ------------------------------------------------------------------------------------------
    @write("max_velocity", unit="1/s",
           description="Maximum velocity of the axis in device encoder steps per second",
           limit=Limit.operator_required(
               "no text file of the clone states the velocity range of a stage or a motor (the APT manual is not in "
               "the clone); the site sets the range of the stage mounted on its controller"))
    def set_max_velocity(self, value):
        parameters = self.native.setup_velocity(max_velocity=value, scale=False)
        return parameters.max_velocity        # the value the controller stored (whole steps per second)

    # -- actions --------------------------------------------------------------------------------------------------
    @action(name="x-cap.alexshkarin.home_axis.v1",
            description="Home the axis with the native MOT_HOME and report the homed bit; it takes no input",
            output={"homed": Field("boolean", description="True once the axis reports that it is homed")})
    def home_axis(self):
        self.native.home(sync=False, force=True)
        while self.native.is_homing():
            if self.cancelled():
                raise Cancelled("homing was cancelled before the axis was homed")
            time.sleep(0.02)
        return {"homed": bool(self.native.is_homed())}

    @action(cap="cap.motion.stop.v1", safe_state=True,
            description="Stop the axis motion with the native MOT_STOP; a deceleration request selects the profiled "
                        "stop (parameter 2), without one the abrupt stop (parameter 1) is used",
            input={"deceleration": Field("number", unit="m/s2",
                                         description="A deceleration profile request: the APT stop command carries no "
                                                     "deceleration value, so a value selects the profiled stop and the "
                                                     "controller's configured acceleration governs")})
    def stop_motion(self, deceleration=None):
        self.native.stop(immediate=deceleration is None, sync=False)
        return {"stopped": not self.native.is_moving()}

    @action(name="x-cap.alexshkarin.move_to_absolute.v1",
            description="Move the axis to an absolute position in device encoder steps and wait until it stops",
            input={"target_position": Field("number", unit="1",
                                            description="Target position in device encoder steps",
                                            limit=Limit.operator_required(
                                                "the travel range depends on the stage mounted on the controller and "
                                                "no text file of the clone states it; the site sets the range of its "
                                                "stage"))},
            output={"position": Field("number", unit="1", description="Position reported after the motion stopped")})
    def move_to_absolute(self, target_position):
        self.native.move_to(target_position, scale=False)
        while self.native.is_moving():
            if self.cancelled():
                raise Cancelled("the move was cancelled before the axis stopped")
            time.sleep(0.02)
        return {"position": self.native.get_position(scale=False)}

    # -- safety -------------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: the runtime latches first, then sends the abrupt MOT_STOP."""
        self.native.stop(immediate=True, sync=False)

    def teardown(self):
        self.native.close()     # pylablib/core/devio/comm_backend.py:1819
