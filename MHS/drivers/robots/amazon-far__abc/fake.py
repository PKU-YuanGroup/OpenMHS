"""Fake backend of the ABC YAM driver: a small kinematic stand-in for ``abc_sim.env.MuJoCoYAMEnv``.

Why a fake: the acceptance gate runs where the upstream package is not installed (its dependencies are
``mujoco~=3.8.0`` and ``gymnasium>=1.1``, ``pyproject.toml:15`` and ``:21``), and package code never imports the clone.
This module re-implements the public call shape of the class the driver names as ``native`` (``reset``, ``step``,
``step_chunk``, ``get_obs``, ``forget_arm_state``, ``get_init_q`` and ``close``; gate G7) and the spaces the bridge
reads.  It is an analytical stand-in, not a recording and not a physics simulation.

What is modelled (all lines of the clone at the pinned commit):

* the 14D policy-space action and state order [left_j1..6, left_gripper, right_j1..6, right_gripper]
  (``abc_sim/env.py:75-76``, ``abc_sim/README.md:94-98``);
* the action space ``Box(-1.0, 1.0, (14,))`` (``abc_sim/env.py:175-179``) and the observation dictionary with one
  image per camera, a 14-element state, per-camera masks, a prompt and per-camera timestamps
  (``abc_sim/env.py:130-173``);
* ``reset`` preserving the current 14D arm pose across resets unless ``forget_arm_state`` is called
  (``abc_sim/env.py:304-315``, ``:498-510``);
* ``step`` returning the Gymnasium 5-tuple and ``step_chunk`` stopping at the first terminal or truncated step
  (``abc_sim/env.py:380-391``, ``:393-417``);
* truncation at ``max_episode_steps`` and termination only through ``terminate_on_success`` plus an evaluator
  (``abc_sim/env.py:461-470``), with reward 0.0 when no evaluator exists (``abc_sim/env.py:451-459``).

What this is not: the upstream MuJoCo environment.  There are no rigid bodies, contacts, actuators, task evaluator,
randomizer or rendered scene here; every step simply makes the commanded 14D policy values the new state.  The images
are tiny placeholder arrays: the upstream constructor renders ``(3, camera_height, camera_width)`` uint8 images and
defaults to 480x640 (``abc_sim/env.py:87-88``); the size is configurable.  These differences are stated in the
driver's fidelity ``gaps`` and in RESULT.json.

Nothing here talks to a device.
"""

from dataclasses import dataclass


@dataclass
class FakeRandomizationState:
    """Placeholder shape of randomization/core.py:50-73; no sampling or physics is modelled."""

    seed: int

    def to_dict(self):
        return {"seed": self.seed, "object_states": {}, "scale_states": {},
                "metadata": {"fixture": "placeholder"}}  # placeholder

# abc_sim/env.py:75-76 and abc_sim/config.py:92-122: the base configuration has the two arms left and right.
ROBOT_NAMES = ("left", "right")
# abc_sim/config.py:69-90: the base configuration's three cameras.
CAMERA_NAMES = ("top", "left", "right")
# abc_sim/env.py:126: seven values per configured robot.
ACTION_DIM = 7 * len(ROBOT_NAMES)
# The image size below is test data, not the upstream default: upstream defaults to 3x480x640 (env.py:87-88).
IMAGE_HEIGHT = 4  # placeholder
IMAGE_WIDTH = 4  # placeholder
# abc_sim/env.py:89-90: the default physics step and decimation, about 0.034 s per control transition.
DEFAULT_PHYSICS_DT = 0.002  # placeholder: upstream constructor default
DEFAULT_CONTROL_DECIMATION = 17  # placeholder: upstream constructor default


class Discrete:
    """Duck-typed ``gymnasium.spaces.Discrete``: the integers ``start .. start + n - 1``."""

    def __init__(self, n, start=0):
        self.n = int(n)
        self.start = int(start)
        self.shape = ()
        self.dtype = "int64"


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high, shape=None, dtype="float32"):
        lows = list(low) if isinstance(low, (list, tuple)) else [low]
        highs = list(high) if isinstance(high, (list, tuple)) else [high]
        self.low = [float(value) for value in lows]
        self.high = [float(value) for value in highs]
        self.shape = tuple(shape) if shape is not None else (len(self.low),)
        self.dtype = dtype


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: named subspaces."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


