"""OpenMHS driver for gh.amathislab/musclemimic: the MyoFullBody MuJoCo environment.

The card proposes a ``MujocoDriver`` (family ``mujoco``), but the entry symbol is not a raw MJCF model: it is the
repository's own ``MyoFullBody`` environment (``musclemimic/environments/humanoids/myofullbody.py:17``), which derives
from the repository's ``LocoEnv``/``Mujoco`` classes (``loco_mujoco/core/mujoco_base.py:44``) and resolves its model
file through the separate ``musclemimic_models`` package at runtime
(``musclemimic/environments/humanoids/myofullbody.py:449-453``).  The clone ships no MJCF file and the card's
``models`` list is empty, so a ``MujocoDriver`` has no ``model_path`` it could load.  The primary interface is the
environment's own ``reset(key)`` and ``step(action)`` (``loco_mujoco/core/mujoco_base.py:194-228`` and
``:230-288``), and the class exposes its spaces only through ``env.info`` (``loco_mujoco/core/mujoco_base.py:158``
and ``:1296-1303``), not as ``action_space``/``observation_space`` attributes; a ``GymnasiumDriver`` therefore cannot
derive the contract either.  This package is a direct ``Driver`` over the entry class (see RESULT.json, DEVIATION
FROM THE CARD).

``cap.world.step.v1`` takes the catalogue ``ticks`` count and an action object ``{"values": [...]}``: one normalized
muscle command per actuator, in the model's actuator order.  The command range is the environment's control range,
``[-1, 1]`` for every muscle actuator (``myofullbody.py:317-322``), and the default control function maps that range
to the actuator range (``loco_mujoco/core/control_functions/default.py:24-50``).  The vector length is model-dependent
(the environment takes every actuator name, ``myofullbody.py:394-407``, and deletes the finger muscles when
``disable_fingers`` is true, ``myofullbody.py:157-301``); this driver therefore does not invent a length and leaves
the native dimension check to the environment.  ``cap.world.reset.v1`` calls ``reset()`` and returns the initial
observation.  The native reset takes a JAX key, not an integer seed, so the class seed input is accepted but not
applied and the output seed is 0; ``cap.world.seed.v1`` is deliberately not bound.

The environment reports ``(observation, reward, absorbing, done, info)``: the third value is the terminal state and
the fourth is done (absorbing or the episode horizon, ``mujoco_base.py:397``); the driver publishes them as
``terminated`` and ``truncated``.

The device is simulated (R0): there is no hardware backend, no native stop and no operator-required limit.  The
``fake`` backend (``fake.py``) is this package's pure Python stand-in.  MuJoCo, JAX and the external model package are
not installed where the gate runs, and the model file is not in this clone, so only the fake backend is served and the
real environment was not run.  This package is model-authored and unreviewed.
"""

from collections.abc import Mapping
import math

from mhs import canonical
from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, read

ENV = "musclemimic/environments/humanoids/myofullbody.py"
BASE = "loco_mujoco/core/mujoco_base.py"
LOCO = "musclemimic/environments/base.py"
CONTROL = "loco_mujoco/core/control_functions/default.py"
REGISTRY = "musclemimic/environments/humanoids/__init__.py"
README = "README.md"
PYPROJECT = "pyproject.toml"


def _plain_scalar(value, *, flag=False):
    """One Python scalar from a native reward or flag (a NumPy scalar, a one-element list or a scalar)."""
    if hasattr(value, "tolist"):
        value = value.tolist()
    while isinstance(value, (list, tuple)) and len(value) == 1:
        value = value[0]
    if (not isinstance(value, (int, float)) or (isinstance(value, bool) and not flag)
            or not math.isfinite(value) or (flag and value not in (0, 1))):
        raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID", "native reward or flag is missing or invalid")
    return value


