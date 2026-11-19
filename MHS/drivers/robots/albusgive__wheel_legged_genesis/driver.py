"""OpenMHS driver for gh.albusgive/wheel_legged_genesis: the WheelLeggedEnv Genesis environment.

The card names the repository as a ``sim-env`` with a ``python-object`` family and a ``PythonObjectDriver`` helper.
The upstream entry is a plain Python class, not a Gymnasium environment: ``WheelLeggedEnv`` has no ``action_space``,
no ``observation_space`` and no ``env_id``.  It takes seven configuration dictionaries, a device string and a
``train_mode`` flag, and it exposes ``step(action)`` returning a five-tuple
``(observation, privileged_observation, reward, reset_flag, extras)`` and ``reset()`` returning
``(observation, None)`` (``locomotion/wheel_legged_env.py:16-17``, ``:391-519`` and ``:602-605``).  A direct
``Driver`` over that class, with the package's own fake backend, expresses the whole interface; the card's
PythonObjectDriver would have to map a 286-value observation row and a stateful step loop through a command table,
which adds no fidelity.  See RESULT.json, "DEVIATION FROM THE CARD".

The bound capabilities are ``cap.world.step.v1`` and ``cap.world.reset.v1``:

* a step takes the catalogue ``ticks`` count and eight action values.  One tick is one ``WheelLeggedEnv.step``
  call, i.e. one ``gs.Scene.step`` at the 0.01 s control period (``locomotion/wheel_legged_env.py:35`` and
  ``:403``).  The eight values are the joint and wheel action vector the training configuration uses
  (``locomotion/wheel_legged_train.py:62`` and ``:86-106``); ``WheelLeggedEnv.step`` clips them to
  ``env_cfg["clip_actions"]``, which the training configuration sets to 100.0
  (``locomotion/wheel_legged_env.py:392``, ``locomotion/wheel_legged_train.py:160``).  ``cap.world.seed.v1`` is
  not bound: the upstream class defines no seed method; the reset action seeds the process RNGs (Python random,
  NumPy and Torch) with its own seed input instead.
* a reset calls ``WheelLeggedEnv.reset()``.  The upstream reset returns the existing ``obs_buf`` without
  recomputing it; the driver returns exactly the native observation and the fake returns a fresh one, as recorded
  in the fidelity gaps.

The device is simulated (R0). The action interval is operator_required; the example overlay supplies fake-test
bounds only. The fake is a pure Python analytic stand-in, not the Genesis engine; it was never compared with the
upstream simulator, which needs a source build of Genesis, PyTorch, OpenCV and the 123 MB of robot assets
(``README.md:11-13``, ``pyproject.toml:8-14``).  This package is model-authored and unreviewed: it is checked on
the fake backend only.  The pinned commit is d34f4a13cf74216063df276a77efda5b784ecdbf.
"""

from collections.abc import Mapping
import math
import random

from mhs import canonical
from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, read

ENV = "locomotion/wheel_legged_env.py"
TRAIN = "locomotion/wheel_legged_train.py"
README = "README.md"
PYPROJECT = "pyproject.toml"

#: The action vector of the configured robot: six leg joints and two wheel joints (train.py:62, :86-106).
ACTION_DIM = 8
#: The configured observation: a nine-row history of 28 values, the current 28-value slice and six commands
#: (train.py:166-168, :217; env.py:511-517).
OBSERVATION_DIM = 286
#: The control period: 0.01 s (env.py:35).
TIMESTEP_MS = 10.0

def _plain_scalar(value, *, flag=False):
    """One Python scalar from a native reward or reset flag (a tensor, a one-element list or a scalar)."""
    if hasattr(value, "tolist"):
        value = value.tolist()
    while isinstance(value, (list, tuple)) and len(value) == 1:
        value = value[0]
    if (not isinstance(value, (int, float)) or (isinstance(value, bool) and not flag)
            or not math.isfinite(value) or (flag and value not in (0, 1))):
        raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID", "native reward or flag is missing or invalid")
    return value


def _plain(value):
    """A JSON-safe copy of a native buffer, tensor, array, mapping or scalar."""
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID", "native extras contain a non-JSON value")


def _observation_row(value) -> dict:
    """The first environment's observation as a JSON object with the flat 286-value row."""
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, Mapping):
        value = value.get("values", list(value.values()))
    if isinstance(value, (list, tuple)) and value and isinstance(value[0], (list, tuple)):
        value = value[0]
    if isinstance(value, (list, tuple)):
        return {"values": [float(item) for item in value]}
    return {"values": [float(value)]}


