"""OpenMHS driver for gh.dyson-ai/grip: the PickAndPlaceEnvironment pybullet simulation.

DEVIATION FROM THE CARD: the card proposes the ROS family and ``RosDriver``
(``reason_code: family:ros``), but its own AST-confirmed entry class is
``grip.environments.pick_and_place_env:PickAndPlaceEnvironment``, a Python
pybullet environment, not a ROS topic/service/action endpoint.  The clone does
contain ROS 2 nodes (``grip/ros``, README.md:48-75), yet the environment's
control interface is ``reset()`` and ``step(action)`` (template_env.py:148-185),
which no rosbridge endpoint in the clone exposes.  A ``RosDriver`` would have
to invent an endpoint.  This package is therefore a direct ``Driver`` over the
entry class, with the package fake.  ``cap.world.step.v1`` takes ``ticks`` and
the upstream action object (``joint_position_cmd`` and ``gripper_cmd``);
``cap.world.reset.v1`` calls ``PickAndPlaceEnvironment.reset()``.  The upstream
has no ``action_space``/``observation_space`` (base_env.py:8-92), so a
``GymnasiumDriver`` cannot derive a contract either.

The device is simulated (R0): there is no hardware backend, no hardware e-stop
path and no operator-required limit.  The gate cannot import pybullet, NumPy or
the clone, so the checked ``fake`` backend is this package's pure-Python
stand-in (fake.py); it was never compared with the upstream simulator.  This
package is model-authored and unreviewed: every run here is a fake run.

Every fact cites the pinned clone at
eee9f38f86ac636ba4b4ddd1e6b9cfb783f0e203.
"""

from collections.abc import Mapping
import copy
import math
from types import MappingProxyType

from mhs import canonical
from mhs.driver import Driver, DriverFailed, Fact, Field, action, read, reset

from .adapter import EnvironmentAdapter
from .sim import configuration

ENV = "grip/environments/pick_and_place_env.py"
TEMPLATE = "grip/environments/template_env.py"
BASE = "grip/environments/base_env.py"
PANDA = "grip/robot/panda_robot.py"
PANDA_GRIPPER = "grip/robot/panda_gripper.py"
README = "README.md"
SETUP = "setup.py"
PYPROJECT = "pyproject.toml"

#: The Franka Panda arm has seven actuated joints (panda_robot.py:57-59).
JOINT_COUNT = 7
#: ``TemplateEnvironment.__init__`` default seed (template_env.py:34).
DEFAULT_SEED = 77
#: One environment tick runs ``sim_steps`` (10) world steps of ``time_step``
#: (1/240 s); both are constructor defaults (template_env.py:42-43), so the
#: deployed value is configurable and the fake repeats the defaults.
TIMESTEP_MS = 1000.0 * 10.0 / 240.0


def _plain_scalar(value):
    """One Python scalar from a native reward or terminal flag (array-like or scalar)."""
    if hasattr(value, "tolist"):
        value = value.tolist()
    while isinstance(value, (list, tuple)) and len(value) == 1:
        value = value[0]
    if isinstance(value, (list, tuple, Mapping)):
        raise ValueError("native reward/flag must be scalar")
    return value


def _plain(value):
    """JSON-safe observation data; the upstream entity states embed a non-JSON ``entity`` pointer."""
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items() if key != "entity"}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, (str, bool, int, float)) or value is None:
        return value
    raise DriverFailed("MHS.ADAPTER.SHIM_FAILED",
                       f"observation contains {type(value).__name__}, which is not JSON data")


def _native_action(action):
    """The upstream ``step`` action dict from the capability input (template_env.py:164-174)."""
    if action is None:
        return {}
    if not isinstance(action, Mapping):
        raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "action must be an object")
    native = {}
    joint = action.get("joint_position_cmd")
    if joint is not None:
        if hasattr(joint, "tolist"):
            joint = joint.tolist()
        if not isinstance(joint, (list, tuple)) or len(joint) != JOINT_COUNT:
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                               f"action.joint_position_cmd must have {JOINT_COUNT} values")
        values = []
        for value in joint:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                                   "action.joint_position_cmd values must be numbers")
            values.append(float(value))
        native["joint_position_cmd"] = values
    gripper = action.get("gripper_cmd")
    if gripper is not None:
        if isinstance(gripper, bool) or not isinstance(gripper, (int, float)) or not math.isfinite(gripper):
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                               "action.gripper_cmd must be a number (the upstream string modes are not exposed)")
        native["gripper_cmd"] = float(gripper)
    return native