def _observation_object(value) -> dict:
    """The native observation as a JSON object with one flat ``values`` row.

    The environment returns a NumPy array (``mujoco_base.py:288``); the default configuration is one environment, so
    the first row of a nested result is used and a mapping is flattened in its native key order.
    """
    if hasattr(value, "tolist"):
        value = value.tolist()
    while isinstance(value, (list, tuple)) and value and isinstance(value[0], (list, tuple)):
        value = value[0]
    if isinstance(value, Mapping):
        flat = []
        for item in value.values():
            if hasattr(item, "tolist"):
                item = item.tolist()
            if isinstance(item, (list, tuple)):
                flat.extend(float(element) for element in item)
            else:
                flat.append(float(item))
        return {"values": flat}
    if isinstance(value, (list, tuple)):
        return {"values": [float(item) for item in value]}
    return {"values": [float(value)]}


def _action_values(action) -> list:
    """The normalized muscle command row of the ``action`` object, without changing it."""
    if not isinstance(action, Mapping):
        raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "action must be an object")
    values = action.get("values")
    if not isinstance(values, (list, tuple)):
        raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "action.values must be an array")
    out = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "action.values must contain numbers")
        number = float(value)
        if not math.isfinite(number):
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "action.values must be finite")
        out.append(number)
    if not out:
        raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "action.values must not be empty")
    return out


def _native_action(values):
    """The action in the array form the native ``step`` receives; a list is accepted when NumPy is absent."""
    try:
        import numpy as np
    except ImportError:  # the upstream needs NumPy as well; the fake accepts a plain list
        return list(values)
    return np.asarray(list(values), dtype=np.float32)


