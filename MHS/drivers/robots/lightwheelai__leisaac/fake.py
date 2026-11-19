"""Fake backend for the LeIsaac SO101 PickOrange Direct environment.

The gate cannot import the upstream package: it needs Isaac Sim, the IsaacLab
2.3.0 extra and a GPU (source/leisaac/pyproject.toml:21 and :41), and package
code never imports the clone.  This module is a pure-Python analytic F0
stand-in for ``leisaac.tasks.pick_orange.direct.pick_orange_env:PickOrangeEnv``:
it keeps the environment surface (``reset``, ``step``, ``close``,
``action_space`` and ``observation_space``) and the six-value SO101 joint action
of the direct task, but it models no physics.

Every constant that is not test data cites the clone at
24d3bcd3f1e4585740fc79921782c41617237812.  The start offsets, camera stand-in
sizes, image pixels, joint velocities, end-effector state and subtask flags are
test data and are marked ``# placeholder``; they are never facts, limits or
references.  The fidelity gaps in ``driver.py`` disclose them.

What this is not: the upstream environment.  There is no Isaac Sim, no PhysX
contact, no torch, no domain randomization, no rendering and no vectorization.
The action is accepted in the same six-value order and multiplied by the
upstream ``action_scale`` of 1.0; the joints follow the target directly.
"""

import math
import random

# source/leisaac/leisaac/tasks/template/direct/single_arm_env.py:33 (`action_space = 6`)
ACTION_DIM = 6
# source/leisaac/leisaac/tasks/template/direct/single_arm_env.py:64-65
DECIMATION = 1
EPISODE_LENGTH_S = 25.0
# dependencies/IsaacLab/source/isaaclab/isaaclab/sim/simulation_cfg.py:346 (`dt = 1.0 / 60.0`)
SIM_DT_S = 1.0 / 60.0
# dependencies/IsaacLab/source/isaaclab/isaaclab/envs/direct_rl_env.py:264-267 and
# source/leisaac/leisaac/tasks/template/direct/single_arm_env.py:162-165:
# max_episode_length = ceil(episode_length_s / (sim.dt * decimation)), and the time_out
# comparison is episode_length_buf >= max_episode_length - 1.
MAX_EPISODE_STEPS = math.ceil(EPISODE_LENGTH_S / (SIM_DT_S * DECIMATION)) - 1
# source/leisaac/leisaac/tasks/template/direct/single_arm_env.py:49 (`action_scale = 1.0`)
ACTION_SCALE = 1.0
# The real cameras are 640 x 480 x 3, width x height (source/leisaac/leisaac/tasks/template/single_arm_env_cfg.py:50-83).
# A smaller stand-in keeps one receipt small enough for the gate; this is test data.
IMAGE_SHAPE = (1, 4, 4, 3)  # placeholder
START_JITTER = 0.01  # placeholder: the fake's initial joint offsets
SUBTASK_TERMS = (
    "pick_orange001",
    "put_orange001_to_plate",
    "pick_orange002",
    "put_orange002_to_plate",
    "pick_orange003",
    "put_orange003_to_plate",
)


def _fill(value, shape):
    """A nested list of ``value`` with the given shape (spaces use nested low/high lists)."""

    if not shape:
        return value
    return [_fill(value, shape[1:]) for _ in range(int(shape[0]))]


class Box:
    """Duck-typed one-dimensional or multi-dimensional ``gymnasium.spaces.Box``."""

    def __init__(self, low, high, shape):
        self.shape = tuple(int(item) for item in shape)
        self.low = _fill(low, self.shape)
        self.high = _fill(high, self.shape)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the bridge reads ``spaces``."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)
        self.shape = ()
        self.dtype = "dict"


def _flatten(value):
    """The flat list of numbers in an action array/tensor, in row-major order."""

    raw = value.tolist() if hasattr(value, "tolist") else value
    out = []

    def walk(item):
        if isinstance(item, (list, tuple)):
            for element in item:
                walk(element)
        else:
            out.append(float(item))

    walk(raw)
    return out