def _action_array(values):
    """The native action: a two-dimensional tensor of shape [1, 8], as ``WheelLeggedEnv.step`` expects."""
    try:
        import torch
    except ImportError:  # the fake accepts a plain list; Genesis needs Torch, which the clone installs
        return [list(values)]
    return torch.tensor([list(values)], dtype=torch.float32)


def _action_values(action) -> list:
    if not isinstance(action, Mapping):
        raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "action must be an object")
    values = action.get("values")
    if not isinstance(values, (list, tuple)):
        raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "action.values must be an array")
    if len(values) != ACTION_DIM:
        raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                           f"action.values must have {ACTION_DIM} values, got {len(values)}")
    out = []
    for value in values:
        number = float(value)
        if number != number or number in (float("inf"), float("-inf")):
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "action values must be finite")
        out.append(number)
    return out


def _seed_process_rngs(seed: int) -> None:
    """Seed the process generators the upstream environment draws from (Python random, NumPy and Torch).

    ``WheelLeggedEnv`` has no seed method; its randomness comes from ``torch.rand``/``torch.randn`` and
    ``torch.randint`` (``locomotion/wheel_legged_env.py:9-12`` and ``:552``).  NumPy and Python random are seeded
    as well because the fake uses the standard generator.
    """
    random.seed(int(seed))
    try:
        import numpy as np
    except ImportError:
        np = None
    if np is not None:
        np.random.seed(int(seed) % (2 ** 32))
    try:
        import torch
    except ImportError:
        torch = None
    if torch is not None:
        torch.manual_seed(int(seed))


