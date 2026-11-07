"""OpenMHS driver for gh.electronicelephant/pybullet_ur5_robotiq: the ClutteredPushGrasp PyBullet simulation.

The upstream is a Gym-styled but not Gymnasium-registered environment: ``ClutteredPushGrasp`` has no
``action_space``, no ``observation_space``, no ``env_id`` and no ``gymnasium.make`` entry point
(``env.py:19-23`` and ``:81-97``).  A ``GymnasiumDriver`` derives the whole contract from those spaces, so that
shape cannot express this interface.  This package is therefore a direct ``Driver`` over the upstream class (see
RESULT.json, "DEVIATION FROM THE CARD").

The two bound capabilities are ``cap.world.step.v1`` and ``cap.world.reset.v1``.  A step takes the catalogue
``ticks`` count and the seven-element end-effector action the clone documents (``env.py:83``): x, y, z, roll, pitch,
yaw and the gripper opening.  The action envelope is the range of the clone's own interactive sliders
(``env.py:40-46``), the same tuple ``read_debug_parameter`` returns (``env.py:69-79``) and the documented demo
passes to ``step(..., 'end')`` (``main.py:30``).  A reset calls ``ClutteredPushGrasp.reset`` (``env.py:131-134``)
and returns its observation.

``cap.world.seed.v1`` is deliberately not bound: ``ClutteredPushGrasp`` has no seed method and no random start.
``reset`` restores fixed rest poses and the fixed box (``robot.py:86-108``, ``env.py:127-134``), so the driver
declares an exact deterministic scene and publishes no integer seed.  A ``seed`` supplied to the reset is recorded
only, and the required ``seed`` field of the reset output defaults to 0, because there is no random generator.

The device is simulated (R0): there is no hardware backend and no operator-required limit.  The fake backend
(``fake.py``) is the package's own pure Python stand-in; it was not compared with the upstream PyBullet environment
(pybullet, numpy and the YCB assets were not run where the gate ran).  This package is model-authored and
unreviewed, and is checked on the fake backend only.
"""

from collections.abc import Mapping

from mhs import canonical
from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, read

ENV = "env.py"
ROBOT = "robot.py"
MAIN = "main.py"
README = "README.md"

#: The order of the seven-element end-effector action (``env.py:83``).
ACTION_FIELDS = ("x", "y", "z", "roll", "pitch", "yaw", "gripper_opening_length")


def _observation_dict(value) -> dict:
    """A JSON object for the runtime: the upstream returns a dict, or a single value if it ever does not."""
    if isinstance(value, Mapping):
        return dict(value)
    return {"value": value}