class Text:
    """The descriptive fields of ``gymnasium.spaces.Text`` (the bridge derives no observation limits from it)."""

    def __init__(self, max_length=4096, min_length=0, charset=None):
        self.max_length = int(max_length)
        self.min_length = int(min_length)
        self.charset = charset
        self.shape = ()
        self.dtype = "str"


def _image(height, width):
    """One placeholder ``(3, H, W)`` uint8 image; the upstream renders a real camera frame."""
    return [[[0 for _ in range(width)] for _ in range(height)] for _ in range(3)]


def _stack_observations(observations):
    """The shape of ``MuJoCoYAMEnv._stack_obs`` for these plain lists (``abc_sim/env.py:642-655``)."""
    stacked = {}
    for key in observations[0]:
        first = observations[0][key]
        if isinstance(first, str):
            stacked[key] = first
        elif isinstance(first, dict):
            stacked[key] = {
                name: [observation[key][name] for observation in observations]
                for name in first
            }
        else:
            stacked[key] = [observation[key] for observation in observations]
    return stacked


class FakeMuJoCoYAMEnv:
    """Kinematic stand-in for ``abc_sim.env.MuJoCoYAMEnv`` with its public call shape (gate G7)."""

    def __init__(
        self,
        prompt="throw plastic bottles in bin",  # placeholder: the default task's prompt (task_specs.py:45)
        max_episode_steps=None,
        terminate_on_success=False,
        render_cameras=True,
        camera_height=IMAGE_HEIGHT,  # placeholder: test data
        camera_width=IMAGE_WIDTH,  # placeholder: test data
        physics_dt=DEFAULT_PHYSICS_DT,  # placeholder: upstream constructor default
        control_decimation=DEFAULT_CONTROL_DECIMATION,  # placeholder: upstream constructor default
        chunk_dim=30,  # placeholder: upstream constructor default
        **_options,
    ):
        if max_episode_steps is not None and max_episode_steps < 1:
            raise ValueError(f"max_episode_steps must be >= 1 or None, got {max_episode_steps}")
        self.prompt = prompt
        self.max_episode_steps = max_episode_steps
        self.terminate_on_success = bool(terminate_on_success)
        self.chunk_dim = int(chunk_dim)
        self.camera_names = list(CAMERA_NAMES)
        self.robot_names = list(ROBOT_NAMES)
        self.single_timestep_action_dim = ACTION_DIM
        self.action_dim = ACTION_DIM
        self.chunk_action_dim = ACTION_DIM * self.chunk_dim
        self.cur_step = 0
        self._physics_dt = float(physics_dt)
        self._control_decimation = int(control_decimation)
        self._control_period_s = self._physics_dt * self._control_decimation
        self._state = [0.0] * ACTION_DIM  # placeholder: the upstream first reset uses each robot's configured init_q
        self._arm_state_initialized = False
        self._last_seed = None
        self._camera_height = int(camera_height)
        self._camera_width = int(camera_width)

        # abc_sim/env.py:130-173: the observation dictionary.
        self.observation_space = Dict(
            {
                "images": Dict(
                    {
                        name: Box(0, 255, shape=(3, int(camera_height), int(camera_width)), dtype="uint8")
                        for name in self.camera_names
                    }
                ),
                "state": Box([float("-inf")] * ACTION_DIM, [float("inf")] * ACTION_DIM,
                             shape=(ACTION_DIM,), dtype="float32"),
                "masks": Dict({name: Discrete(2) for name in self.camera_names}),
                "prompt": Text(max_length=4096, min_length=0),
                "camera_timestamps": Dict(
                    {name: Box(float("-inf"), float("inf"), shape=(), dtype="float64")
                     for name in self.camera_names}
                ),
            }
        )
        # abc_sim/env.py:175-179: the upstream action space this fake copies (action_space_ref cites that range).
        self.action_space = Box([-1.0] * ACTION_DIM, [1.0] * ACTION_DIM, shape=(ACTION_DIM,), dtype="float32")
        # abc_sim/env.py:181-186.
        self.chunk_action_space = Box([-1.0] * (self.chunk_dim * ACTION_DIM),
                                      [1.0] * (self.chunk_dim * ACTION_DIM),
                                      shape=(self.chunk_dim, ACTION_DIM), dtype="float32")

    def get_init_q(self):
        """The flat 14D initial state (``abc_sim/env.py:636-640``); the fake's values are placeholders."""
        return [0.0] * ACTION_DIM  # placeholder

    def forget_arm_state(self):
        """Drop the carried arm pose so the next reset starts from the initial state (``abc_sim/env.py:498-500``)."""
        self._arm_state_initialized = False

    def get_obs(self):
        """The observation dictionary of ``abc_sim/env.py:596-619`` with placeholder images."""
        sim_time = self.cur_step * self._control_period_s
        return {
            "images": {name: _image(self._camera_height, self._camera_width) for name in self.camera_names},
            "masks": {name: True for name in self.camera_names},
            "state": list(self._state),
            "prompt": self.prompt,
            "camera_timestamps": {name: sim_time for name in self.camera_names},
        }

    def reset(self, *, seed=None, options=None, randomize=True):
        """Preserve the arm pose across resets like ``abc_sim/env.py:304-315`` and return ``(obs, info)``."""
        if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int) or seed < 0):
            raise ValueError(f"seed must be a non-negative integer, got {seed!r}")
        del randomize, options  # the fake has no randomizer and no reset request to honour
        self._last_seed = seed
        if not self._arm_state_initialized:
            self._state = self.get_init_q()
        self._arm_state_initialized = True
        self.cur_step = 0
        # env.py:375-378 returns the native RandomizationState object in info, not its JSON form.
        return self.get_obs(), {"randomization": FakeRandomizationState(seed or 0)}

    def step(self, action, *, render_obs=True):
        """Make one 14D command the next policy state and return the Gymnasium 5-tuple (``abc_sim/env.py:380-391``)."""
        values = list(action)
        if len(values) != ACTION_DIM:
            raise ValueError(
                "step() expects one 14D policy action; "
                "use step_chunk() for a (chunk_dim, 14) action chunk"
            )
        self._state = [float(value) for value in values]
        self.cur_step += 1
        obs = self.get_obs() if render_obs else None
        reward = 0.0
        info = {}
        # abc_sim/env.py:451-470 with no task evaluator attached.
        terminated = False
        time_limit_reached = self.max_episode_steps is not None and self.cur_step >= self.max_episode_steps
        truncated = bool(time_limit_reached and not terminated)
        info["episode_step"] = self.cur_step
        info["terminate_on_success"] = self.terminate_on_success
        info["time_limit_reached"] = bool(time_limit_reached)
        if self.max_episode_steps is not None:
            info["max_episode_steps"] = self.max_episode_steps
        return obs, reward, terminated, truncated, info

    def step_chunk(self, action_chunk):
        """Apply up to ``chunk_dim`` 14D actions, stopping at a terminal or truncated step (``abc_sim/env.py:393-417``)."""
        if hasattr(action_chunk, "tolist"):
            action_chunk = action_chunk.tolist()
        values = list(action_chunk)
        if values and isinstance(values[0], (list, tuple)):
            values = [value for row in values for value in row]
        expected = self.chunk_dim * ACTION_DIM
        if len(values) != expected:
            raise ValueError(
                f"step_chunk() expects {self.chunk_dim} actions of size {ACTION_DIM}; got {len(values)} values"
            )
        actions = [values[index * ACTION_DIM:(index + 1) * ACTION_DIM] for index in range(self.chunk_dim)]
        observations = []
        reward, terminated, truncated, info = 0.0, False, False, {}
        for action in actions:
            obs, reward, terminated, truncated, info = self.step(action, render_obs=True)
            observations.append(obs)
            if terminated or truncated:
                break
        return observations[-1], _stack_observations(observations), reward, terminated, truncated, info

    def close(self):
        """Release the fake's state; the upstream closes its camera backend (``abc_sim/env.py:485-486``)."""
        self._state = [0.0] * ACTION_DIM  # placeholder


def connect(**options):
    """Exercise the same reset-info adapter as the live simulator without importing abc_sim."""
    from .sim import ResetInfoAdapter

    return ResetInfoAdapter(FakeMuJoCoYAMEnv(**options))
