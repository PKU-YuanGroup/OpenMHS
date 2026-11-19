"""OpenMHS driver for gh.cvzone/pysimverse: the simulated Drone publisher of the pysimverse drone simulator.

The upstream class is a ZeroMQ client, not a Gymnasium environment.  ``Drone`` builds a PUB socket for RC commands
(``simulators/drone/drone.py:24-25``) and SUB sockets for state and video (``drone.py:28-33``), and publishes a JSON
object with the left/right, forward/backward, up/down and yaw axes plus a camera angle (``drone.py:78-91``).  The
``move_*``, ``rotate``, ``rotate_camera``, ``take_off`` and ``land`` methods emit a nonzero command, sleep for the
duration the distance and speed imply, and then emit a zero command (``drone.py:166-171``, ``220-227``, ``231-237``,
``241-249``, ``253-257``).  This package keeps that primary control interface and records the commands on the fake
backend; the clone ships no simulator server, so the ZMQ peer at the other end is not reproduced.

The card names ``PythonObjectDriver``.  That family is a flat command table and cannot express the multi-part native
motions above (a nonzero RC command, a native sleep, a zero RC command) or the direction dispatch; this package is a
direct ``Driver`` instead.  The class is simulated and model-authored; only the fake backend exists, so no hardware
backend, no upstream ZMQ server and no hardware run is claimed.  The upstream README is only a title
(``README.md:1``), so no vendor text documents units, ranges or a safety function.  Every numeric input is therefore
``Limit.operator_required`` and the example site overlay supplies test bounds for the conformance run.

Model review blocks this package with HELPER_MISSING. The e-stop attempts the native zero RC call and then raises
SAFE_STATE_UNREACHED: the PUB send has no acknowledgement, catches publish errors and returns None. The absent peer's
interpretation of a zero command is unknown. The ordinary stop action reports only that the call was requested and
is not a safe-state action. The runtime latch stays held until an explicit reset; that reset does not confirm recovery or resume motion. Native motion sleeps
are uninterruptible, an admission race can send motion after an e-stop, and a sleep exception can skip the final zero
command. The instant fake cannot establish live timing, delivery, hovering or landing. No live backend is declared.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

DRONE = "simulators/drone/drone.py"
MANAGER = "simulators/drone/drone_manager.py"

#: Runtime execution bound for one motion action, in milliseconds.  It is not a device or safety limit: the upstream
#: computes its own sleep as distance/speed or height/speed (drone.py:169, 224) and states no maximum.
EXECUTION_BOUND_MS = 300000

HEIGHT_REASON = ("the clone states no takeoff-height range: take_off takes takeoff_height with a constructor-style "
                 "default and computes takeoff_height / takeoff_speed (drone.py:220-225); the site sets the bound")
TAKEOFF_SPEED_REASON = ("the clone states no takeoff-speed range: take_off takes takeoff_speed and divides the height "
                        "by it (drone.py:220-225); the site sets the bound")
LANDING_SPEED_REASON = ("the clone states no landing-speed range: land takes landing_speed and sends it as the down "
                        "axis (drone.py:231-237); the site sets the bound")
DISTANCE_REASON = ("the clone states no distance range: every move_* method divides distance by the current speed to "
                   "get a sleep duration (drone.py:166-171); the site sets the bound")
ANGLE_REASON = ("the clone states no angle range: rotate divides the angle by 60 for its sleep and uses "
                "rotation_speed / 70 as the yaw value (drone.py:241-249); the site sets the bound")
CAMERA_ANGLE_REASON = ("the clone states no camera-angle range: rotate_camera sends the angle as cameraangle and "
                       "divides it by 40 for its sleep (drone.py:253-257); the site sets the bound")
SPEED_REASON = ("the clone states no RC speed range: the constructor only sets speed=300 (drone.py:11), set_speed "
                "assigns its argument unchanged (drone.py:261-262) and the motion methods divide the distance by it; "
                "the site sets the bound")
ROTATION_SPEED_REASON = ("the clone states no rotation-speed range: the constructor only sets rotation_speed=15 "
                         "(drone.py:11) and set_rotation_speed assigns its argument unchanged (drone.py:264-265); "
                         "the site sets the bound")


class PysimverseDrone(Driver):
    device_id = "pysimverse-drone"
    device_kind = "robot.mobile_base"
    mode = "simulated"
    #: A drone in flight is a mobile base (MHS-004 section 2.1).  The device is simulated, so there is no physical
    #: e-stop; the unacknowledged zero-RC request does not establish a safe state.
    risk = "R2"
    native = "pysimverse.simulators.drone.drone:Drone"
    backends = {"fake": ".fake:FakeDrone"}
    vendor, model = "cvzone", "pysimverse simulated drone"
    display_name = "cvzone pysimverse Drone (ZeroMQ RC publisher)"
    tags = ["drone", "simulation", "zeromq", "rc control", "mobile base", "pysimverse"]
    facts = [
        Fact("The upstream README contains only the project title and no usage, unit, range or safety text",
             source="vendor_doc", ref="README.md:1"),
        Fact("The package exports Drone and DroneManager from pysimverse.simulators.drone",
             source="upstream_code", ref="__init__.py:1-2"),
        Fact("The Drone constructor takes host='*', cmd_port=5550, state_port=5556, video_port=5557, speed=300 and "
             "rotation_speed=15", source="upstream_code", ref=f"{DRONE}:11"),
        Fact("The constructor sets command_address to tcp://{host}:{cmd_port}, state_address to "
             "tcp://localhost:{state_port} and video_address to tcp://localhost:{video_port}",
             source="upstream_code", ref=f"{DRONE}:24-33"),
        Fact("connect() binds the command socket, connects and subscribes the state and video sockets and sleeps "
             "0.25 s", source="upstream_code", ref=f"{DRONE}:43-60"),
        Fact("send_rc_control publishes a JSON object with left_right, forward_backward, up_down, yaw, cameraangle, "
             "streamon and a red/green/blue color object", source="upstream_code", ref=f"{DRONE}:72-91"),
        Fact("send_rc_control catches every exception, prints it and returns, so a failed publish has no error value",
             source="upstream_code", ref=f"{DRONE}:93-94"),
        Fact("streamon and streamoff assign self.stream_on and publish it with all motion axes None",
             source="upstream_code", ref=f"{DRONE}:96-102"),
        Fact("Each move_* method acts only while is_flying is true, otherwise it prints 'Take off the drone first.'",
             source="upstream_code", ref=f"{DRONE}:166-218"),
        Fact("move_forward publishes the current speed on the forward axis, sleeps distance / speed and then publishes "
             "a zero command", source="upstream_code", ref=f"{DRONE}:166-171"),
        Fact("move_backward, move_right, move_left, move_up and move_down mirror move_forward with the opposite sign or "
             "another axis", source="upstream_code", ref=f"{DRONE}:175-218"),
        Fact("take_off sets is_flying true, publishes takeoff_speed on the up axis, sleeps "
             "takeoff_height / takeoff_speed and then publishes a zero command", source="upstream_code",
             ref=f"{DRONE}:220-227"),
        Fact("land publishes -landing_speed on the up axis, sleeps 3 s, publishes a zero command and sets is_flying "
             "false", source="upstream_code", ref=f"{DRONE}:231-237"),
        Fact("rotate publishes rotation_speed / 70 on the yaw axis with the sign of the angle, sleeps abs(angle / 60) "
             "and then publishes a zero command", source="upstream_code", ref=f"{DRONE}:241-249"),
        Fact("rotate_camera publishes the angle as cameraangle, sleeps abs(angle / 40) and then publishes a zero "
             "command", source="upstream_code", ref=f"{DRONE}:253-257"),
        Fact("set_speed and set_rotation_speed assign their argument to the corresponding attribute",
             source="upstream_code", ref=f"{DRONE}:261-265"),
        Fact("get_battery receives and prints the state message, parses it as a float and sleeps 1 s, but never "
             "returns the parsed value and catches only KeyboardInterrupt", source="upstream_code",
             ref=f"{DRONE}:152-164"),
        Fact("get_frame calls self.fpsReader.update when a frame is available",
             source="upstream_code", ref=f"{DRONE}:123-130"),
        Fact("get_frame catches exceptions, prints the error and returns frame and is_success",
             source="upstream_code", ref=f"{DRONE}:134-139"),
        Fact("shutdown closes the command, state and video sockets, terminates the context and calls "
             "cv2.destroyAllWindows", source="upstream_code", ref=f"{DRONE}:141-150"),
        Fact("DroneManager.create_drones connects, publishes the drone count, reads a port list and constructs one "
             "Drone per port", source="upstream_code", ref=f"{MANAGER}:64-72"),
        Fact("DroneManager.takeoff_all_drones starts one thread per drone and calls take_off with 300",
             source="upstream_code", ref=f"{MANAGER}:89-116"),
    ]
    safe_state = ("unconfirmed: a zero RC publish is attempted, but the clone supplies no acknowledgement or "
                  "stopped-state read-back and suppresses send errors; the latch refuses new commands, while the "
                  "external simulator may continue moving; e-stop reports SAFE_STATE_UNREACHED and recovery "
                  "requires a reviewed stop/confirmation path outside this package")
    fidelity = {
        "engine": "analytic",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "the fake is a deterministic command recorder with no time advance and no randomness; one call "
                     "sequence always gives the same recorded commands",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the checked fake is an in-memory command recorder, not the upstream ZMQ simulator peer: it sends no "
            "traffic, models no flight dynamics, position, battery, video, wind or timing, and was never compared "
            "with the simulator that the clone's PUB/SUB client expects",
            "the upstream methods sleep for the duration computed from distance/speed, height/speed, abs(angle/60), "
            "abs(angle/40) or 3 s for land (drone.py:169, 224, 234, 248, 256); the fake returns immediately and "
            "records only the command pair",
            "the clone ships no simulator server, so the live peer, pyzmq, OpenCV and NumPy dependencies and the "
            "recorded F0 timing were not run",
            "get_battery (drone.py:152-164) never returns its parsed value, so battery telemetry is not covered",
            "get_frame (drone.py:104-139) calls an undefined fpsReader but catches the exception and may return "
            "a frame with is_success already true; video capture is not covered",
            "DroneManager's handshake and fleet takeoff (drone_manager.py:41-116) are not covered by this package",
            "the fake does not simulate the native time.sleep, so an action's wall-clock duration is not modelled",
            "zero RC is an unacknowledged request, not a confirmed stop; send_rc_control suppresses errors and "
            "the clone contains no simulator-side consumer; the package is blocked with HELPER_MISSING",
            "native methods print to stdout, which would interfere with a stdio endpoint; live construction "
            "opens ZeroMQ sockets and shutdown can wait on socket/context cleanup; no live factory is declared",
        ],
    }

    def setup(self):
        """Open the native ZMQ sockets the upstream class expects; the fake only records the call."""
        self.native.connect()

    def teardown(self):
        """Close the native sockets; the fake only clears its connection flag."""
        self.native.shutdown()

    # -- reads ---------------------------------------------------------------------------------------------------
    @read("is_flying", type="boolean", description="True while the drone is airborne according to the simulator")
    def get_is_flying(self):
        return bool(self.native.is_flying)

    @read("speed", type="number",
          description="RC speed used by the move_* methods; the clone states no unit or range")
    def get_speed(self):
        return float(self.native.speed)

    @read("rotation_speed", type="number",
          description="Rotation speed used by rotate; the clone states no unit or range")
    def get_rotation_speed(self):
        return float(self.native.rotation_speed)

    @read("stream_on", type="boolean", description="True after streamon and false after streamoff")
    def get_stream_on(self):
        return bool(self.native.stream_on)

    # -- writes --------------------------------------------------------------------------------------------------
    @write("speed", type="number", description="RC speed used by the move_* methods",
           limit=Limit.operator_required(SPEED_REASON))
    def set_speed(self, value):
        self.native.set_speed(value)
        return value

    @write("rotation_speed", type="number", description="Rotation speed used by rotate",
           limit=Limit.operator_required(ROTATION_SPEED_REASON))
    def set_rotation_speed(self, value):
        self.native.set_rotation_speed(value)
        return value

    # -- motion --------------------------------------------------------------------------------------------------
    @action(name="x-cap.cvzone.takeoff.v1", long_running=True, max_duration_ms=EXECUTION_BOUND_MS,
            cancellable=True,
            description="Take off to the given native height at the given native speed; the native method publishes "
                        "an up command, sleeps height / speed and then publishes a zero command",
            input={
                "takeoff_height": Field("number",
                                        description="Takeoff height in the clone's native units (no unit stated)",
                                        limit=Limit.operator_required(HEIGHT_REASON)),
                "takeoff_speed": Field("number",
                                       description="Up-axis takeoff speed in the clone's native units (no unit stated)",
                                       limit=Limit.operator_required(TAKEOFF_SPEED_REASON)),
            },
            output={
                "is_flying": Field("boolean", description="True after the native take_off call"),
                "takeoff_height": Field("number", description="Height sent to the native method"),
                "takeoff_speed": Field("number", description="Speed sent to the native method"),
                "applied": Field("boolean", description="False when the drone was already flying"),
            })
    def takeoff(self, takeoff_height, takeoff_speed):
        was_flying = bool(self.native.is_flying)
        self.check_cancelled()
        self.native.take_off(takeoff_height=takeoff_height, takeoff_speed=takeoff_speed)
        self.check_cancelled()
        return {"is_flying": bool(self.native.is_flying), "takeoff_height": takeoff_height,
                "takeoff_speed": takeoff_speed, "applied": not was_flying}

    @action(name="x-cap.cvzone.land.v1", long_running=True, max_duration_ms=EXECUTION_BOUND_MS,
            cancellable=True,
            description="Land at the given native speed; the native method publishes a down command, sleeps its fixed "
                        "3 s, publishes a zero command and clears is_flying",
            input={
                "landing_speed": Field("number",
                                       description="Down-axis landing speed in the clone's native units (no unit stated)",
                                       limit=Limit.operator_required(LANDING_SPEED_REASON)),
            },
            output={
                "is_flying": Field("boolean", description="False after the native land call"),
                "landing_speed": Field("number", description="Speed sent to the native method"),
                "applied": Field("boolean", description="False when the drone was already on the ground"),
            })
    def land(self, landing_speed):
        was_flying = bool(self.native.is_flying)
        self.check_cancelled()
        self.native.land(landing_speed=landing_speed)
        self.check_cancelled()
        return {"is_flying": bool(self.native.is_flying), "landing_speed": landing_speed, "applied": was_flying}

    @action(name="x-cap.cvzone.move.v1", long_running=True, max_duration_ms=EXECUTION_BOUND_MS,
            cancellable=True,
            description="Move one native axis by a distance at the current native speed; the native method publishes "
                        "the direction command, sleeps distance / speed and then publishes a zero command",
            input={
                "direction": Field("string", description="Native motion method to call",
                                   enum=["forward", "backward", "right", "left", "up", "down"]),
                "distance": Field("number",
                                  description="Distance in the clone's native units (no unit stated)",
                                  limit=Limit.operator_required(DISTANCE_REASON)),
            },
            output={
                "direction": Field("string", description="Direction that was asked for"),
                "distance": Field("number", description="Distance sent to the native method"),
                "is_flying": Field("boolean", description="The simulator's flying state after the call"),
                "applied": Field("boolean", description="False when the drone was not flying and the native method "
                                                        "would only print its precondition message"),
            })
    def move(self, direction, distance):
        was_flying = bool(self.native.is_flying)
        self.check_cancelled()
        if was_flying:
            if direction == "forward":
                self.native.move_forward(distance)
            elif direction == "backward":
                self.native.move_backward(distance)
            elif direction == "right":
                self.native.move_right(distance)
            elif direction == "left":
                self.native.move_left(distance)
            elif direction == "up":
                self.native.move_up(distance)
            elif direction == "down":
                self.native.move_down(distance)
            else:
                raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", f"unknown direction {direction!r}")
        self.check_cancelled()
        return {"direction": direction, "distance": distance, "is_flying": bool(self.native.is_flying),
                "applied": was_flying}

    @action(name="x-cap.cvzone.rotate.v1", long_running=True, max_duration_ms=EXECUTION_BOUND_MS,
            cancellable=True,
            description="Rotate by an angle at the current native rotation speed; the native method publishes a yaw "
                        "command, sleeps abs(angle / 60) and then publishes a zero command",
            input={
                "angle": Field("number",
                               description="Angle in the clone's native units (no unit stated)",
                               limit=Limit.operator_required(ANGLE_REASON)),
            },
            output={
                "angle": Field("number", description="Angle sent to the native method"),
                "is_flying": Field("boolean", description="The simulator's flying state after the call"),
                "applied": Field("boolean", description="False when the drone was not flying"),
            })
    def rotate(self, angle):
        was_flying = bool(self.native.is_flying)
        self.check_cancelled()
        if was_flying:
            self.native.rotate(angle)
        self.check_cancelled()
        return {"angle": angle, "is_flying": bool(self.native.is_flying), "applied": was_flying}

    @action(name="x-cap.cvzone.rotate_camera.v1", long_running=True, max_duration_ms=EXECUTION_BOUND_MS,
            cancellable=True,
            description="Rotate the camera by an angle; the native method publishes the camera angle, sleeps "
                        "abs(angle / 40) and then publishes a zero command",
            input={
                "angle": Field("number",
                               description="Camera angle in the clone's native units (no unit stated)",
                               limit=Limit.operator_required(CAMERA_ANGLE_REASON)),
            },
            output={
                "angle": Field("number", description="Camera angle sent to the native method"),
                "is_flying": Field("boolean", description="The simulator's flying state after the call"),
                "applied": Field("boolean", description="False when the drone was not flying"),
            })
    def rotate_camera(self, angle):
        was_flying = bool(self.native.is_flying)
        self.check_cancelled()
        if was_flying:
            self.native.rotate_camera(angle)
        self.check_cancelled()
        return {"angle": angle, "is_flying": bool(self.native.is_flying), "applied": was_flying}

    @action(name="x-cap.cvzone.stream_on.v1", cancellable=True,
            description="Turn the simulator's video stream on with the native streamon method",
            output={"stream_on": Field("boolean", description="The native stream_on flag after the call")})
    def stream_on(self):
        self.check_cancelled()
        self.native.streamon()
        self.check_cancelled()
        return {"stream_on": bool(self.native.stream_on)}

    @action(name="x-cap.cvzone.stream_off.v1", cancellable=True,
            description="Turn the simulator's video stream off with the native streamoff method",
            output={"stream_on": Field("boolean", description="The native stream_on flag after the call")})
    def stream_off(self):
        self.check_cancelled()
        self.native.streamoff()
        self.check_cancelled()
        return {"stream_on": bool(self.native.stream_on)}

    # -- safety --------------------------------------------------------------------------------------------------
    @estop(native="send_rc_control")
    def stop(self):
        """Attempt zero RC, then refuse confirmation: the upstream has no acknowledgement."""
        self.native.send_rc_control(0, 0, 0, 0, 0)
        raise DriverFailed("MHS.SAFETY.SAFE_STATE_UNREACHED",
                           "zero RC has no acknowledgement and upstream suppresses publish errors")

    @action(name="x-cap.cvzone.stop.v1",
            description="Attempt a zero RC publish; the return confirms neither delivery nor a stopped simulator",
            output={"requested": Field("boolean", description="The native zero-RC call returned; delivery is unknown")})
    def stop_motion(self):
        self.native.send_rc_control(0, 0, 0, 0, 0)
        return {"requested": True}
