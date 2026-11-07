"""OpenMHS driver for gh.avisengine/avis-engine-python-api: the Car client of the AVIS Engine driving simulator.

The upstream class is ``avisengine:Car`` (avisengine.py:17).  A Car is a TCP client of the external AVIS Engine
simulator: ``connect(server, port)`` opens the socket (avisengine.py:58-64), the control methods send a
comma-separated text request (avisengine.py:51 and :92-137), and ``getData`` requests and parses the reply's
``<image>``, ``<sensor>`` and ``<speed>`` tags (avisengine.py:139-176).  The README documents the control ranges
as -100..100 for throttle and steering (README.md:132-133), sensor distances in cm (README.md:102 and :137) and
the current speed in km/h (README.md:107 and :139).

This package serves the simulator as a *simulated* device (task.json safety.expected_mode "simulated"): only the
package's own fake backend is offered (``.fake:FakeCar``), and the external simulator at its documented
127.0.0.1:25001 (README.md:62-63, config.py:5-6) is never contacted.  The fake is an analytic stand-in, not a copy
of the simulator; its fidelity contract lists what it does not model.

Capabilities:

* resource reads: speed (km/h), the three distance sensors (cm), and the last throttle, steering and sensor-angle
  commands; each read refreshes the data with ``Car.getData`` first;
* ``cap.device.configure.v1``: throttle and steering are bounded by the README's -100..100, and the angle between
  sensor rays waits for the site because the clone states no range for it;
* ``cap.motion.stop.v1``: the native ``Car.stop`` (speed and steering 0, the text command "stop", socket closed,
  avisengine.py:206-214); ``Car.stop`` is also the native e-stop.

NOT COVERED: the camera image array returned by ``Car.getImage`` (avisengine.py:179-183); MHS 0.9 carries no image
array field.  The device's scalar telemetry and controls above are served instead.

This package is model-authored and unreviewed: it is checked on the fake backend only, and nothing here ran the
external simulator or a vehicle.  The pinned commit is 32b9a9e063a5608b9b60a87aa32171d44c116316.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write

AVISENGINE = "avisengine.py"
README = "README.md"
EXAMPLE = "example.py"

THROTTLE_REASON = "the README states the throttle range as -100 to 100"
STEERING_REASON = "the README states the steering range as -100 to 100"
SENSOR_ANGLE_REASON = ("the clone states no range for the angle between sensor rays: setSensorAngle accepts any "
                       "angle (avisengine.py:123-137) and example.py:36 only passes 45 degrees, an example value, "
                       "not a bound")


class AvisEngineCar(Driver):
    device_id = "avis-engine-car"
    device_kind = "robot.mobile_base"
    mode = "simulated"
    risk = "R1"
    native = "avisengine:Car"
    backends = {"fake": ".fake:FakeCar"}
    vendor, model = "AVIS Engine", "AVIS Engine simulated car (Python API client)"
    display_name = "AVIS Engine car (avisengine.Car)"
    tags = ["avis-engine", "autonomous-vehicle", "simulator", "car", "mobile-base", "sensor", "telemetry"]
    facts = [
        Fact("The project is a Python API for AVIS Engine, an autonomous-vehicle simulation platform",
             source="vendor_doc", ref=f"{README}:3"),
        Fact("The README's Getting Started section launches the simulator and starts its server (section 1) "
             "before it connects and controls the vehicle (section 2)", source="vendor_doc", ref=f"{README}:56-68"),
        Fact("The simulator's documented default server address is 127.0.0.1 and port 25001",
             source="vendor_doc", ref=f"{README}:62-63"),
        Fact("config.py sets SIMULATOR_IP to 127.0.0.1 and SIMULATOR_PORT to 25001",
             source="upstream_code", ref="config.py:5-6"),
        Fact("AVIS Engine's main class is Car, the object a client instantiates to drive the simulated car",
             source="upstream_code", ref=f"{AVISENGINE}:17"),
        Fact("The Car transport is a TCP socket (AF_INET, SOCK_STREAM)", source="upstream_code",
             ref=f"{AVISENGINE}:47"),
        Fact("The request is a comma-separated text command with Speed, Steering, ImageStatus, SensorStatus, "
             "GetSpeed and SensorAngle fields", source="upstream_code", ref=f"{AVISENGINE}:51"),
        Fact("connect(server, port) connects the socket and sets a 5.0 s socket timeout", source="upstream_code",
             ref=f"{AVISENGINE}:58-64"),
        Fact("setSpeed stores speed_value, disables image and sensor replies, updates the request and sends it",
             source="upstream_code", ref=f"{AVISENGINE}:108-121"),
        Fact("setSteering stores steering_value, disables image and sensor replies, updates the request and sends it",
             source="upstream_code", ref=f"{AVISENGINE}:92-106"),
        Fact("setSensorAngle stores sensor_angle, disables image and sensor replies, updates the request and sends "
             "it", source="upstream_code", ref=f"{AVISENGINE}:123-137"),
        Fact("getData requests image, sensor and speed data and parses the <image>, <sensor> and <speed> tags of "
             "the reply", source="upstream_code", ref=f"{AVISENGINE}:139-176"),
        Fact("getSensors returns the three distance readings as a list [left, middle, right]", source="upstream_code",
             ref=f"{AVISENGINE}:185-191"),
        Fact("getSpeed returns current_speed", source="upstream_code", ref=f"{AVISENGINE}:193-197"),
        Fact("getData decodes the reply's <image> payload from base64 and OpenCV into self.image",
             source="upstream_code", ref=f"{AVISENGINE}:154-160"),
        Fact("getImage returns self.image, the image the client stored", source="upstream_code",
             ref=f"{AVISENGINE}:179-183"),
        Fact("stop sets speed and steering to 0, sends the text command 'stop' and closes the socket",
             source="upstream_code", ref=f"{AVISENGINE}:206-214"),
        Fact("The README documents the throttle range as -100 to 100", source="vendor_doc", ref=f"{README}:132"),
        Fact("The README documents the steering range as -100 to 100", source="vendor_doc", ref=f"{README}:133"),
        Fact("The README documents sensor distances in cm", source="vendor_doc", ref=f"{README}:102"),
        Fact("The README documents the current speed in km/h", source="vendor_doc", ref=f"{README}:107"),
        Fact("The README documents getSensors as [left, middle, right] distances in cm and getSpeed as km/h",
             source="vendor_doc", ref=f"{README}:137-139"),
        Fact("The example comment calls setSteering a steering angle in degrees", source="upstream_code",
             ref=f"{EXAMPLE}:33"),
        Fact("The example sets the angle between sensor rays to 45 degrees, once from the client",
             source="upstream_code", ref=f"{EXAMPLE}:36-38"),
        Fact("The example returns three sensor values and an integer speed in KMH", source="upstream_code",
             ref=f"{EXAMPLE}:48-56"),
        Fact("The README's license section says MIT License and refers to a LICENSE file", source="vendor_doc",
             ref=f"{README}:208-210"),
    ]
    safe_state = ("the car is stopped: speed and steering are set to 0 and the simulator's stop command is sent "
                  "(Car.stop), which closes the client connection")
    #: The model as deployed (spec 05-fidelity section 2): a synchronous analytic stand-in, never the Unity simulator.
    fidelity = {
        "engine": "analytic",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "exact",
            "notes": "the fake keeps plain attributes and has no random source; the same command sequence gives the "
                     "same state, while the external simulator's own state depends on its scene and physics",
        },
        "timestep_ms": 0.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is an in-process stand-in for Car, not the AVIS Engine simulator: it has no Unity scene, "
            "track, traffic, vehicle dynamics, collision or physics and no wall-clock pacing",
            "NOT COVERED: the camera image array returned by Car.getImage(); no capability returns it, and its "
            "real base64/OpenCV payload is not modelled",
            "the three distance readings and the speed are placeholders that change only with the throttle, "
            "steering and sensor-angle commands; no ray casting or vehicle motion is computed",
            "no socket, <EOF> framing, image decoding or 5.0 s receive timeout: the fake never contacts the "
            "documented simulator address 127.0.0.1:25001",
            "the fake's stop only zeroes the commands and records the stop; unlike Car.stop it does not close a "
            "connection, and the external simulator is never run or compared with the fake",
        ],
    }

    # -- reads ---------------------------------------------------------------------------------------------------
    @read("speed", type="integer", unit="km/h",
          description="Current car speed in km/h, refreshed from the simulator by getData")
    def speed(self):
        self.native.getData()
        return self.native.getSpeed()

    @read("sensors", type="array", items="integer", length=3, unit="cm",
          description="Distance readings of the left, middle and right sensors in cm, refreshed by getData")
    def sensors(self):
        self.native.getData()
        return list(self.native.getSensors())

    @read("throttle", type="integer", unit="1",
          description="Last throttle command in the simulator's -100..100 scale; the clone states no physical unit")
    def throttle(self):
        return self.native.speed_value

    @read("steering", type="integer", unit="deg", description="Last steering command, in degrees from centre")
    def steering(self):
        return self.native.steering_value

    @read("sensor_angle", type="integer", unit="deg",
          description="Angle between adjacent sensor rays set by setSensorAngle, in degrees")
    def sensor_angle(self):
        return self.native.sensor_angle

    # -- writes --------------------------------------------------------------------------------------------------
    @write("throttle", type="integer", unit="1",
           description="Throttle command in the simulator's -100..100 scale; negative drives in reverse",
           limit=Limit(min=-100, max=100, unit="1", source="vendor_doc", ref=f"{README}:132",
                       reason=THROTTLE_REASON))
    def set_throttle(self, value):
        self.native.setSpeed(value)

    @write("steering", type="integer", unit="deg", description="Steering angle in degrees from centre, -100..100",
           limit=Limit(min=-100, max=100, unit="deg", source="vendor_doc", ref=f"{README}:133",
                       reason=STEERING_REASON))
    def set_steering(self, value):
        self.native.setSteering(value)

    @write("sensor_angle", type="integer", unit="deg",
           description="Angle between adjacent sensor rays, in degrees",
           limit=Limit.operator_required(SENSOR_ANGLE_REASON))
    def set_sensor_angle(self, value):
        self.native.setSensorAngle(value)

    # -- stop ----------------------------------------------------------------------------------------------------
    @action(cap="cap.motion.stop.v1",
            description="Stop the car with the simulator's own stop command (speed and steering 0, then stop)",
            input={"deceleration": Field(
                unit="m/s2",
                description="Accepted for the class signature only; the simulator's stop command takes no "
                            "deceleration argument and the clone states no deceleration range")})
    def stop_motion(self, deceleration=None):
        self.native.stop()
        return {"stopped": True}

    @estop(native="stop")
    def emergency_stop(self):
        """The native stop: Car.stop sets speed and steering to 0, sends "stop" and closes the socket."""
        self.native.stop()
