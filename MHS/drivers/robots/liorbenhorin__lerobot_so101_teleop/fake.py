"""Fake backend of the lerobot_so101_teleop driver: a pure Python stand-in for the Isaac Lab Rock-A-Stack task.

Why a fake: the acceptance gate runs without Isaac Sim, Isaac Lab, ``torch``, ``gymnasium`` or an NVIDIA GPU.  The
clone's README installs Isaac Sim 5.1.0 and Isaac Lab v2.3.0 (README.md:38-47), and the registered environment's
entry point is ``isaaclab.envs:ManagerBasedRLEnv`` (tasks/rock_a_stack/__init__.py:9-16), a class that lives outside the
clone.  Package code never imports the clone, so this module models the contract the clone configures: the six
joint-position action targets (tasks/base/base_env_cfg.py:141-146), the ``policy`` observation group with the robot's
joint positions (:154-161), the ``visual`` group with the two RGB cameras (:163-186), the 480 x 640 camera size
(:75-80 and :105-110) and the 1/60 s policy step of decimation 2 with a 1/120 s simulation timestep (:294-305).

What this is not: the upstream task.  There is no rigid-body dynamics, contact, actuator, sensor, renderer, domain
randomisation or physics material.  A step stores the commanded joint positions and returns them; the reward is a
constant placeholder, only the derived 5 s time-out truncates an episode, and the camera frames are constant
placeholders.  Every number below that is not a configuration value read from the clone is marked ``# placeholder``
(test data, never a fact or a limit).  The fake was never compared with an Isaac Sim run.

The public members are the Gymnasium environment interface the bridge calls (``reset``, ``step`` and ``close``; gate
G7), and the two space classes duck-type ``gymnasium.spaces.Box`` and ``gymnasium.spaces.Dict`` (the bridge reads
``low``, ``high``, ``shape`` and ``spaces``).

Nothing here talks to a device.
"""

import random

# tasks/base/base_env_cfg.py:297 and :305: decimation 2 with sim.dt 1/120 s, so one policy step is 1/60 s.
DECIMATION = 2
SIM_DT_S = 1.0 / 120.0
TIMESTEP_S = DECIMATION * SIM_DT_S
# tasks/base/base_env_cfg.py:298: episode_length_s = 5.  The step count is derived from the two values above
# (5 s / (1/60 s) = 300); the upstream truncation logic itself lives in Isaac Lab, outside the clone.
EPISODE_LENGTH_S = 5.0
MAX_EPISODE_STEPS = int(round(EPISODE_LENGTH_S / TIMESTEP_S))
# tasks/base/base_env_cfg.py:141-146 names six controlled joints.
N_JOINTS = 6
# tasks/base/base_env_cfg.py:78-80 and :108-110: the two cameras are 480 x 640 RGB images (921600 values each).  The
# fake returns smaller flat arrays so a receipt stays small; the real size is disclosed in the fidelity gaps and in
# RESULT.json.  This count is test data.
FAKE_CAMERA_VALUES = 18  # placeholder

# No finite action bound is claimed: the clone configures the joint-position term and its scale but no numeric bound,
# and the fake's action Box is unbounded, so the bridge publishes no action limit.
INF = float("inf")


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high, shape=None):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape) if shape is not None else (len(self.low),)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the bridge reads ``spaces``."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


class FakeSo101RockAStackEnv:
    """A single-environment stand-in for the registered ``Lerobot-So101-Teleop-Rock-A-Stack-Simple`` task.

    ``reset(seed, options)`` and ``step(action)`` follow the Gymnasium interface the bridge calls; ``close`` releases
    nothing.  The upstream ``ManagerBasedRLEnv`` also takes ``env_ids`` and returns batched tensors, while this stand-in
    serves one environment with Python lists (fidelity gaps).
    """

    def __init__(self, **_options):
        # tasks/base/base_env_cfg.py:141-146: six joint-position targets; no numeric bound is stated in the clone.
        self.action_space = Box([-INF] * N_JOINTS, [INF] * N_JOINTS, (N_JOINTS,))
        # tasks/base/base_env_cfg.py:188-190: the observation groups are policy and visual; the visual group keeps
        # its two terms separate (:184-186, concatenate_terms = False).
        self.observation_space = Dict({
            "policy": Box([-INF] * N_JOINTS, [INF] * N_JOINTS, (N_JOINTS,)),
            "visual": Dict({
                "camera_ego": Box([-INF] * FAKE_CAMERA_VALUES, [INF] * FAKE_CAMERA_VALUES, (FAKE_CAMERA_VALUES,)),
                "camera_external": Box([-INF] * FAKE_CAMERA_VALUES, [INF] * FAKE_CAMERA_VALUES,
                                       (FAKE_CAMERA_VALUES,)),
            }),
        })
        self._rng = random.Random()
        # placeholder: the fake starts every joint at zero; the upstream reset writes the asset's default joint
        # positions (tasks/base/base_env_cfg.py:197-215 and assets/so101.py:23-31).
        self._joint_pos = [0.0] * N_JOINTS  # placeholder
        self._tick = 0
        self._closed = False

    def reset(self, *, seed=None, options=None):
        """Start a new episode; ``seed`` fixes the stand-in's random stream, ``options`` are accepted and unused."""
        if seed is not None:
            self._rng = random.Random(int(seed))
        self._joint_pos = [0.0] * N_JOINTS  # placeholder
        self._tick = 0
        return self._observation(), {}

    def step(self, action):
        """Hold one 1/60 s joint-position step and return the Gymnasium five-tuple."""
        try:
            values = [float(value) for value in action]
        except (TypeError, ValueError) as exc:
            raise ValueError("the action must be a sequence of six joint positions") from exc
        if len(values) != N_JOINTS:
            raise ValueError(f"the action has {N_JOINTS} values, got {len(values)}")
        # placeholder: zero-order hold, not Isaac Lab physics.  The clone configures a joint-position target with
        # scale 1 and use_default_offset False (tasks/base/base_env_cfg.py:141-146); the stand-in stores the command.
        self._joint_pos = values
        self._tick += 1
        # tasks/base/base_env_cfg.py:298 with :297 and :305: 5 s at a 1/60 s policy step.
        truncated = self._tick >= MAX_EPISODE_STEPS
        return self._observation(), 0.0, False, truncated, {"tick": self._tick}

    def close(self):
        """Close the stand-in; it holds no external resource."""
        self._closed = True

    def _observation(self):
        """The observation groups of tasks/base/base_env_cfg.py:154-190 (the policy group is the joint positions)."""
        return {
            "policy": list(self._joint_pos),
            "visual": {
                "camera_ego": self._camera(),
                "camera_external": self._camera(),
            },
        }

    def _camera(self):
        """placeholder: a constant frame; the real cameras are 480 x 640 RGB and see the randomised scene."""
        return [0.0] * FAKE_CAMERA_VALUES