class MuscleMimicMyoFullBody(Driver):
    device_id = "myofullbody"
    device_kind = "world.sim"
    resource_id = "world"
    mode = "simulated"
    risk = "R0"
    native = "musclemimic.environments.humanoids.myofullbody:MyoFullBody"
    backends = {"fake": ".fake:FakeMyoFullBody"}
    display_name = "MuscleMimic MyoFullBody (MuJoCo muscle-actuated humanoid)"
    vendor, model = "MuscleMimic Team", "MyoFullBody"
    tags = ["biomechanics", "humanoid", "jax", "mujoco", "muscle", "musculoskeletal", "simulation"]
    facts = [
        Fact("MyoFullBody is a concrete MuJoCo environment class of a full-body humanoid model with muscle "
             "actuation, deriving from LocoEnv", source="upstream_code", ref=f"{ENV}:17-22"),
        Fact("The repository's base class for MuJoCo environments is its own Mujoco class, declared at "
             "loco_mujoco/core/mujoco_base.py:44", source="upstream_code", ref=f"{BASE}:44-46"),
        Fact("The constructor defaults are timestep 0.002 s, n_substeps 5 and disable_fingers True",
             source="upstream_code", ref=f"{ENV}:56-58"),
        Fact("The action specification is every actuator name of the model, in the model's actuator order",
             source="upstream_code", ref=f"{ENV}:394-407"),
        Fact("Every muscle actuator's control range is set to [-1, 1] with ctrllimited True",
             source="upstream_code", ref=f"{ENV}:317-322"),
        Fact("The default control function normalizes the agent action space to [-1, 1] and rescales it to the "
             "actuator range", source="upstream_code", ref=f"{CONTROL}:24-90"),
        Fact("When disable_fingers is true the environment deletes the finger joints, finger muscles and their "
             "tendons", source="upstream_code", ref=f"{ENV}:157-301"),
        Fact("The README model table lists MyoFullBody as free-root with 123 joints, 416 muscles and 72 DoFs, or "
             "83 joints, 354 muscles and 32 DoFs with finger muscles disabled",
             source="vendor_doc", ref=f"{README}:45-50"),
        Fact("The default model XML path is resolved by musclemimic_models.get_xml_path('myofullbody'), a separate "
             "package from this clone", source="upstream_code", ref=f"{ENV}:449-453"),
        Fact("musclemimic_models is a declared runtime dependency of the project",
             source="upstream_code", ref=f"{PYPROJECT}:70"),
        Fact("The environment registry registers MyoFullBody when the humanoids package is imported",
             source="upstream_code", ref=f"{REGISTRY}:1-9"),
        Fact("LocoEnv.reset forwards to the MuJoCo reset with a JAX key and returns the initial observation",
             source="upstream_code", ref=f"{LOCO}:687-701"),
        Fact("The MuJoCo reset restores the data with mj_resetData and mj_forward and returns the initial "
             "observation", source="upstream_code", ref=f"{BASE}:194-228"),
        Fact("The MuJoCo step preprocesses the action, writes data.ctrl, runs mj_step for n_substeps and returns "
             "observation, reward, absorbing, done and info", source="upstream_code", ref=f"{BASE}:230-288"),
        Fact("done is absorbing or the current step count reaches the configured episode horizon",
             source="upstream_code", ref=f"{BASE}:378-398"),
        Fact("The default episode horizon is 1000 steps", source="upstream_code", ref=f"{BASE}:80-85"),
        Fact("The environment timestep is model.opt.timestep and one environment step advances simulation_dt times "
             "n_intermediate_steps times n_substeps", source="upstream_code", ref=f"{BASE}:1315-1333"),
    ]
    safe_state = ("the simulation stops advancing: the runtime latches the e-stop and no step or reset is accepted "
                  "until mhs.safety.reset clears it; the last observation and tick stay readable")
    #: The deployed backend is an analytic stand-in; no MuJoCo backend is declared.
    fidelity = {
        "engine": "analytic:FakeMyoFullBody",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "seed_control": "none",
            "notes": "the native reset takes a JAX random key, not an integer seed; this driver passes no key, so "
                     "the environment uses its default key 0 and no operator seed selects a trajectory.  The "
                     "environment's dynamics were not run and the fake was not compared with them.",
        },
        "timestep_ms": 10.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is a pure Python stand-in: it models a tick, a placeholder muscle-excitation state "
            "and a placeholder observation row, but no MuJoCo physics, Hill-type muscle dynamics, contacts, "
            "tendons or sensors, and it was never compared with the upstream environment",
            "the model file and its assets are supplied by the separate musclemimic_models package "
            "(myofullbody.py:449-453) and are not in this clone; the clone ships no MJCF and the card lists no model",
            "the action vector length and the observation vector length are model-dependent and are not "
            "hard-coded here: the environment takes every actuator name (myofullbody.py:394-407) and the README "
            "lists 354 muscles with finger muscles disabled (README.md:48), but the actual model was not loaded",
            "the fake accepts a placeholder action width and returns a placeholder observation width; the real "
            "environment's dimensions are not exposed by this package or verified",
            "only the default configuration is modelled (disable_fingers True, default observation options, "
            "DefaultControl, horizon 1000); other constructor options are not exposed",
            "one cap.world.step.v1 tick is one MuJoCo environment step, which runs n_substeps physics substeps "
            "of 0.002 s each (myofullbody.py:56-57, mujoco_base.py:1326-1333), so the default control step is 10 ms",
            "the native reset takes a JAX key, not an integer seed, so the reset seed input is not applied and the "
            "fidelity determinism kind is none",
            "snapshot and restore are not offered: this driver declares no checkpoint methods",
            "MuJoCo, JAX, flax and musclemimic_models were not installed or run where the gate ran; only the fake "
            "backend is declared",
            "no physical device is modelled and nothing was validated against hardware",
        ],
    }

    # ------------------------------------------------------------------ hooks
    def setup(self) -> None:
        self._tick = 0
        self._episode = 0
        self._reward = 0.0
        self._terminated = False
        self._truncated = False
        self._last_observation = {"values": []}
        self._info = {}

    # ------------------------------------------------------------------ state
    @read("observation", type="object",
          description="Last observation of the simulation as a flat row in the environment's observation order",
          properties={"values": Field("array", items="number", unit="1",
                                      description="Observation values in the environment's observation order")})
    def observation(self) -> dict:
        return dict(getattr(self, "_last_observation", {}))

    @read("reward", type="number", unit="1", description="Reward of the last step")
    def reward(self) -> float:
        return float(getattr(self, "_reward", 0.0))

    @read("terminated", type="boolean", description="Whether the last step reached an absorbing terminal state")
    def terminated(self) -> bool:
        return bool(getattr(self, "_terminated", False))

    @read("truncated", type="boolean",
          description="Whether the last step reached the episode horizon without an absorbing state")
    def truncated(self) -> bool:
        return bool(getattr(self, "_truncated", False))

    @read("tick", type="integer", unit="1", description="Environment steps applied since the last reset")
    def tick(self) -> int:
        return int(getattr(self, "_tick", 0))

    @read("episode", type="integer", unit="1", description="Resets served by this backend")
    def episode(self) -> int:
        return int(getattr(self, "_episode", 0))

    @read("info", type="object", description="Task information returned by the last step")
    def info(self) -> dict:
        return dict(getattr(self, "_info", {}))

    # ---------------------------------------------------------------- actions
    @action(cap="cap.world.step.v1",
            description="Advance the MyoFullBody simulation by bounded steps with one normalized muscle command",
            input={
                "ticks": Field("integer", unit="1",
                               description="Environment steps to advance; the command is applied at every step"),
                "action": Field("object", description="Normalized muscle command, one value per actuator",
                                properties={
                                    "values": Field("array", items="number", unit="1",
                                                    description="Normalized muscle excitation in the model's actuator "
                                                                "order; the vector length is model-dependent",
                                                    limit=Limit(min=-1.0, max=1.0, unit="1",
                                                                source="upstream_code",
                                                                ref=f"{ENV}:317-322")),
                                }),
            })
    def step(self, ticks: int, action: dict) -> dict:
        if self._terminated or self._truncated:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "the episode has ended; reset the environment before stepping")
        if not isinstance(ticks, int) or isinstance(ticks, bool) or ticks < 1:
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "ticks must be a positive integer")
        values = _action_values(action)
        total_reward = 0.0
        for _ in range(ticks):
            self.check_cancelled()
            result = self.native.step(_native_action(values))
            try:
                observation, reward, absorbing, done, info = result
            except (TypeError, ValueError) as exc:
                raise DriverFailed("MHS.ADAPTER.SHIM_FAILED", "MyoFullBody.step did not return a five-tuple") from exc
            self._tick += 1
            self._last_observation = _observation_object(observation)
            self._reward = float(_plain_scalar(reward))
            total_reward += self._reward
            self._terminated = bool(_plain_scalar(absorbing, flag=True))
            done = bool(_plain_scalar(done, flag=True))
            self._truncated = done and not self._terminated
            self._info = dict(info or {}) if isinstance(info, Mapping) else {"info": info}
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
            }),
        }

    @action(cap="cap.world.reset.v1",
            description="Reset the MyoFullBody scene and return its initial observation",
            input={
                "seed": Field("integer", unit="1", required=False,
                              description="Accepted for the class contract; the native reset takes a JAX key, not an "
                                          "integer seed, so this value is not applied and the output seed is 0"),
                "scenario": Field("string", required=False,
                                  description="Named scenario; only 'default' is served"),
                "options": Field("object", required=False,
                                 description="Reset options; the upstream reset takes none, so a non-empty object "
                                             "is refused"),
            })
    def reset_world(self, seed=None, scenario=None, options=None) -> dict:
        if scenario not in (None, "default"):
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "only the 'default' scenario is served")
        if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int) or seed < 0):
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "seed must be a non-negative integer")
        if options:
            if not isinstance(options, Mapping):
                raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "options must be an object")
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                               "the native reset takes no options; pass an empty object or omit it")
        observation = self.native.reset()
        self._tick = 0
        self._episode += 1
        self._reward = 0.0
        self._terminated = False
        self._truncated = False
        self._last_observation = _observation_object(observation)
        self._info = {}
        return {"observation": dict(self._last_observation), "seed": 0}
