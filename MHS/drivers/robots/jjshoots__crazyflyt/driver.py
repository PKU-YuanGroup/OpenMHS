"""OpenMHS driver for gh.jjshoots/crazyflyt: a Crazyflie 2.x quadcopter over CrazyFlyt.drone_controller:DroneController.

A direct Driver over the upstream class.  The class keeps two four-number arrays: ``setpoint``, which is
``(x, y, z, yaw)`` in position control and ``(vx, vy, vz, vyaw)`` in velocity control (drone_controller.py:102-108),
and ``position_estimate``, filled by the firmware log callback (drone_controller.py:144-147).  A background thread
sends the current setpoint to the flight controller every 1/40 s while ``running`` is true, and the stop setpoint
while it is false (drone_controller.py:118-133).  The driver exposes:

* reads: the state estimate, the stored setpoint, the position-control flag and the running flag;
* a writable ``pos_control`` flag (``cap.device.configure.v1``), which calls ``set_pos_control``;
* ``x-cap.jjshoots.position_setpoint.v1``: store an ``(x, y, z, yaw)`` setpoint, select position control and start;
* ``x-cap.jjshoots.velocity_setpoint.v1``: store a ``(vx, vy, vz, vyaw)`` setpoint, select velocity control and
  start;
* ``x-cap.jjshoots.halt.v1`` (safe state): call the native ``stop``, after which the control thread sends the stop
  setpoint;
* the native ``stop`` as the e-stop.

The clone states no envelope for any setpoint value: the numbers are passed to the flight controller and the source
only fixes the four-value layout.  Every motion input is therefore ``Limit.operator_required`` and refused with
``MHS.SAFETY.LIMITS_UNSET`` until a site overlay supplies its bound (``site-limits.example.json`` shows the form).
The clone documents no independent hardware e-stop; the e-stop and the safe-state action are the software stop path
``stop()``, and ``safe_state`` says exactly that.  Because the device moves in the air it is R2.

This package is model-authored and unreviewed: the acceptance gate checks it on the fake backend only, and the loader
refuses its hardware backend (R2) until a human signs ``reviewed_by`` in driver.lock.json.  Nothing here ran on a
drone.  The pinned commit is 85d99afa21cb5b90fd130cd480f0589a2b700b58.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write

POSITION_REASON = ("the clone states no position envelope for the Crazyflie: the setpoint is passed to the flight "
                   "controller, so the site sets the allowed value")
VELOCITY_REASON = ("the clone states no velocity envelope for the Crazyflie: the setpoint is passed to "
                   "send_velocity_world_setpoint, so the site sets the allowed value")
YAW_REASON = "the clone states no yaw envelope; the site sets the allowed value"
YAW_RATE_REASON = "the clone states no yaw-rate envelope; the site sets the allowed value"


def _setpoint_output(properties):
    """The output object shared by the two setpoint actions."""
    return {
        "setpoint": Field("object", description="The four values handed to native set_setpoint", properties=properties),
        "running": Field("boolean", description="running after the action; the control thread now sends the setpoint"),
    }


class Crazyflie(Driver):
    device_id = "crazyflie"
    device_kind = "robot.mobile_base"
    mode = "hardware"
    risk = "R2"
    native = "CrazyFlyt.drone_controller:DroneController"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeDroneController"}
    vendor = "Bitcraze"
    model = "Crazyflie 2.x"
    display_name = "Crazyflie 2.x (CrazyFlyt DroneController)"
    tags = ["drone", "uav", "crazyflie", "position control", "velocity control", "flight"]
    facts = [
        Fact("The library is for flying real CrazyFlie 2.x drones, with a simulation environment via PyFlyt",
             source="vendor_doc", ref="readme.md:5"),
        Fact("The upstream README says the library is in the developmental stage", source="vendor_doc",
             ref="readme.md:3"),
        Fact("The hardware example opens a DroneController on a radio URI, selects position control, starts it, "
             "sends a hover setpoint at 0.5 m and then 0 m, stops it and ends it", source="upstream_code",
             ref="examples/fly_single.py:25-44"),
        Fact("The hardware example sends the setpoint [0.0, 0.0, 0.5, 0.0] to hover at 0.5 m",
             source="upstream_code", ref="examples/fly_single.py:31-32"),
        Fact("The setpoint is four numbers: (x, y, z, yaw) in position control or (vx, vy, vz, vyaw) in velocity "
             "control", source="upstream_code", ref="CrazyFlyt/drone_controller.py:102-108"),
        Fact("The control thread repeats every period = 1/40.0 s", source="upstream_code",
             ref="CrazyFlyt/drone_controller.py:29"),
        Fact("With running true, the control thread sends a position setpoint when pos_control is true and a "
             "world-frame velocity setpoint otherwise", source="upstream_code",
             ref="CrazyFlyt/drone_controller.py:120-129"),
        Fact("The control thread multiplies the four-value setpoint by self.rad_to_deg before sending it",
             source="upstream_code", ref="CrazyFlyt/drone_controller.py:120-129"),
        Fact("rad_to_deg is [1.0, 1.0, 1.0, math.pi / 180.0], so only the fourth value is converted from radians to "
             "degrees and the first three are passed unchanged", source="upstream_code",
             ref="CrazyFlyt/drone_controller.py:39"),
        Fact("When running is false the control thread calls send_stop_setpoint every period", source="upstream_code",
             ref="CrazyFlyt/drone_controller.py:130-133"),
        Fact("start() sets running true, stop() sets running false, and end() clears running, stops the logging "
             "configuration and closes the link", source="upstream_code",
             ref="CrazyFlyt/drone_controller.py:80-92"),
        Fact("position_estimate holds the logged stateEstimate.x, .y and .z and the yaw converted from degrees to "
             "radians", source="upstream_code", ref="CrazyFlyt/drone_controller.py:144-147"),
        Fact("position_estimate and setpoint are four-element numpy arrays initialised to zero", source="upstream_code",
             ref="CrazyFlyt/drone_controller.py:35-36"),
        Fact("The velocity example describes the setpoint [1.0, 0.0, 0.0, 1.0] as flying in horizontal x with a "
             "1 rad/s yaw rate", source="upstream_code", ref="examples/sim_swarm.py:45-50"),
        Fact("The constructor opens a SyncCrazyflie link and starts a daemon control thread", source="upstream_code",
             ref="CrazyFlyt/drone_controller.py:42-73"),
    ]
    safe_state = ("running is false, so the control thread calls send_stop_setpoint every period; the radio link "
                  "stays open and this is not a power cut")
    #: No independent hardware e-stop occurs in the clone; SAFE-045 is met by the safe-state action below.

    # -- reads ------------------------------------------------------------------------------------------------
    @read("position_estimate", type="object",
          description="Last state estimate logged from the flight controller: x, y and z in m, yaw in rad",
          properties={
              "x": Field("number", unit="m", description="stateEstimate.x"),
              "y": Field("number", unit="m", description="stateEstimate.y"),
              "z": Field("number", unit="m", description="stateEstimate.z"),
              "yaw": Field("number", unit="rad", description="stateEstimate.yaw converted from degrees to radians"),
          })
    def get_position_estimate(self):
        x, y, z, yaw = (float(value) for value in self.native.position_estimate)
        return {"x": x, "y": y, "z": z, "yaw": yaw}

    @read("setpoint", type="array", items="number", length=4,
          description="Four numbers last passed to set_setpoint: x, y, z, yaw in position control or vx, vy, vz, "
                      "vyaw in velocity control")
    def get_setpoint(self):
        return [float(value) for value in self.native.setpoint]

    @read("pos_control", type="boolean",
          description="True when the setpoint is sent with send_position_setpoint, false for the world-frame "
                      "velocity setpoint")
    def get_pos_control(self):
        return bool(self.native.pos_control)

    @read("running", type="boolean",
          description="True while the control thread sends the stored setpoint instead of the stop setpoint")
    def get_running(self):
        return bool(self.native.running)

    # -- writable state ---------------------------------------------------------------------------------------
    @write("pos_control", type="boolean",
           description="Select position control (true) or world-frame velocity control (false) for the stored "
                       "setpoint")
    def set_pos_control(self, value):
        self.native.set_pos_control(bool(value))

    # -- motion ------------------------------------------------------------------------------------------------
    @action(name="x-cap.jjshoots.position_setpoint.v1",
            description="Store an (x, y, z, yaw) setpoint in m and rad, select position control and start the "
                        "control thread",
            input={
                "x": Field("number", unit="m", description="Target x in the world frame",
                           limit=Limit.operator_required(POSITION_REASON)),
                "y": Field("number", unit="m", description="Target y in the world frame",
                           limit=Limit.operator_required(POSITION_REASON)),
                "z": Field("number", unit="m", description="Target z in the world frame",
                           limit=Limit.operator_required(POSITION_REASON)),
                "yaw": Field("number", unit="rad", description="Target yaw in rad",
                             limit=Limit.operator_required(YAW_REASON)),
            },
            output=_setpoint_output({
                "x": Field("number", unit="m", description="x handed to set_setpoint"),
                "y": Field("number", unit="m", description="y handed to set_setpoint"),
                "z": Field("number", unit="m", description="z handed to set_setpoint"),
                "yaw": Field("number", unit="rad", description="yaw handed to set_setpoint"),
            }))
    def set_position_setpoint(self, x, y, z, yaw):
        # Stop the thread first: a setpoint stored while the previous mode is still selected would be sent once under
        # the other interpretation (a position read as a velocity or the reverse).
        self.native.stop()
        self.native.set_pos_control(True)
        self.native.set_setpoint([x, y, z, yaw])
        self.check_cancelled()
        self.native.start()
        return {"setpoint": {"x": x, "y": y, "z": z, "yaw": yaw}, "running": True}

    @action(name="x-cap.jjshoots.velocity_setpoint.v1",
            description="Store a (vx, vy, vz, vyaw) world-frame velocity setpoint, select velocity control and "
                        "start the control thread; the clone states no velocity unit, so vx, vy and vz are "
                        "dimensionless upstream values",
            input={
                "vx": Field("number", unit="1",
                            description="Value for send_velocity_world_setpoint's first argument; the clone does "
                                        "not state its unit",
                            limit=Limit.operator_required(VELOCITY_REASON)),
                "vy": Field("number", unit="1",
                            description="Value for send_velocity_world_setpoint's second argument; the clone does "
                                        "not state its unit",
                            limit=Limit.operator_required(VELOCITY_REASON)),
                "vz": Field("number", unit="1",
                            description="Value for send_velocity_world_setpoint's third argument; the clone does "
                                        "not state its unit",
                            limit=Limit.operator_required(VELOCITY_REASON)),
                "yaw_rate": Field("number", unit="rad/s",
                                  description="Yaw rate in rad/s; the control thread converts the fourth value to "
                                              "degrees",
                                  limit=Limit.operator_required(YAW_RATE_REASON)),
            },
            output=_setpoint_output({
                "vx": Field("number", unit="1", description="vx handed to set_setpoint"),
                "vy": Field("number", unit="1", description="vy handed to set_setpoint"),
                "vz": Field("number", unit="1", description="vz handed to set_setpoint"),
                "yaw_rate": Field("number", unit="rad/s", description="vyaw handed to set_setpoint"),
            }))
    def set_velocity_setpoint(self, vx, vy, vz, yaw_rate):
        self.native.stop()
        self.native.set_pos_control(False)
        self.native.set_setpoint([vx, vy, vz, yaw_rate])
        self.check_cancelled()
        self.native.start()
        return {"setpoint": {"vx": vx, "vy": vy, "vz": vz, "yaw_rate": yaw_rate}, "running": True}

    # -- safety ------------------------------------------------------------------------------------------------
    @action(name="x-cap.jjshoots.halt.v1", safe_state=True,
            description="Stop commanding motion: call the native stop, so the control thread sends the stop setpoint",
            output={"stop_requested": Field("boolean",
                                            description="True once the native stop was called")})
    def halt(self):
        self.native.stop()
        return {"stop_requested": True}

    @estop(native="stop")
    def emergency_stop(self):
        """The native stop: the runtime latches first, then running is cleared and stop setpoints are sent."""
        self.native.stop()

    def teardown(self):
        self.native.end()