class GripPickAndPlace(Driver):
    device_id = "grip-pick-and-place"
    device_kind = "world.sim"
    resource_id = "world"
    mode = "simulated"
    risk = "R0"
    native = "grip.environments.pick_and_place_env:PickAndPlaceEnvironment"
    backends = {"fake": ".fake:FakePickAndPlaceEnvironment", "sim": ".sim:open_sim"}
    display_name = "Grip PickAndPlaceEnvironment (pybullet)"
    vendor, model = "Dyson AI", "grip PickAndPlaceEnvironment"
    tags = ["pybullet", "manipulation", "pick-and-place", "franka", "simulation", "reinforcement-learning"]
    facts = [
        Fact("Grip is a Bullet3-powered prototyping toolbox for manipulation environments, robot arms, "
             "grippers and RGBD cameras, with ROS2 integration", source="vendor_doc", ref=f"{README}:5"),
        Fact("The Env abstract base declares step(action), reset() and render(mode)", source="upstream_code",
             ref=f"{BASE}:8-77"),
        Fact("TemplateEnvironment is defined as an Env subclass", source="upstream_code", ref=f"{TEMPLATE}:32"),
        Fact("PickAndPlaceEnvironment is defined as a TemplateEnvironment subclass", source="upstream_code",
             ref=f"{ENV}:21"),
        Fact("The constructor reads seed (default 77) and seeds Python's random and NumPy's generator with it",
             source="upstream_code", ref=f"{TEMPLATE}:34-37"),
        Fact("The constructor defaults time_step to 1/240 s and sim_steps to 10", source="upstream_code",
             ref=f"{TEMPLATE}:42-43"),
        Fact("The constructor creates a BulletWorld with the configured render mode, real_time_sim False and the "
             "time step", source="upstream_code", ref=f"{TEMPLATE}:59-61"),
        Fact("The environment spawns a BulletPandaArmGripper with the configured gripper type and maximum force",
             source="upstream_code", ref=f"{TEMPLATE}:99-105"),
        Fact("init registers the plane, robot and table, the shoulder camera for the selected modes and the wrist "
             "camera for the wrist/all modes", source="upstream_code", ref=f"{TEMPLATE}:123-131"),
        Fact("reset restores the world state, resets the panda and returns obs()", source="upstream_code",
             ref=f"{TEMPLATE}:148-155"),
        Fact("step applies joint_position_cmd with set_angles and gripper_cmd with control_fingers or "
             "apply_gripper_delta_action, advances sim_steps world steps and returns (obs, reward, done, info)",
             source="upstream_code", ref=f"{TEMPLATE}:160-185"),
        Fact("obs returns each entity's state and, unless camera_mode is none, each camera's rgb, depth, seg and "
             "pose", source="upstream_code", ref=f"{TEMPLATE}:190-204"),
        Fact("sample returns seven joint-position values and one gripper value drawn with np.random.randn",
             source="upstream_code", ref=f"{TEMPLATE}:206-210"),
        Fact("PickAndPlaceEnvironment adds a fixed tray and a free duck object loaded from pybullet_data URDFs",
             source="upstream_code", ref=f"{ENV}:38-72"),
        Fact("The panda arm controls panda_joint1 through panda_joint7 and defaults gripper_max_force to 12",
             source="upstream_code", ref=f"{PANDA}:57-61"),
        Fact("PandaGripper.apply_gripper_delta_action takes a delta finger-distance action, adds it to the finger "
             "positions and clips each finger to its lower and upper joint limit", source="upstream_code",
             ref=f"{PANDA_GRIPPER}:54-65"),
        Fact("The documented pure-python example runs the pick-and-place environment with "
             "python3 -m grip_examples.environments.ex01_pick_and_place", source="vendor_doc",
             ref=f"{README}:19-23"),
        Fact("The package metadata requires Python >=3.10,<3.13", source="vendor_doc", ref=f"{SETUP}:41"),
        Fact("The runtime dependencies include NumPy, pybullet, open3d, OpenCV and Matplotlib", source="vendor_doc",
             ref=f"{PYPROJECT}:10-24"),
    ]
    safe_state = ("new environment calls are fenced immediately; idle is confirmed only after any in-flight "
                  "native call returns; reset refuses while a call is active; the last state stays readable")
    #: The checked fake is an analytic, pybullet-free kinematic stand-in.  The
    #: upstream constructor's 10 x 1/240 s substeps are configurable defaults,
    #: recorded here as the deployed fake's fixed timestep.
    fidelity = {
        "engine": "analytic:grip PickAndPlaceEnvironment stand-in (no pybullet)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "the upstream constructor seeds Python and NumPy once (template_env.py:34-37) and reset() "
                     "has no seed argument, so this driver exposes no seed control; the fake is deterministic for "
                     "a fixed action sequence but claims no seeded-replay contract and was not compared with "
                     "upstream",
        },
        "timestep_ms": TIMESTEP_MS,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a pure-Python kinematic stand-in: no pybullet, rigid-body dynamics, contacts, friction, "
            "gripper contact, camera rendering or point-cloud pipeline",
            "one cap.world.step.v1 tick models the upstream constructor defaults of 10 world steps of 1/240 s "
            "(template_env.py:42-43); both are configurable per environment instance and the fake uses fixed "
            "placeholder values",
            "the observation is a reduced JSON object with robot joint positions/velocities/efforts and object and "
            "tray poses; the upstream observation also carries entity pointers, plane/table states and camera rgb, "
            "depth and segmentation arrays (template_env.py:190-204), which are omitted",
            "the fake accepts a numeric gripper delta finger-distance command only; the upstream step also accepts the "
            "strings 'open' and 'close' (template_env.py:170-174), which the published schema does not expose",
            "reset performs no seeding: the upstream reset takes no seed argument and the environment seeds its "
            "generators only in the constructor; the reset receipt reports the selected constructor seed, without claiming reset reseeding",
            "snapshot and restore are not offered: the environment exposes no get_state/set_state pair",
            "the real pybullet environment needs pybullet, NumPy, open3d, OpenCV and Matplotlib "
            "(pyproject.toml:10-24); nothing was installed or run where the gate ran",
            "no physical device is modelled and nothing was validated against one",
        ],
    }

    # ------------------------------------------------------------------ hooks
    def __init__(self, **kwargs):
        self._config = configuration(copy.deepcopy(kwargs.get("options") or {}))
        kwargs["options"] = dict(self._config)
        super().__init__(**kwargs)
        self.options = MappingProxyType(dict(self._config))

    def _driver_model(self):
        model = copy.deepcopy(super()._driver_model())
        model.fidelity = copy.deepcopy(model.fidelity)
        model.fidelity["timestep_ms"] = 1000 * self._config["sim_steps"] * self._config["time_step"]
        model.fidelity["gaps"].append("A tick is one native environment call; physics receipts are not yet L14-accounted")
        if self.backend == "sim":
            model.fidelity.update(engine="pybullet:grip PickAndPlaceEnvironment (unverified live deployment)",
                                  fidelity_level="F1")
            model.fidelity["gaps"] = [
                "real dependency import/construction not executed by this package review",
                "numeric Panda control only; no open/close strings with extra physics steps",
                "non-realtime world configured with default Panda gripper; no hardware",
                "constructor seed is recorded; reset does not reseed or restore RNG state",
                "one environment call per tick; physics receipt accounting remains unverified",
                "no portable snapshot/restore or hardware fidelity validation"]
        return model

    def setup(self) -> None:
        self._adapter = EnvironmentAdapter(self.native, self._config, owns_world=self.backend == "sim")
        self._tick = 0
        self._episode = 0
        self._seed = self._config["seed"]
        self._reward = 0.0
        self._terminated = False
        self._truncated = False
        self._last_observation = {}
        self._info = {}

    def teardown(self) -> None:
        self._adapter.close()

    # ------------------------------------------------------------------ state
    @read("observation", type="object", description="Last environment observation (JSON projection)")
    def observation(self) -> dict:
        return dict(getattr(self, "_last_observation", {}))

    @read("reward", type="number", unit="1", description="Reward of the last step")
    def reward(self) -> float:
        return float(getattr(self, "_reward", 0.0))

    @read("terminated", type="boolean", description="Whether the last step reached a terminal state")
    def terminated(self) -> bool:
        return bool(getattr(self, "_terminated", False))

    @read("truncated", type="boolean", description="Whether the last step reached an episode limit")
    def truncated(self) -> bool:
        return bool(getattr(self, "_truncated", False))

    @read("tick", type="integer", unit="1", description="Environment ticks applied since the last reset")
    def tick(self) -> int:
        return int(getattr(self, "_tick", 0))

    @read("episode", type="integer", unit="1", description="Resets served by this backend")
    def episode(self) -> int:
        return int(getattr(self, "_episode", 0))

    @read("seed", type="integer", unit="1",
          description="Recorded construction seed; native reset does not reseed")
    def seed(self) -> int:
        return int(getattr(self, "_seed", DEFAULT_SEED))

    @read("info", type="object", description="Task information returned by the last step")
    def info(self) -> dict:
        return dict(getattr(self, "_info", {}))

    # ---------------------------------------------------------------- actions
    @action(cap="cap.world.step.v1",
            description="Advance the pick-and-place simulation by bounded ticks with one action",
            input={
                "ticks": Field("integer", unit="1",
                               description="Environment ticks to advance; the action is applied at every tick"),
                "action": Field("object",
                                description="Upstream step action; omitted members are not commanded",
                                properties={
                                    "joint_position_cmd": Field(
                                        "array", items="number", length=JOINT_COUNT, unit="rad", required=False,
                                        description="Seven Franka Panda joint angles"),
                                    "gripper_cmd": Field(
                                        "number", unit="m", required=False,
                                        description="Gripper delta finger-distance command (the upstream 'open'/'close' "
                                                    "strings are not exposed)"),
                                }),
            })
    def step(self, ticks: int, action=None) -> dict:
        if self._terminated or self._truncated:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "the episode has ended; reset the environment before stepping")
        if isinstance(ticks, bool) or not isinstance(ticks, int) or ticks < 1:
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "ticks must be a positive integer")
        native_action = _native_action(action)
        total_reward = 0.0
        for _ in range(ticks):
            self.check_cancelled()
            result = self._adapter.invoke("step", native_action, check=self.check_cancelled)
            try:
                observation, reward, terminated, truncated, info = result
            except (TypeError, ValueError):
                observation, reward, done, info = result
                terminated, truncated = done, False
            self._tick += 1
            self._last_observation = _plain(observation)
            if not isinstance(self._last_observation, Mapping):
                raise DriverFailed("MHS.ADAPTER.SHIM_FAILED", "the environment observation is not an object")
            self._reward = float(_plain_scalar(reward))
            total_reward += self._reward
            self._terminated = bool(_plain_scalar(terminated))
            self._truncated = bool(_plain_scalar(truncated))
            self._info = dict(info or {}) if isinstance(info, Mapping) else {"info": _plain(info)}
            if self._terminated or self._truncated:
                break
        return {
            "observation": dict(self._last_observation),
            "reward": total_reward,
            "terminated": bool(self._terminated),
            "truncated": bool(self._truncated),
            "tick": int(self._tick),
            "state_hash": canonical.digest({
                "observation": self._last_observation,
                "tick": int(self._tick),
                "episode": int(self._episode),
                "terminated": bool(self._terminated),
                "truncated": bool(self._truncated),
                "seed": int(self._seed),
            }),
        }

    @action(cap="cap.world.reset.v1",
            description="Reset the pick-and-place scene and return its initial observation",
            input={
                "scenario": Field("string", required=False,
                                  description="Named scenario; only 'default' is served"),
                "options": Field("object", required=False,
                                 description="Only an empty options object is supported; native reset has no options"),
            })
    def reset_world(self, scenario=None, options=None) -> dict:
        if scenario not in (None, "default"):
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "only the 'default' scenario is served")
        if options is not None and (not isinstance(options, Mapping) or options):
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "only empty reset options are supported")
        observation = self._adapter.invoke("reset", check=self.check_cancelled)
        self._tick = 0
        self._episode += 1
        self._reward = 0.0
        self._terminated = False
        self._truncated = False
        self._last_observation = _plain(observation)
        if not isinstance(self._last_observation, Mapping):
            raise DriverFailed("MHS.ADAPTER.SHIM_FAILED", "the environment observation is not an object")
        self._info = {}
        return {"observation": dict(self._last_observation), "seed": int(self._seed)}

    @action(name="x-cap.dyson-ai.fence.v1", safe_state=True,
            description="Fence future environment calls and confirm the non-realtime world is idle",
            output={"idle": Field("boolean")})
    def fence(self):
        return self._adapter.fence()

    @reset
    def recover(self):
        self._adapter.recover()