class WheelLeggedGenesis(Driver):
    device_id = "wheel-legged-genesis"
    device_kind = "world.sim"
    resource_id = "world"
    mode = "simulated"
    risk = "R0"
    native = "locomotion.wheel_legged_env:WheelLeggedEnv"
    backends = {"fake": ".fake:FakeWheelLeggedEnv"}
    display_name = "Wheel-legged Genesis environment (CJ-003)"
    vendor, model = "albusgive", "wheel_legged_genesis WheelLeggedEnv"
    tags = ["wheel-legged", "robot", "genesis", "simulation", "reinforcement-learning", "cj-003"]
    facts = [
        Fact("WheelLeggedEnv is the concrete Genesis environment class of the repository",
             source="upstream_code", ref=f"{ENV}:15"),
        Fact("The environment imports genesis as gs", source="upstream_code", ref=f"{ENV}:3"),
        Fact("The constructor takes num_envs, the env, observation, reward, command, curriculum, domain "
             "randomization and terrain configurations, robot_morphs, show_viewer, num_view, device and "
             "train_mode", source="upstream_code", ref=f"{ENV}:16-17"),
        Fact("The control period is 0.01 s, 100 Hz", source="upstream_code", ref=f"{ENV}:35"),
        Fact("The Genesis scene uses the control period and five physics substeps", source="upstream_code",
             ref=f"{ENV}:48-51"),
        Fact("The training configuration sets num_actions to 8", source="upstream_code", ref=f"{TRAIN}:62"),
        Fact("The training configuration lists the left and right hip, thigh, calf and wheel joints",
             source="upstream_code", ref=f"{TRAIN}:86-106"),
        Fact("The training configuration sets num_obs to 286, num_slice_obs to 28 and history_length to 9",
             source="upstream_code", ref=f"{TRAIN}:166-168"),
        Fact("The training configuration sets num_commands to 6", source="upstream_code", ref=f"{TRAIN}:217"),
        Fact("The observation row concatenates the history buffer, the current slice and the scaled commands",
             source="upstream_code", ref=f"{ENV}:511-517"),
        Fact("step clips every action to the configured clip_actions range", source="upstream_code",
             ref=f"{ENV}:391-392"),
        Fact("The training configuration sets clip_actions to 100.0", source="upstream_code", ref=f"{TRAIN}:160"),
        Fact("step advances the Genesis scene once with scene.step()", source="upstream_code", ref=f"{ENV}:403"),
        Fact("step returns the observation, None for the privileged observation, the reward buffer, the reset "
             "flag buffer and the extras", source="upstream_code", ref=f"{ENV}:519"),
        Fact("reset sets reset_buf, calls reset_idx for every environment and returns the existing obs_buf and "
             "None", source="upstream_code", ref=f"{ENV}:602-605"),
        Fact("reset_idx resets the DOF and base state and the episode buffers but does not recompute the "
             "observation buffers", source="upstream_code", ref=f"{ENV}:527-600"),
        Fact("The episode timeout is marked in extras['time_outs'] for every environment whose "
             "episode_length_buf exceeds max_episode_length", source="upstream_code", ref=f"{ENV}:472-474"),
        Fact("check_termination sets reset_buf from the episode length, the roll and pitch limits and contact "
             "with the listed links", source="upstream_code", ref=f"{ENV}:607-618"),
        Fact("When train_mode is true, step calls reset_idx for every environment whose reset_buf is set before "
             "it computes the reward and observation", source="upstream_code", ref=f"{ENV}:475-478"),
        Fact("The training configuration sets episode_length_s to 20.0", source="upstream_code", ref=f"{TRAIN}:155"),
        Fact("The training script initializes Genesis with the GPU backend", source="upstream_code", ref=f"{TRAIN}:281"),
        Fact("The training script defaults num_envs to 8192", source="upstream_code", ref=f"{TRAIN}:277"),
        Fact("The training configuration carries a runner seed of 1", source="upstream_code", ref=f"{TRAIN}:54"),
        Fact("The install dependencies are genesis-world, tensorboard, pygame, torch and the in-tree rsl-rl",
             source="upstream_code", ref=f"{PYPROJECT}:8-14"),
        Fact("The README states that the repository is reinforcement learning of wheel-legged robots based on "
             "Genesis and that sim2sim in MuJoCo is supported", source="vendor_doc", ref=f"{README}:1-4"),
        Fact("The README says Genesis 0.2.1 cannot be installed from pip and must be a local installation of the "
             "main branch because of an API update", source="vendor_doc", ref=f"{README}:11-13"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the last observation and tick stay readable")
    #: The model as deployed on the checked fake backend: an analytic F0 stand-in, not the Genesis engine.
    fidelity = {
        "engine": "analytic:FakeWheelLeggedEnv",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "WheelLeggedEnv has no seed method; the reset action seeds Python random, NumPy and Torch "
                     "with its seed input (default 0) before calling the native reset.  The fake draws its "
                     "initial joint positions from Python random, so the same seed repeats a reset; it was "
                     "never compared with the upstream simulator",
        },
        "timestep_ms": TIMESTEP_MS,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is a pure Python analytic stand-in: it models the 8-value action, the 10 ms tick, "
            "the 286-value observation layout, a one-step action latency and the episode length, but no Genesis "
            "engine, rigid-body dynamics, contacts, actuators, terrain, sensors, reward terms or domain "
            "randomization, and it was never compared with the upstream environment",
            "the upstream environment needs Genesis from the main branch, PyTorch, OpenCV, pygame and the "
            "repository's MJCF/URDF/terrain assets (README.md:11-13, pyproject.toml:8-14); it was not installed "
            "or run where the gate ran",
            "WheelLeggedEnv.reset sets reset_buf and calls reset_idx, then returns the existing obs_buf "
            "(locomotion/wheel_legged_env.py:602-605); reset_idx does not recompute the observation buffers, so "
            "the upstream reset observation can be stale.  The fake returns a fresh initial observation, which "
            "differs from that native path",
            "when train_mode is true the upstream step auto-resets the environments whose reset_buf is set "
            "(locomotion/wheel_legged_env.py:477); the driver reports the terminal flags and requires an "
            "explicit cap.world.reset.v1 before the next step instead of exposing the auto-reset",
            "the real environment is vectorized over num_envs (the training script defaults to 8192, "
            "locomotion/wheel_legged_train.py:277); the driver models one instance and returns its first "
            "observation row, so num_envs above 1 is not exposed",
            "only the default training configuration of locomotion/wheel_legged_train.py get_cfgs is modelled "
            "(8 actions, 286 observations, clip_actions 100.0, 20 s episodes and train_mode true); another "
            "env_cfg changes the action clip and the observation layout",
            "the fake reward, command vector, observation history and wheel and joint kinematics are placeholder "
            "test data, not the reward terms of locomotion/wheel_legged_env.py:700-940",
            "snapshot and restore are not offered: WheelLeggedEnv exposes no get_state/set_state",
            "no physical device is modelled and nothing was validated against one",
        ],
    }

    # ------------------------------------------------------------------ hooks
    def setup(self) -> None:
        self._tick = 0
        self._episode = 0
        self._seed = 0
        self._reward = 0.0
        self._terminated = False
        self._truncated = False
        self._last_observation = {}
        self._info = {}

    # ------------------------------------------------------------------ state
    @read("observation", type="object",
          description="Last observation of the simulation (the first instance's flat 286-value row)")
    def observation(self) -> dict:
        return dict(getattr(self, "_last_observation", {}))

    @read("reward", type="number", unit="1", description="Reward of the last step")
    def reward(self) -> float:
        return float(getattr(self, "_reward", 0.0))

    @read("terminated", type="boolean", description="Whether the last step reached a terminal state")
    def terminated(self) -> bool:
        return bool(getattr(self, "_terminated", False))

    @read("truncated", type="boolean", description="Whether the last step reached the episode length")
    def truncated(self) -> bool:
        return bool(getattr(self, "_truncated", False))

    @read("tick", type="integer", unit="1", description="Environment steps applied since the last reset")
    def tick(self) -> int:
        return int(getattr(self, "_tick", 0))

    @read("episode", type="integer", unit="1", description="Resets served by this backend")
    def episode(self) -> int:
        return int(getattr(self, "_episode", 0))

    @read("seed", type="integer", unit="1", description="Seed applied by the last reset")
    def seed(self) -> int:
        return int(getattr(self, "_seed", 0))

    @read("info", type="object", description="Extras returned by the last step")
    def info(self) -> dict:
        return dict(getattr(self, "_info", {}))

    # ---------------------------------------------------------------- actions
    @action(cap="cap.world.step.v1",
            description="Advance the wheel-legged simulation by bounded ticks with one eight-value action",
            input={
                "ticks": Field("integer", unit="1",
                               description="Environment steps to advance; the action is applied at every step"),
                "action": Field("object", description="Eight-value joint and wheel action of the one instance",
                                properties={
                                    "values": Field("array", items="number", length=ACTION_DIM, unit="1",
                                                    description="Joint and wheel action, one value per joint",
                                                    limit=Limit.operator_required(
                                                        reason="The deployment must supply both action "
                                                        "bounds for its env_cfg; the training configuration shows "
                                                        "clip_actions=100.0 but no single cited span states the "
                                                        "complete signed numeric interval. The example overlay "
                                                        "is for fake checks only.")),
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
            result = self.native.step(_action_array(values))
            if isinstance(result, tuple) and len(result) == 5:
                observation, _privileged, reward, done, extras = result
            else:
                raise DriverFailed("MHS.ADAPTER.SHIM_FAILED",
                                   "WheelLeggedEnv.step did not return a five-tuple")
            self._tick += 1
            self._last_observation = _observation_row(observation)
            self._reward = float(_plain_scalar(reward))
            total_reward += self._reward
            done = bool(_plain_scalar(done, flag=True))
            if not isinstance(extras, Mapping) or "time_outs" not in extras:
                raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID", "native extras have no timeout flag")
            time_out = bool(_plain_scalar(extras["time_outs"], flag=True))
            # reset_buf includes timeouts (env.py:608); a pure timeout is a truncation.
            self._terminated = done and not time_out
            self._truncated = time_out
            self._info = _plain(extras) if isinstance(extras, Mapping) else {"extras": _plain(extras)}
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
            description="Reset the wheel-legged scene and return its initial observation",
            input={
                "seed": Field("integer", unit="1", required=False,
                              description="Seed applied to the process generators before the reset; default 0"),
                "scenario": Field("string", required=False,
                                  description="Named scenario; only 'default' is served"),
                "options": Field("object", required=False,
                                 description="Reset options; WheelLeggedEnv.reset takes none and they are ignored"),
            })
    def reset_world(self, seed=None, scenario=None, options=None) -> dict:
        if scenario not in (None, "default"):
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "only the 'default' scenario is served")
        if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int) or seed < 0):
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "seed must be a non-negative integer")
        chosen = 0 if seed is None else int(seed)
        _seed_process_rngs(chosen)
        result = self.native.reset()
        if isinstance(result, tuple) and len(result) >= 1:
            observation = result[0]
        else:
            observation = result
        self._tick = 0
        self._episode += 1
        self._seed = chosen
        self._reward = 0.0
        self._terminated = False
        self._truncated = False
        self._last_observation = _observation_row(observation)
        self._info = {}
        return {"observation": dict(self._last_observation), "seed": chosen}
