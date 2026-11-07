"""OpenMHS driver for gh.burhankarahasan/thorlabs-pico: the Pi Pico W stepper controller of the repository.

A direct Driver (decorated methods) over stepper_controller:PicoStepperController, the first entry symbol of the
card.  The upstream class drives a stepper motor over a newline-terminated text protocol: a command is written as
``<command>\\n`` and one reply line is read (stepper_controller.py:10-12, 56-68).  The class is synchronous and uses
pyserial; this package's fake backend replaces the serial line with an in-memory object.

* reads: the current speed, the target speed and the step position, all decoded from the STATUS reply
  (stepper_controller.py:139-154);
* one write: the target speed in revolutions per second, sent with SPEED_RPS (stepper_controller.py:70-81);
* actions: enable the driver, disable it (the upstream docstring says it cuts power, stepper_controller.py:116-124),
  set the ramp rate (RAMP, steps/sec^2, stepper_controller.py:126-137) and stop (STOP, the safe state,
  stepper_controller.py:96-104);
* e-stop: the same native stop.

No text of the clone states a safe speed, ramp or travel range for the installed stepper and driver: README.md:29
says the example firmware and library settings must be matched to the user's hardware, and README.md:408-411 calls
the GUI speed range the user's own limits ("Change to your limits").  Every numeric input is therefore
``Limit.operator_required`` and is refused ``MHS.SAFETY.LIMITS_UNSET`` until the site supplies a range;
``site-limits.example.json`` shows the overlay.

The card's second entry symbol, lts_controller:ThorlabsLTSController, is a separate Thorlabs LTS linear-stage
device and is not covered by this package.

Every Fact cites a line of the clone at the pinned commit 91898e3a55a925ca36ce24d53997351c1b947779.  This package
is model-authored and unreviewed: no hardware was run and it is checked on the fake backend only.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

_SPEED = Limit.operator_required(
    "no text file of the clone states a safe speed range for the installed stepper and driver; README.md:29 says "
    "the example firmware and library settings must be matched to the user's hardware, and README.md:408-411 calls "
    "the GUI range the user's own limits, so the site supplies the range")
_RAMP = Limit.operator_required(
    "no text file of the clone states a ramp-rate range for the installed stepper and driver; the example firmware "
    "starts at 10 steps/sec^2 (accel_stepper_serial.ino:13), but README.md:29 says that configuration is an example "
    "to adapt, so the site supplies the range")


class PicoStepper(Driver):
    device_id = "pico-stepper"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R1"
    native = "stepper_controller:PicoStepperController"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakePicoStepperController"}
    vendor, model = "Raspberry Pi / burhankarahasan", "Pi Pico W stepper controller"
    display_name = "Pi Pico W stepper rotation axis (stepper_controller.PicoStepperController)"
    tags = ["stepper", "rotation", "pico", "serial", "motion"]
    facts = [
        Fact("The controller speaks a text protocol: commands end with a newline and replies start with OK:, ERROR: "
             "or STATUS:", source="upstream_code", ref="stepper_controller.py:10-12"),
        Fact("A command is written as '<command>\\n' and one reply line is read", source="upstream_code",
             ref="stepper_controller.py:56-68"),
        Fact("SPEED_RPS sets the target speed in revolutions per second and accepts negative values for reverse",
             source="upstream_code", ref="stepper_controller.py:70-81"),
        Fact("RAMP sets the acceleration/deceleration rate in steps/sec^2", source="upstream_code",
             ref="stepper_controller.py:126-137"),
        Fact("STOP ramps the motor down to zero speed", source="upstream_code", ref="stepper_controller.py:96-104"),
        Fact("ENABLE enables the stepper driver and DISABLE disables it (the docstring says it cuts power)",
             source="upstream_code", ref="stepper_controller.py:106-124"),
        Fact("STATUS returns (current_rps, target_rps, position in steps), or None when the reply cannot be parsed",
             source="upstream_code", ref="stepper_controller.py:139-154"),
        Fact("The example firmware defines 200 steps per revolution", source="upstream_code",
             ref="accel_stepper_serial.ino:7"),
        Fact("The example firmware sets the AccelStepper maximum speed to 10000 steps/s", source="upstream_code",
             ref="accel_stepper_serial.ino:27"),
        Fact("The example firmware starts with a ramp rate of 10 steps/sec^2", source="upstream_code",
             ref="accel_stepper_serial.ino:13"),
        Fact("The README says to match the microstepping, baudrate and library configuration to the user's "
             "stepper/driver hardware", source="vendor_doc", ref="README.md:29"),
        Fact("The README presents the GUI rotation speed range as the user's own limits ('Change to your limits')",
             source="vendor_doc", ref="README.md:408-411"),
        Fact("The README says the emergency procedure is to click the GUI EMERGENCY STOP ALL button and, if needed, "
             "to turn the power off physically", source="vendor_doc", ref="README.md:435-439"),
    ]
    safe_state = "rotation target zero and the native STOP sent, so the firmware ramps the motor down"

    def _status(self):
        status = self.native.get_status()
        if status is None or len(status) != 3:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               f"the controller returned no usable STATUS reply: {status!r}")
        current, target, position = status
        return float(current), float(target), int(position)

    # -- reads ------------------------------------------------------------------------------------------------
    @read("current_rps", unit="Hz", description="Current rotation speed from STATUS, in revolutions per second")
    def current_rps(self):
        return self._status()[0]

    @read("target_rps", unit="Hz", description="Target rotation speed from STATUS, in revolutions per second")
    def target_rps(self):
        return self._status()[1]

    @read("position_steps", type="integer", unit="1",
          description="Step position from STATUS (the firmware's stepper.currentPosition())")
    def position_steps(self):
        return self._status()[2]

    # -- write -------------------------------------------------------------------------------------------------
    @write("target_rps", unit="Hz", description="Target rotation speed in revolutions per second (negative reverses)",
           limit=_SPEED)
    def set_target_rps(self, value):
        applied = float(value)
        if not self.native.set_speed_rps(applied):
            raise DriverFailed("MHS.DEVICE.FAULTED", f"the controller refused SPEED_RPS:{applied}")
        return self._status()[1]

    # -- actions -----------------------------------------------------------------------------------------------
    @action(cap="cap.motion.stop.v1", safe_state=True,
            description="Stop the rotation with the native STOP; it ramps the target speed to zero",
            input={"deceleration": Field(
                "number", unit="m/s2",
                description="Optional class field; the native STOP has no deceleration setting, so this value is "
                            "not applied")})
    def stop_motion(self, deceleration=None):
        if not self.native.stop():
            raise DriverFailed("MHS.DEVICE.FAULTED", "the controller refused STOP")
        return {"stopped": True, "stopped_position": {"position_steps": self._status()[2]}}

    @action(name="x-cap.burhankarahasan.enable_motor.v1",
            description="Enable the stepper motor driver (the native ENABLE)",
            output={"enabled": Field("boolean", description="True once the controller acknowledged ENABLE")})
    def enable_motor(self):
        if not self.native.enable_motor():
            raise DriverFailed("MHS.DEVICE.FAULTED", "the controller refused ENABLE")
        return {"enabled": True}

    @action(name="x-cap.burhankarahasan.disable_motor.v1",
            description="Disable the stepper motor driver; the upstream docstring says this cuts power (DISABLE)",
            output={"enabled": Field("boolean", description="False once the controller acknowledged DISABLE")})
    def disable_motor(self):
        if not self.native.disable_motor():
            raise DriverFailed("MHS.DEVICE.FAULTED", "the controller refused DISABLE")
        return {"enabled": False}

    @action(name="x-cap.burhankarahasan.set_ramp_rate.v1",
            description="Set the acceleration/deceleration rate in steps/sec^2 (the native RAMP)",
            input={"ramp_rate": Field("number", unit="Hz/s",
                                      description="Ramp rate in steps/second^2 (steps are dimensionless)",
                                      limit=_RAMP)},
            output={"ramp_rate": Field("number", unit="Hz/s",
                                       description="Ramp rate sent to the controller in steps/second^2")})
    def set_ramp_rate(self, ramp_rate):
        applied = float(ramp_rate)
        if not self.native.set_ramp_rate(applied):
            raise DriverFailed("MHS.DEVICE.FAULTED", f"the controller refused RAMP:{applied}")
        return {"ramp_rate": applied}

    # -- safety -------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: the runtime latches first, then sends STOP."""
        if not self.native.stop():
            raise DriverFailed("MHS.DEVICE.FAULTED", "the controller refused STOP during the e-stop")

    def teardown(self):
        self.native.close()                 # stepper_controller.py:156-159
