"""OpenMHS driver for gh.machines-in-motion/go2py: a Unitree Go2 quadruped over Go2Py.robot.interface:GO2Real.

A direct Driver over the upstream Python object.  GO2Real reads the robot state from a CycloneDDS DataReader and
writes low-level joint commands and high-level body-velocity commands through two DataWriters
(Go2Py/robot/interface.py:59-70).  The clone never talks to the robot from Python: the C++ bridge
(deploy/ros2_nodes/go2py_bridge) forwards the topics to the robot's Unitree topics and handles the wireless
remote's emergency stop (README.md:10, bridge.cpp:234-243).

* reads: joint angles, velocities, estimated torques and motor temperatures; IMU acceleration, angular velocity,
  quaternion and temperature; raw foot contact values and battery state of charge;
* ``cap.motion.stop.v1``: the stop the Python interface can send, zero body velocity through setCommandsHigh (the
  bridge turns it into Move(0, 0, 0), bridge.cpp:278-287) and the low-level damping command of the bridge's own
  e-stop, q 0, kp 0, dq 0, kd 3, tau 0 (bridge.cpp:317-333).  The bridge's e-stop also sends a sport-mode Damp
  request, which the high-level message (v_x, v_y, omega_z only, interface.py:163-171) cannot carry;
* ``x-cap.machines-in-motion.go2_body_velocity.v1``: forward, lateral and yaw velocity through setCommandsHigh.
  The clone gives the velocity envelope as the constructor defaults vx_max, vy_max and wz_max (interface.py:
  29-31, 71-75, 195-204), which the deployment configures, so every bound is ``operator_required``;
* ``x-cap.machines-in-motion.go2_joint_command.v1``: 12 target angles and 12 feedforward torques through
  setCommandsLow, with the per-joint position and effort bounds of the clone's URDF and MuJoCo model.  The
  remaining arrays are fixed: dq_des = 0, kp = 150 and kd = 3, the tracking gains of the upstream FSM
  (Go2Py/robot/fsm.py:15-18).  The target is sent at once: the FSM's moveTo ramps a pose change over 0.5 s
  (fsm.py:52-63), which this action does not do, so a target far from the current pose is a step of those gains.

The device is a mobile base, so the driver is R2 and has an independent stop: the bridge sets Estop when the
wireless remote's R2 and L2 buttons are pressed and clears it with L2 and A (bridge.cpp:234-243).  This package is
model-authored and unreviewed, so it runs on the fake backend only; the loader refuses its hardware backend at R2
until a human signs ``reviewed_by`` in driver.lock.json.  Nothing here ran on a robot.

The joint order is the bridge's: FR, FL, RR, RL, three joints each (bridge.cpp:188-219).  The URDF and MuJoCo
files name the joints, so the limits are mapped by name, not by their order in those files.  The clone's own
``sitting_q`` puts a calf at -2.828 rad, outside the URDF calf range (-2.7227 rad); the URDF bound is enforced
here, so that one pose is refused.
"""

import numpy as np

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read

URDF = "Go2Py/assets/urdf/go2.urdf"
MUJOCO = "Go2Py/assets/mujoco/go2.xml"
INTERFACE = "Go2Py/robot/interface.py"
BRIDGE = "deploy/ros2_nodes/go2py_bridge/src/bridge.cpp"
FSM = "Go2Py/robot/fsm.py"
README = "README.md"

#: Bridge order of the 12 motors (bridge.cpp:188-219).  Each entry is (joint name, lower rad, upper rad, max
#: effort N.m, URDF limit line, MuJoCo motor-range line).
JOINTS = (
    ("FR_hip_joint", -1.0472, 1.0472, 23.7, 245, 10),
    ("FR_thigh_joint", -1.5708, 3.4907, 23.7, 275, 10),
    ("FR_calf_joint", -2.7227, -0.83776, 45.43, 305, 24),
    ("FL_hip_joint", -1.0472, 1.0472, 23.7, 99, 10),
    ("FL_thigh_joint", -1.5708, 3.4907, 23.7, 129, 10),
    ("FL_calf_joint", -2.7227, -0.83776, 45.43, 159, 24),
    ("RR_hip_joint", -1.0472, 1.0472, 23.7, 537, 10),
    ("RR_thigh_joint", -0.5236, 4.5379, 23.7, 567, 10),
    ("RR_calf_joint", -2.7227, -0.83776, 45.43, 597, 24),
    ("RL_hip_joint", -1.0472, 1.0472, 23.7, 391, 10),
    ("RL_thigh_joint", -0.5236, 4.5379, 23.7, 421, 10),
    ("RL_calf_joint", -2.7227, -0.83776, 45.43, 451, 24),
)
JOINT_NAMES = [name for name, _low, _high, _effort, _urdf_line, _torque_line in JOINTS]