class ClutteredPushGraspDriver(Driver):
    device_id = "ur5-robotiq"
    device_kind = "world.sim"
    resource_id = "world"
    mode = "simulated"
    risk = "R0"
    native = "env:ClutteredPushGrasp"
    backends = {"fake": ".fake:FakeClutteredPushGrasp"}
    display_name = "UR5 arm with Robotiq-85/140 gripper in a PyBullet push-and-grasp scene"
    vendor, model = "electronicelephant", "pybullet_ur5_robotiq"
    tags = ["ur5", "robotiq", "gripper", "pybullet", "simulation", "reinforcement-learning"]
    facts = [
        Fact("ClutteredPushGrasp is the user-facing environment class", source="upstream_code", ref=f"{ENV}:19"),
        Fact("The constructor opens an in-process PyBullet connection, GUI or DIRECT, and loads the plane, the "
             "robot and a fixed box; it opens no serial, VISA, USB or network transport",
             source="upstream_code", ref=f"{ENV}:23-58"),
        Fact("SIMULATION_STEP_DELAY is 1/240 s", source="upstream_code", ref=f"{ENV}:21"),
        Fact("step_simulation calls p.stepSimulation and sleeps the delay only when the GUI is shown",
             source="upstream_code", ref=f"{ENV}:60-67"),
        Fact("step accepts a seven-element action, asserts control_method is joint or end, calls "
             "move_ee(action[:-1], control_method) and move_gripper(action[-1]), and runs 120 simulation steps",
             source="upstream_code", ref=f"{ENV}:81-92"),
        Fact("The end-effector action is (x, y, z, roll, pitch, yaw, gripper_opening_length)",
             source="upstream_code", ref=f"{ENV}:83"),
        Fact("The interactive sliders bound x and y to -0.224..0.224, z to 0..1.0, roll and pitch to -3.14..3.14, "
             "yaw to -pi/2..pi/2 and the gripper opening to 0..0.085", source="upstream_code", ref=f"{ENV}:40-46"),
        Fact("read_debug_parameter returns the seven slider values in the action order", source="upstream_code",
             ref=f"{ENV}:69-79"),
        Fact("The documented user-control demo passes read_debug_parameter() and 'end' to step", source="upstream_code",
             ref=f"{MAIN}:30"),
        Fact("step returns (observation, reward, done, info), with done true only when reward == 1",
             source="upstream_code", ref=f"{ENV}:94-97"),
        Fact("The reward becomes 1 when the box has been opened and the button pressed and the box is then closed; "
             "the joint thresholds are 1.9, -0.02 and 0.1", source="upstream_code", ref=f"{ENV}:99-114"),
        Fact("The observation is the camera's rgb, depth and seg arrays when a Camera is configured, plus the "
             "robot's joint observation", source="upstream_code", ref=f"{ENV}:116-125"),
        Fact("get_joint_obs returns the controllable joints' positions and velocities and the end-effector position",
             source="upstream_code", ref=f"{ROBOT}:130-138"),
        Fact("reset resets the robot and the box and returns the observation", source="upstream_code",
             ref=f"{ENV}:127-134"),
        Fact("RobotBase.reset resets the arm to the rest poses and opens the gripper; it takes no seed",
             source="upstream_code", ref=f"{ROBOT}:86-108"),
        Fact("close disconnects the PyBullet client", source="upstream_code", ref=f"{ENV}:136-137"),
        Fact("UR5Robotiq85 loads ur5_robotiq_85.urdf with fixed base, eef 7, six arm dofs and gripper range "
             "0..0.085", source="upstream_code", ref=f"{ROBOT}:168-176"),
        Fact("UR5Robotiq140 loads ur5_robotiq_140.urdf with the same eef, six arm dofs and 0..0.085 gripper range",
             source="upstream_code", ref=f"{ROBOT}:209-218"),
        Fact("The README lists a Gym-styled API for reinforcement learning in push-and-grasp, 6D end-effector IK "
             "with Position XYZ and Orientation RPY, and PyBullet as the only prerequisite",
             source="vendor_doc", ref=f"{README}:11-20"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the last observation and tick stay readable")
    #: The model as deployed.  The upstream is a rigid-body PyBullet scene: fixed time stepping, contacts and IK,
    #: no random start and no state snapshot.
    fidelity = {
        "engine": "pybullet:ClutteredPushGrasp",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "exact",
            "seed_control": "none",
            "notes": "the scene, the reset and the actions are fixed and the clone seeds no random generator; "
                     "reset() restores fixed rest poses (robot.py:86-108) and the box (env.py:127-134), so the "
                     "same action sequence repeats from a fresh backend.  The clone states no integer seed and "
                     "exposes no get_state/set_state",
        },
        "timestep_ms": 0.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "one tick is one ClutteredPushGrasp.step call, which runs 120 p.stepSimulation iterations (env.py:91); "
            "the clone does not state the PyBullet physics time step, so timestep_ms is 0 (unknown) and only the "
            "step count is modelled",
            "the action envelope is the range of the clone's interactive debug sliders (env.py:40-46); step itself "
            "does not assert those bounds and the joint-position control mode is not exposed because the clone "
            "states no joint range for it",
            "the fake backend is a pure Python stand-in that models the tick, the last end-effector target and the "
            "observation shape but not PyBullet contacts, inverse kinematics, gravity, the box button or the "
            "reward thresholds; it was not compared with the upstream environment",
            "camera rgb, depth and seg arrays are not modelled by the fake and the driver declares no array size or "
            "unit: a Camera-configured environment passes them through as part of the open observation object",
            "snapshot and restore are not offered: the environment exposes no get_state/set_state",
            "no physical device is modelled and the model was never validated against one",
        ],
    }

    # ------------------------------------------------------------------ hooks
    def setup(self) -> None:
        self._tick = 0
        self._episode = 0
        self._terminated = False
        self._info = {"box_opened": False, "btn_pressed": False, "box_closed": False}
        self._last_observation = None

    def teardown(self) -> None:
        self.native.close()

    # ------------------------------------------------------------------ state
    def _tick_value(self) -> int:
        return int(getattr(self, "_tick", 0))

    def _episode_value(self) -> int:
        return int(getattr(self, "_episode", 0))

    def _observation(self) -> dict:
        return _observation_dict(self.native.get_observation())

    @read("observation", type="object",
          description="Current observation of the simulated robot and scene")
    def observation(self) -> dict:
        return self._observation()

    @read("tick", type="integer", unit="1", description="Control steps applied since the last reset")
    def tick(self) -> int:
        return self._tick_value()

    @read("episode", type="integer", unit="1", description="Resets served by this backend")
    def episode(self) -> int:
        return self._episode_value()

    @read("info", type="object", description="Task flags returned by the last step",
          properties={
              "box_opened": Field("boolean", description="Whether the box joint passed its opening threshold"),
              "btn_pressed": Field("boolean", description="Whether the button joint passed its threshold"),
              "box_closed": Field("boolean", description="Whether the box was closed after the button"),
          })
    def info(self) -> dict:
        return dict(getattr(self, "_info", {}))

    # ---------------------------------------------------------------- actions
    @action(cap="cap.world.step.v1",
            description="Apply the end-effector action to the upstream scene",
            input={
                "ticks": Field("integer", unit="1",
                               description="Control steps; one tick calls step once (120 physics iterations)"),
                "action": Field("object", description="End-effector action of step(..., 'end')",
                                properties={
                                    "x": Field("number", unit="m", description="Target x",
                                               limit=Limit(min=-0.224, max=0.224, source="upstream_code",
                                                           ref=f"{ENV}:40")),
                                    "y": Field("number", unit="m", description="Target y",
                                               limit=Limit(min=-0.224, max=0.224, source="upstream_code",
                                                           ref=f"{ENV}:41")),
                                    "z": Field("number", unit="m", description="Target z",
                                               limit=Limit(min=0.0, max=1.0, source="upstream_code",
                                                           ref=f"{ENV}:42")),
                                    "roll": Field("number", unit="rad", description="Target roll",
                                                  limit=Limit(min=-3.14, max=3.14, source="upstream_code",
                                                              ref=f"{ENV}:43")),
                                    "pitch": Field("number", unit="rad", description="Target pitch",
                                                   limit=Limit(min=-3.14, max=3.14, source="upstream_code",
                                                               ref=f"{ENV}:44")),
                                    "yaw": Field("number", unit="rad", description="Target yaw",
                                                 limit=Limit(min=-1.5707963267948966, max=1.5707963267948966,
                                                             source="upstream_code", ref=f"{ENV}:45")),
                                    "gripper_opening_length": Field(
                                        "number", unit="m", description="Gripper opening",
                                        limit=Limit(min=0.0, max=0.085, source="upstream_code", ref=f"{ENV}:46")),
                                }),
            })
    def step(self, ticks: int, action: dict) -> dict:
        if getattr(self, "_terminated", False):
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "the box task is done; reset the environment before stepping again")
        if not isinstance(action, Mapping):
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "action must be an object")
        count = int(ticks)
        if count < 1:
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "ticks must be at least 1")
        values = tuple(float(action[name]) for name in ACTION_FIELDS)
        observation = self._observation()
        reward_total = 0.0
        terminated = False
        for _ in range(count):
            observation, reward, done, info = self.native.step(values, "end")
            self._tick = self._tick_value() + 1
            reward_total += float(reward) if reward is not None else 0.0
            self._info = {"box_opened": False, "btn_pressed": False, "box_closed": False}
            self._info.update(info or {})
            terminated = bool(done)
            if terminated:
                break
        self._last_observation = observation
        self._terminated = terminated
        observation = _observation_dict(observation)
        return {
            "observation": observation,
            "reward": reward_total,
            "terminated": terminated,
            "truncated": False,
            "tick": self._tick_value(),
            "state_hash": canonical.digest({
                "observation": observation,
                "tick": self._tick_value(),
                "episode": self._episode_value(),
                "terminated": terminated,
            }),
        }

    @action(cap="cap.world.reset.v1",
            description="Reset the robot to its rest pose and the box to its start state",
            input={
                "seed": Field("integer", unit="1", required=False,
                              description="Seed recorded for this reset; the scene has no random generator"),
                "scenario": Field("string", required=False,
                                  description="Named scenario; only 'default' is served"),
                "options": Field("object", required=False,
                                 description="Reset options; the upstream reset takes none"),
            })
    def reset_world(self, seed=None, scenario=None, options=None) -> dict:
        if scenario not in (None, "default"):
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "only the 'default' scenario is served")
        if options:
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "the upstream reset takes no options")
        if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int) or seed < 0):
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "seed must be a non-negative integer")
        observation = _observation_dict(self.native.reset())
        self._tick = 0
        self._episode = self._episode_value() + 1
        self._terminated = False
        self._info = {"box_opened": False, "btn_pressed": False, "box_closed": False}
        self._last_observation = observation
        # The upstream reset takes no seed and the scene has no random start.  The catalogue output requires an
        # integer seed: an explicitly supplied seed is recorded only, and the endpoint's default is 0.
        return {"observation": observation, "seed": int(seed) if seed is not None else 0}
