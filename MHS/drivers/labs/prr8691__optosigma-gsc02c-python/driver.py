"""OpenMHS driver for gh.prr8691/optosigma-gsc02c-python: an OptoSigma GSC-02C delay-stage controller.

A direct Driver over the upstream class ``optosigma_gsc02c.controller:GSC02C``
(``optosigma_gsc02c/controller.py:43``).  The controller is an open-loop stepper controller on an RS-232 line; the
upstream class assembles each ASCII command from parts (a letter and an axis, then signed pulse fields, for example
``M:1+P1000`` and ``D:1S500F10000R200``), so this driver calls the upstream methods and never re-implements a command.

* reads: the controller coordinate in millimetres and in pulses, the busy flag and the raw ``Q:`` status line;
* actions: configure the motion ramp (``D:``), move absolute or relative in millimetres or pulses (``A:``/``M:`` then
  ``G:``), home (``H:``) and the native controlled stop (``L:``);
* no text file of the clone states the travel range of the stage: ``min_position_mm`` and ``max_position_mm`` are
  ``StageConfig`` constructor defaults (``optosigma_gsc02c/controller.py:37-40``) that the upstream says to change when
  the controller or stage is configured differently (``optosigma_gsc02c/controller.py:31``).  Every position and speed
  input is therefore ``Limit.operator_required``: it is refused ``MHS.SAFETY.LIMITS_UNSET`` until the site overlay
  supplies the range of its stage (``site-limits.example.json`` shows the overlay);
* the native stop (``L:``) is both the e-stop and the safe-state action.

Every Fact cites the clone at commit ``d3403dc83f62fd39a3b437c13076ee676122e760``.  This package is model-authored and
unreviewed; it has been checked on the fake backend only and no hardware was attached.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read

_POSITION_MM = Limit.operator_required(
    "the travel range of the stage is a StageConfig constructor default (optosigma_gsc02c/controller.py:37-40) that "
    "the upstream says to change for another stage (optosigma_gsc02c/controller.py:31); the site supplies the "
    "absolute position range of its stage")

_DISTANCE_MM = Limit.operator_required(
    "the allowed step depends on where the stage is inside its travel range, and that range is a StageConfig "
    "constructor default (optosigma_gsc02c/controller.py:37-40); the site supplies the range of its stage")

_POSITION_PULSES = Limit.operator_required(
    "the pulse range maps to the stage travel range, a StageConfig constructor default "
    "(optosigma_gsc02c/controller.py:37-40); the site supplies the absolute pulse range of its stage")

_DISTANCE_PULSES = Limit.operator_required(
    "the allowed pulse step depends on the current position inside the travel range, a StageConfig constructor "
    "default (optosigma_gsc02c/controller.py:37-40); the site supplies the range of its stage")

_START_SPEED = Limit.operator_required(
    "a speed in mm/s depends on StageConfig.um_per_pulse, a constructor default "
    "(optosigma_gsc02c/controller.py:34-35); the controller itself only bounds pulses/s "
    "(optosigma_gsc02c/controller.py:394-402), so the site supplies the mm/s range of its stage")

_MAX_SPEED = Limit.operator_required(
    "a speed in mm/s depends on StageConfig.um_per_pulse, a constructor default "
    "(optosigma_gsc02c/controller.py:34-35); the controller itself only bounds pulses/s "
    "(optosigma_gsc02c/controller.py:394-402), so the site supplies the mm/s range of its stage")


class Gsc02c(Driver):
    device_id = "gsc02c"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R1"
    native = "optosigma_gsc02c.controller:GSC02C"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeGSC02C"}
    vendor = "OptoSigma / Sigma Koki"
    model = "GSC-02C controller with OSMS20-85 stage"
    display_name = "OptoSigma GSC-02C delay stage (optosigma_gsc02c.GSC02C)"
    tags = ["motion", "stage", "delay-stage", "serial", "open-loop"]
    facts = [
        Fact("The controller uses ASCII text commands Q:, M:, A:, G:, D:, H:, L: and !:", source="upstream_code",
             ref="optosigma_gsc02c/controller.py:59-68"),
        Fact("Q: returns the position/status string and !: returns B for busy or R for ready", source="upstream_code",
             ref="optosigma_gsc02c/controller.py:281-298"),
        Fact("get_position_pulses returns the controller's commanded pulse coordinate; it is not an independent "
             "encoder measurement of the carriage", source="upstream_code",
             ref="optosigma_gsc02c/controller.py:328-332"),
        Fact("For the OSMS20-85 half-step configuration one pulse is 1 um, so 1000 pulses are 1 mm",
             source="upstream_code", ref="optosigma_gsc02c/controller.py:239-243"),
        Fact("StageConfig's default software travel range is 0.0 to 85.0 mm", source="upstream_code",
             ref="optosigma_gsc02c/controller.py:37-40"),
        Fact("StageConfig says to change um_per_pulse, min_position_mm and max_position_mm when the controller or "
             "stage is configured differently", source="upstream_code",
             ref="optosigma_gsc02c/controller.py:31"),
        Fact("set_motion validates start and maximum speed in 1..30000 pulses/s and acceleration time in 0..1000 ms",
             source="upstream_code", ref="optosigma_gsc02c/controller.py:393-411"),
        Fact("set_max_speed_mm_s converts mm/s to pulses/s and clamps each speed to at least 1 pulse/s",
             source="upstream_code", ref="optosigma_gsc02c/controller.py:440-452"),
        Fact("The D: command carries the starting speed S, the maximum speed F and the acceleration time R",
             source="upstream_code", ref="optosigma_gsc02c/controller.py:377-390"),
        Fact("M: prepares a relative movement in signed pulses and G: starts the prepared motion",
             source="upstream_code", ref="optosigma_gsc02c/controller.py:504-515"),
        Fact("A: prepares an absolute movement in signed pulses and G: starts the prepared motion",
             source="upstream_code", ref="optosigma_gsc02c/controller.py:594-605"),
        Fact("H: starts the home/origin search and homing waits up to 120 s", source="upstream_code",
             ref="optosigma_gsc02c/controller.py:660-667"),
        Fact("L: requests a controlled deceleration stop", source="upstream_code",
             ref="optosigma_gsc02c/controller.py:669-676"),
        Fact("wait_until_idle waits at most 60 s by default", source="upstream_code",
             ref="optosigma_gsc02c/controller.py:300-303"),
        Fact("The GSC-02C can control two axes, 1 or 2", source="upstream_code",
             ref="optosigma_gsc02c/controller.py:83-84"),
        Fact("The README documents the software travel range of the OSMS20-85 configuration as 0 to 85 mm",
             source="vendor_doc", ref="README.md:21"),
        Fact("The README states that the GSC-02C is an open-loop stepper controller whose reported coordinate is based "
             "on commanded pulses, not on encoder feedback", source="vendor_doc", ref="README.md:124-126"),
        Fact("The RS-232 link is 9600 baud, 8 data bits, no parity, 1 stop bit with RTS/CTS handshaking",
             source="upstream_code", ref="optosigma_gsc02c/controller.py:139-149"),
        Fact("Every command ends with carriage-return plus line-feed", source="upstream_code",
             ref="optosigma_gsc02c/controller.py:96-97"),
    ]
    safe_state = "motion stopped by the controller's native L: command (controlled deceleration)"

    # -- reads ------------------------------------------------------------------------------------------------
    @read("position_mm", unit="mm", description="Controller coordinate of the stage in millimetres")
    def position_mm(self):
        return self.native.get_position_mm()

    @read("position_pulses", type="integer", unit="1", description="Controller coordinate of the stage in pulses")
    def position_pulses(self):
        return self.native.get_position_pulses()

    @read("busy", type="boolean", description="True while the controller reports that the stage is moving")
    def busy(self):
        return self.native.is_busy()

    @read("status", type="string", description="Raw Q: position/status reply of the controller")
    def status(self):
        return self.native.raw_status()

    # -- actions ----------------------------------------------------------------------------------------------
    @action(name="x-cap.prr8691.configure_motion.v1", long_running=True, max_duration_ms=60000,
            description="Set the D: motion ramp used by later moves",
            input={
                "start_speed_mm_s": Field("number", unit="mm/s", description="Speed at which motion begins",
                                          limit=_START_SPEED),
                "max_speed_mm_s": Field("number", unit="mm/s", description="Maximum translation speed",
                                        limit=_MAX_SPEED),
                "accel_time_ms": Field("integer", unit="ms",
                                       description="Acceleration and deceleration ramp time",
                                       limit=Limit(min=0, max=1000, source="upstream_code",
                                                   ref="optosigma_gsc02c/controller.py:409")),
            },
            output={
                "start_speed_mm_s": Field("number", unit="mm/s", description="Applied starting speed"),
                "max_speed_mm_s": Field("number", unit="mm/s", description="Applied maximum speed"),
                "accel_time_ms": Field("integer", unit="ms", description="Applied ramp time"),
            })
    def configure_motion(self, start_speed_mm_s, max_speed_mm_s, accel_time_ms):
        self.native.set_max_speed_mm_s(max_speed_mm_s, start_speed_mm_s=start_speed_mm_s,
                                       accel_time_ms=accel_time_ms)
        # set_max_speed_mm_s rounds the mm/s value to whole pulses; report the value the controller really has.
        start_pulses = max(1, self.native.mm_to_pulses(start_speed_mm_s))
        max_pulses = max(1, self.native.mm_to_pulses(max_speed_mm_s))
        return {"start_speed_mm_s": self.native.pulses_to_mm(start_pulses),
                "max_speed_mm_s": self.native.pulses_to_mm(max_pulses),
                "accel_time_ms": accel_time_ms}

    @action(name="x-cap.prr8691.move_absolute_mm.v1", long_running=True, max_duration_ms=60000,
            description="Move to an absolute position in millimetres (A: then G:)",
            input={"position_mm": Field("number", unit="mm",
                                        description="Absolute controller coordinate in millimetres",
                                        limit=_POSITION_MM)},
            output={
                "position_mm": Field("number", unit="mm", description="Coordinate reported after the move"),
                "position_pulses": Field("integer", unit="1", description="Pulse coordinate reported after the move"),
            })
    def move_absolute_mm(self, position_mm):
        self.native.move_absolute_mm(position_mm)
        return {"position_mm": self.native.get_position_mm(),
                "position_pulses": self.native.get_position_pulses()}

    @action(name="x-cap.prr8691.move_relative_mm.v1", long_running=True, max_duration_ms=60000,
            description="Move by a distance in millimetres (M: then G:)",
            input={"distance_mm": Field("number", unit="mm", description="Signed distance in millimetres",
                                        limit=_DISTANCE_MM)},
            output={
                "position_mm": Field("number", unit="mm", description="Coordinate reported after the move"),
                "position_pulses": Field("integer", unit="1", description="Pulse coordinate reported after the move"),
            })
    def move_relative_mm(self, distance_mm):
        self.native.move_relative_mm(distance_mm)
        return {"position_mm": self.native.get_position_mm(),
                "position_pulses": self.native.get_position_pulses()}

    @action(name="x-cap.prr8691.move_absolute_pulses.v1", long_running=True, max_duration_ms=60000,
            description="Move to an absolute controller coordinate in pulses (A: then G:)",
            input={"pulses": Field("integer", unit="1",
                                   description="Absolute controller coordinate in pulses",
                                   limit=_POSITION_PULSES)},
            output={
                "position_pulses": Field("integer", unit="1", description="Pulse coordinate reported after the move"),
                "position_mm": Field("number", unit="mm", description="Coordinate reported after the move"),
            })
    def move_absolute_pulses(self, pulses):
        self.native.move_absolute_pulses(pulses)
        return {"position_pulses": self.native.get_position_pulses(),
                "position_mm": self.native.get_position_mm()}

    @action(name="x-cap.prr8691.move_relative_pulses.v1", long_running=True, max_duration_ms=60000,
            description="Move by a signed number of pulses (M: then G:)",
            input={"pulses": Field("integer", unit="1",
                                   description="Signed distance in controller pulses",
                                   limit=_DISTANCE_PULSES)},
            output={
                "position_pulses": Field("integer", unit="1", description="Pulse coordinate reported after the move"),
                "position_mm": Field("number", unit="mm", description="Coordinate reported after the move"),
            })
    def move_relative_pulses(self, pulses):
        self.native.move_relative_pulses(pulses)
        return {"position_pulses": self.native.get_position_pulses(),
                "position_mm": self.native.get_position_mm()}

    @action(name="x-cap.prr8691.home.v1", long_running=True, max_duration_ms=120000,
            description="Run the controller's mechanical-origin search (H:)",
            input={"direction": Field("string", enum=["-", "+"],
                                      description="Search direction: '-' toward the minimum, '+' toward the maximum")},
            output={
                "homed": Field("boolean", description="True once the home search has finished"),
                "position_mm": Field("number", unit="mm", description="Coordinate reported after homing"),
                "position_pulses": Field("integer", unit="1", description="Pulse coordinate reported after homing"),
            })
    def home(self, direction):
        self.native.home(direction)
        return {"homed": True,
                "position_mm": self.native.get_position_mm(),
                "position_pulses": self.native.get_position_pulses()}

    @action(name="x-cap.prr8691.stop_motion.v1", safe_state=True,
            description="Stop motion with the controller's native controlled deceleration (L:)",
            output={"stopped": Field("boolean", description="True once the stop command has been sent")})
    def stop_motion(self):
        self.native.stop()
        return {"stopped": True}

    # -- safety -----------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop (L:): the runtime latches first, then sends the controlled deceleration command."""
        self.native.stop()

    def teardown(self):
        self.native.close()