#: One rule on the whole array (the runtime's LIMITS_UNSET rule reads a numeric array as one leaf); ``names``
#: labels the elements in a refusal.  The URDF states one range per joint in four leg blocks (go2.urdf:99-597).
JOINT_POSITION_LIMIT = Limit(
    min=[low for _name, low, _high, _effort, _urdf_line, _torque_line in JOINTS],
    max=[high for _name, _low, high, _effort, _urdf_line, _torque_line in JOINTS],
    names=JOINT_NAMES, unit="rad", source="upstream_code", ref=f"{URDF}:99-597",
    reason="URDF joint ranges for the 12 leg joints, in bridge order FR, FL, RR, RL")
#: The MuJoCo model gives the motor control range with both signs: +-23.7 N.m for hip and thigh motors and
#: +-45.43 N.m for the calf motors (go2.xml:10, 24).
JOINT_TORQUE_LIMIT = Limit(
    min=[-effort for _name, _low, _high, effort, _urdf_line, _torque_line in JOINTS],
    max=[effort for _name, _low, _high, effort, _urdf_line, _torque_line in JOINTS],
    names=JOINT_NAMES, unit="N.m", source="upstream_code", ref=f"{MUJOCO}:10-24",
    reason="MuJoCo motor control range for the hip and thigh motors and for the calf motors")
#: The upstream FSM's tracking move uses kp 150 and kv 3 (fsm.py:15-18); the driver sends them as the position and
#: damping gains of the low-level command.  The bridge's e-stop uses kd 3 with kp 0 (bridge.cpp:328).
TRACKING_KP = 150.0
TRACKING_KD = 3.0

VELOCITY_REASON = ("the clone states the body-velocity envelope only as the constructor defaults vx_max, vy_max "
                   "and wz_max (interface.py:29-31), which the deployment configures; the site sets the envelope")