class FakePickOrangeEnv:
    """A pure-Python F0 stand-in with the native ``reset``, ``step`` and ``close`` surface."""

    def __init__(self, cfg=None, render_mode=None, **kwargs):
        if render_mode is not None:
            raise ValueError("the fake PickOrange environment cannot render; use render_mode=None")
        del cfg, kwargs
        # The upstream space is a gymnasium.spaces.Box with one bound per action (spec_to_gym_space(6)).
        # The fake keeps the native num_envs=1 vectorized shape and unbounded values; it is not a limit.
        # the leading 1 is the fake's batch view (placeholder num_envs=1; ACTION_DIM is the upstream action_space)
        self.action_space = Box(-math.inf, math.inf, (1, ACTION_DIM))
        self.observation_space = Dict({
            "policy": Dict({
                "joint_pos": Box(-math.inf, math.inf, (1, ACTION_DIM)),
                "joint_vel": Box(-math.inf, math.inf, (1, ACTION_DIM)),
                "joint_pos_rel": Box(-math.inf, math.inf, (1, ACTION_DIM)),
                "joint_vel_rel": Box(-math.inf, math.inf, (1, ACTION_DIM)),
                "actions": Box(-math.inf, math.inf, (1, ACTION_DIM)),
                "ee_frame_state": Box(-math.inf, math.inf, (1, 7)),
                "joint_pos_target": Box(-math.inf, math.inf, (1, ACTION_DIM)),
                "front": Box(0.0, 255.0, IMAGE_SHAPE),   # placeholder RGB bound
                "wrist": Box(0.0, 255.0, IMAGE_SHAPE),   # placeholder RGB bound
            }),
            "subtask_terms": Dict({name: Box(0.0, 1.0, (1, 1)) for name in SUBTASK_TERMS}),  # placeholder
        })
        self._rng = random.Random()
        self._joint_pos = [0.0] * ACTION_DIM   # placeholder
        self._action = [0.0] * ACTION_DIM      # placeholder
        self._steps = 0
        self._started = False

    def reset(self, seed=None, options=None):
        """The native ``reset(seed=None, options=None)``: a fresh episode, seeded when given."""
        del options
        if seed is not None:
            self._rng = random.Random(int(seed))
        self._reset_episode()
        return self._observation(), {}

    def _reset_episode(self):
        # placeholder: the upstream resets the scene to defaults and randomizes objects/cameras; the fake
        # draws a small joint offset so a seed still selects an episode.
        self._joint_pos = [self._rng.uniform(-START_JITTER, START_JITTER) for _ in range(ACTION_DIM)]
        # Resetting the native scene does not assign SingleArmTaskDirectEnv.actions, so retain the last action.
        self._steps = 0
        self._started = True

    def step(self, action):
        """The native ``step(action)`` with a five-tuple result, without physics."""
        if not self._started:
            raise AssertionError("Call reset before using step method.")
        values = _flatten(action)
        if len(values) != ACTION_DIM:
            raise AssertionError(f"{len(values)} action values; expected {ACTION_DIM}")
        # single_arm_env.py:129-134: the native writes action * action_scale as the joint position target.
        self._action = [value * ACTION_SCALE for value in values]
        self._joint_pos = list(self._action)
        self._steps += 1
        # single_arm_env.py:162-165: time_out at episode_length_buf >= max_episode_length - 1.
        truncated = self._steps >= MAX_EPISODE_STEPS
        if truncated:
            # enhance/envs/direct_rl_env.py:82-107 resets ended environments before reading observations.
            self._reset_episode()
        # 0.0 is the upstream _get_rewards value; the fake does not model task success (see fidelity gaps).
        return self._observation(), 0.0, False, truncated, {}

    def close(self):
        """Release the fake state; the native close tears down the simulator."""
        self._started = False

    def _observation(self):
        """The observation groups the native ``_get_observations`` returns, with placeholder arrays."""
        def joint(value):
            return [list(value)]

        policy = {
            "joint_pos": joint(self._joint_pos),                       # placeholder
            "joint_vel": joint([0.0] * ACTION_DIM),                       # placeholder
            "joint_pos_rel": joint(self._joint_pos),                   # placeholder
            "joint_vel_rel": joint([0.0] * ACTION_DIM),                   # placeholder
            "actions": joint(self._action),
            "ee_frame_state": [[0.0] * 7],                                # placeholder
            "joint_pos_target": joint(self._joint_pos),                # placeholder
            "front": _fill(0.0, IMAGE_SHAPE),                             # placeholder
            "wrist": _fill(0.0, IMAGE_SHAPE),                             # placeholder
        }
        subtasks = {name: [[0.0]] for name in SUBTASK_TERMS}              # placeholder
        return {"policy": policy, "subtask_terms": subtasks}