class Go2(Driver):
    device_id = "go2"
    device_kind = "robot.mobile_base"
    mode = "hardware"
    risk = "R2"
    native = "Go2Py.robot.interface:GO2Real"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeGo2Real"}
    vendor, model = "Unitree Robotics", "Go2"
    display_name = "Unitree Go2 (Go2Py GO2Real)"
    tags = ["quadruped", "mobile robot", "unitree", "go2", "dds", "joint control", "velocity control"]
    facts = [
        Fact("GO2Real is the clone's user-facing robot interface class", source="upstream_code",
             ref=f"{INTERFACE}:24"),
        Fact("GO2Real creates a CycloneDDS participant, a state DataReader and low- and high-command DataWriters",
             source="upstream_code", ref=f"{INTERFACE}:59-70"),
        Fact("getJointStates returns the joint angles q, velocities dq, estimated torques tau_est and motor "
             "temperatures", source="upstream_code", ref=f"{INTERFACE}:106-111"),
        Fact("getIMU returns acceleration, angular velocity, quaternion and IMU temperature", source="upstream_code",
             ref=f"{INTERFACE}:94-99"),
        Fact("getFootContacts returns the raw foot contact forces", source="upstream_code",
             ref=f"{INTERFACE}:101-104"),
        Fact("getBatteryState returns the battery percentage", source="upstream_code", ref=f"{INTERFACE}:159-161"),
        Fact("setCommandsHigh writes v_x, v_y and omega_z to the high-level command writer", source="upstream_code",
             ref=f"{INTERFACE}:163-171"),
        Fact("setCommandsLow requires q_des, dq_des, kp, kd and tau_ff arrays of 12 elements and writes them to "
             "the low-level command writer", source="upstream_code", ref=f"{INTERFACE}:173-190"),
        Fact("The bridge names the 12 motor_state entries FR, FL, RR, RL and copies them in that order into "
             "go2py_state q, dq, tau and motor_temp", source="upstream_code", ref=f"{BRIDGE}:188-219"),
        Fact("The bridge sets Estop = 1 when the wireless remote's R2 and L2 buttons are pressed and Estop = 0 "
             "with L2 and A", source="upstream_code", ref=f"{BRIDGE}:234-243"),
        Fact("While Estop is set the bridge sends a damp request and a zero low-level command with kd 3 to all 12 "
             "motors", source="upstream_code", ref=f"{BRIDGE}:317-333"),
        Fact("The upstream FSM's tracking move uses kp 150 and kv 3 and its damping mode uses kd 2",
             source="upstream_code", ref=f"{FSM}:15-18"),
        Fact("The URDF states the position range, effort and velocity of every leg joint", source="upstream_code",
             ref=f"{URDF}:99-597"),
        Fact("The MuJoCo model states the motor torque control range as +-23.7 for the hip and thigh motors and "
             "+-45.43 for the calf motors", source="upstream_code", ref=f"{MUJOCO}:10-24"),
        Fact("The README describes the C++ bridge as implementing a remote-controlled emergency stop",
             source="vendor_doc", ref=f"{README}:10"),
    ]
    safe_state = ("zero body velocity (the bridge sends Move(0, 0, 0)) and the bridge's low-level damping command, "
                  "kp 0 and kd 3 with zero torque, to all 12 motors; the wireless remote's R2 and L2 make the bridge "
                  "add its sport-mode Damp request and latch Estop until an operator clears it with L2 and A")
    #: The bridge's wireless-remote stop (R2 + L2) is an independent hardware stop (SAFE-045).
    estop_physical_ref = f"{BRIDGE}:234-243"

    # -- reads -----------------------------------------------------------------------------------------------------
    @read("joint_positions", type="array", items="number", length=12, unit="rad",
          description="Joint angles in bridge order FR, FL, RR, RL (three joints per leg)")
    def get_joint_positions(self):
        return [float(value) for value in self.native.getJointStates()["q"]]

    @read("joint_velocities", type="array", items="number", length=12, unit="rad/s",
          description="Joint velocities in bridge order FR, FL, RR, RL")
    def get_joint_velocities(self):
        return [float(value) for value in self.native.getJointStates()["dq"]]

    @read("joint_torques", type="array", items="number", length=12, unit="N.m",
          description="Estimated joint torques in bridge order FR, FL, RR, RL")
    def get_joint_torques(self):
        return [float(value) for value in self.native.getJointStates()["tau_est"]]

    @read("motor_temperatures", type="array", items="number", length=12, unit="Cel",
          description="Motor temperatures in bridge order FR, FL, RR, RL")
    def get_motor_temperatures(self):
        return [float(value) for value in self.native.getJointStates()["temperature"]]

    @read("imu_acceleration", type="array", items="number", length=3, unit="m/s2",
          description="IMU linear acceleration (x, y, z)")
    def get_imu_acceleration(self):
        return [float(value) for value in self.native.getIMU()["accel"]]

    @read("imu_angular_velocity", type="array", items="number", length=3, unit="rad/s",
          description="IMU angular velocity (x, y, z)")
    def get_imu_angular_velocity(self):
        return [float(value) for value in self.native.getIMU()["gyro"]]

    @read("imu_orientation", type="object", description="IMU orientation quaternion",
          properties={
              "x": Field("number", unit="1", description="Quaternion x"),
              "y": Field("number", unit="1", description="Quaternion y"),
              "z": Field("number", unit="1", description="Quaternion z"),
              "w": Field("number", unit="1", description="Quaternion w"),
          })
    def get_imu_orientation(self):
        quat = self.native.getIMU()["quat"]
        return {"x": float(quat[0]), "y": float(quat[1]), "z": float(quat[2]), "w": float(quat[3])}

    @read("imu_temperature", unit="Cel", description="IMU temperature")
    def get_imu_temperature(self):
        return float(self.native.getIMU()["temp"])

    @read("foot_contact_forces", type="array", items="number", length=4, unit="1",
          description="Raw foot contact values in bridge order FR, FL, RR, RL; the clone states no unit")
    def get_foot_contact_forces(self):
        return [float(value) for value in self.native.getFootContacts()]

    @read("battery_soc", unit="%", description="Battery state of charge, percent")
    def get_battery_soc(self):
        return float(self.native.getBatteryState())

    # -- actions ---------------------------------------------------------------------------------------------------
    @action(cap="cap.motion.stop.v1",
            description="Stop the robot as the e-stop does: zero body velocity through setCommandsHigh, which ends "
                        "a body-velocity command, and the bridge's low-level damping command (kp 0, kd 3)",
            input={"deceleration": Field(
                "number", unit="m/s2",
                description="Requested deceleration; the clone's stop is a fixed damping command and does not use "
                            "a deceleration profile")})
    def stop_motion(self, deceleration=None):
        self._stop_commands()
        return {"stopped": True}

    @action(name="x-cap.machines-in-motion.go2_body_velocity.v1", risk="R2",
            description="Command forward, lateral and yaw velocity through setCommandsHigh; the command stays in "
                        "effect until another command or the stop action, because the clone documents no expiry",
            input={
                "forward_velocity": Field(
                    "number", unit="m/s", description="Forward velocity in the body frame",
                    limit=Limit.operator_required(VELOCITY_REASON)),
                "lateral_velocity": Field(
                    "number", unit="m/s", description="Lateral velocity in the body frame",
                    limit=Limit.operator_required(VELOCITY_REASON)),
                "yaw_rate": Field(
                    "number", unit="rad/s", description="Yaw rate in the body frame",
                    limit=Limit.operator_required(VELOCITY_REASON)),
            },
            output={
                "applied": Field("boolean", description="True once the command reached the high-level writer"),
                "forward_velocity": Field("number", unit="m/s",
                                          description="Forward velocity written to the high-level writer"),
                "lateral_velocity": Field("number", unit="m/s",
                                          description="Lateral velocity written to the high-level writer"),
                "yaw_rate": Field("number", unit="rad/s",
                                  description="Yaw rate written to the high-level writer"),
            })
    def drive(self, forward_velocity, lateral_velocity, yaw_rate):
        forward = float(forward_velocity)
        lateral = float(lateral_velocity)
        yaw = float(yaw_rate)
        self.native.setCommandsHigh(forward, lateral, yaw)
        return {"applied": True, "forward_velocity": forward, "lateral_velocity": lateral, "yaw_rate": yaw}

    @action(name="x-cap.machines-in-motion.go2_joint_command.v1", risk="R2",
            description="Command 12 joint angles and 12 feedforward torques through setCommandsLow, with zero "
                        "desired velocity and the upstream FSM's tracking gains kp 150 and kd 3; the target is sent "
                        "at once, with no ramp from the current pose",
            input={
                "joint_positions": Field(
                    "array", unit="rad", length=12,
                    description="Target angles in bridge order FR, FL, RR, RL",
                    limit=JOINT_POSITION_LIMIT),
                "feedforward_torques": Field(
                    "array", unit="N.m", length=12,
                    description="Feedforward torques in bridge order FR, FL, RR, RL",
                    limit=JOINT_TORQUE_LIMIT),
            },
            output={"applied": Field("boolean", description="True once the low-level command was written")})
    def command_joints(self, joint_positions, feedforward_torques):
        q_des = np.asarray(joint_positions, dtype=float)
        tau_ff = np.asarray(feedforward_torques, dtype=float)
        zeros = np.zeros(12, dtype=float)
        self.native.setCommandsLow(q_des, zeros, np.full(12, TRACKING_KP), np.full(12, TRACKING_KD), tau_ff)
        return {"applied": True}

    # -- safety ----------------------------------------------------------------------------------------------------
    @estop(native="setCommandsLow")
    def stop(self):
        """The native stop: the runtime latches, then zero velocity and the bridge's damping command are written."""
        self._stop_commands()

    def _stop_commands(self):
        """Zero body velocity, then the bridge's e-stop low-level command: q 0, kp 0, dq 0, kd 3, tau 0
        (bridge.cpp:323-332)."""
        self.native.setCommandsHigh(0.0, 0.0, 0.0)
        zeros = np.zeros(12, dtype=float)
        self.native.setCommandsLow(zeros, zeros.copy(), zeros.copy(), np.full(12, TRACKING_KD), zeros.copy())
