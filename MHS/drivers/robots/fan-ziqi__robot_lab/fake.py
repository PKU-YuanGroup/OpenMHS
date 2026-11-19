"""Fake backend of the robot_lab G1 AMP dance environment.

The upstream entry ``robot_lab.tasks.direct.g1_amp.g1_amp_env:G1AmpEnv`` is an Isaac Lab ``DirectRLEnv``: opening it
needs Isaac Sim, Isaac Lab, torch, the motion asset and a GPU, and package code never imports or runs the clone.  This
module is therefore a pure Python contract stand-in.  It provides the members the Gymnasium bridge reads
(``action_space``, ``observation_space``, ``reset``, ``step``, ``close``) and the observation layout the upstream code
builds.

What is real here (with the clone line that states it):

* the 29-value action (``g1_amp_env_cfg.py:54``) written as a joint-position target through an offset and a scale
  (``g1_amp_env.py:35-38`` and ``:102-104``);
* the 105-value policy observation built by ``compute_obs`` (``g1_amp_env.py:369-382``), returned as
  ``{"policy": obs}`` (``g1_amp_env.py:134``);
* the 10 s nominal episode at ``dt = 1/60 s`` and ``decimation = 1`` (``g1_amp_env_cfg.py:48-50``),
  with truncation at counter ``max_episode_length - 1`` (599 in this fake; ``g1_amp_env.py:242``);
* the early-termination height 0.5 (``g1_amp_env_cfg.py:59-60``; ``g1_amp_env.py:243-247``);
* the action-L2 reward term ``rew_action_l2 * sum(action**2)`` with ``rew_action_l2 = -0.1``
  (``g1_amp_env.py:400``; ``g1_amp_env_cfg.py:33``).

Everything else is a placeholder: the fake does not integrate the G1 rigid-body dynamics, contacts, actuators or
sensors, does not load ``g1_dance1_subject2_30.npz``, does not reproduce the four imitation reward terms and does not
provide the AMP observation history.  Those values are test data, not facts, and are marked ``# placeholder`` below.
The fake was never compared with the upstream environment; the gaps are listed in the driver's ``fidelity`` contract.
"""

import math
import random

# g1_amp_env_cfg.py:54: action_space = 29.
NUM_JOINTS = 29
# g1_amp_env_cfg.py:53: observation_space = 71 + 3 * (8 + 5) - 6 + 1 = 105.
NUM_POLICY_OBS = 105
# g1_amp_env.py:45-59 lists 13 key bodies used by compute_obs.
NUM_KEY_BODIES = 13
# g1_amp_env_cfg.py:48-50: episode_length_s = 10.0, decimation = 1, dt = 1 / 60.
SIM_DT_S = 1.0 / 60.0
EPISODE_LENGTH_S = 10.0
MAX_EPISODE_STEPS = int(EPISODE_LENGTH_S / SIM_DT_S)
# g1_amp_env_cfg.py:59-60: early_termination = True, termination_height = 0.5.
TERMINATION_HEIGHT = 0.5
# g1_amp_env_cfg.py:33 rew_action_l2 = -0.1; g1_amp_env.py:400 applies it to sum(action**2).
REW_ACTION_L2 = -0.1

# placeholder: the clone states only action_space = 29 (g1_amp_env_cfg.py:54); the exact Box bounds are provided by
# Isaac Lab outside the clone, so these are test data, not a sourced bound.
ACTION_LOW, ACTION_HIGH = -1.0, 1.0
# placeholder: fake start height, joint tracking and fall model; upstream reset loads the motion file and PhysX
# computes the pose.
INITIAL_ROOT_HEIGHT = 0.75
INITIAL_POSE_JITTER = 0.01
LEAN_RATE = 0.004
JOINT_TARGET_SCALE = 0.5
JOINT_TRACKING_RATE = 4.0


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high`` and ``shape``."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the bridge reads ``spaces``."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)
        self.shape = None
        self.dtype = None


class FakeG1AmpEnv:
    """A deterministic contract stand-in for ``G1AmpEnv``; no physics is simulated."""

    def __init__(self, cfg=None, render_mode=None, **kwargs):
        # The upstream constructor is ``__init__(cfg, render_mode=None, **kwargs)`` (g1_amp_env.py:31); the bridge
        # builds the fake without arguments.
        self.cfg = cfg
        self.render_mode = render_mode
        self.action_space = Box([ACTION_LOW] * NUM_JOINTS, [ACTION_HIGH] * NUM_JOINTS)
        self.observation_space = Dict({
            "policy": Box([-math.inf] * NUM_POLICY_OBS, [math.inf] * NUM_POLICY_OBS),
        })
        self._rng = random.Random()
        self._seed = None
        self._episode = 0
        self._tick = 0
        self._terminated = False
        self._truncated = False
        self._closed = False
        # placeholder: all state values are test data, not measurements of a G1.
        self._joint_pos = [0.0] * NUM_JOINTS
        self._joint_vel = [0.0] * NUM_JOINTS
        self._root_height = INITIAL_ROOT_HEIGHT
        self._key_offsets = [0.0] * (NUM_KEY_BODIES * 3)
        self._last_action = [0.0] * NUM_JOINTS

    def reset(self, seed=None, options=None):
        """Reset the fake to a seeded placeholder start state and return ``{"policy": obs}`` and ``{}``.

        ``options`` is accepted because the bridge may pass it; the upstream DirectRLEnv reset has no documented
        option keys in the clone, so the fake ignores it.
        """
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        if seed is not None:
            self._seed = int(seed)
            self._rng = random.Random(self._seed)
        elif self._seed is None:
            # placeholder: the first unseeded reset uses seed 0, as the bridge does for the first episode.
            self._seed = 0
            self._rng = random.Random(0)
        # placeholder: the upstream random-start reset samples the motion at time zero (g1_amp_env.py:281) and writes
        # the motion pose (g1_amp_env.py:263-265); the fake uses a neutral joint pose and draws only the root height
        # and key-body offsets from the seed.
        self._joint_pos = [0.0] * NUM_JOINTS
        self._joint_vel = [0.0] * NUM_JOINTS
        self._root_height = INITIAL_ROOT_HEIGHT + self._rng.uniform(-INITIAL_POSE_JITTER, INITIAL_POSE_JITTER)
        self._key_offsets = [self._rng.uniform(-INITIAL_POSE_JITTER, INITIAL_POSE_JITTER)
                             for _ in range(NUM_KEY_BODIES * 3)]
        self._last_action = [0.0] * NUM_JOINTS
        self._tick = 0
        self._episode += 1
        self._terminated = False
        self._truncated = False
        return self._observation(), {}

    def step(self, action):
        """Apply one action for one 1/60 s environment step and return the Gymnasium five-tuple."""
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        if self._terminated or self._truncated:
            raise RuntimeError("the episode has ended; reset the environment")
        values = self._action_values(action)
        self._last_action = values
        for index in range(NUM_JOINTS):
            # placeholder: the joint target mapping and the first-order tracking are test data; upstream
            # _apply_action writes action_offset + action_scale * actions (g1_amp_env.py:102-104).
            target = JOINT_TARGET_SCALE * values[index]
            velocity = JOINT_TRACKING_RATE * (target - self._joint_pos[index])
            self._joint_vel[index] = velocity
            self._joint_pos[index] += velocity * SIM_DT_S
        lean = sum(abs(value) for value in values) / NUM_JOINTS
        self._root_height -= LEAN_RATE * lean  # placeholder fall model
        self._tick += 1
        self._terminated = self._root_height < TERMINATION_HEIGHT
        self._truncated = self._tick >= MAX_EPISODE_STEPS - 1  # g1_amp_env.py:242
        # g1_amp_env.py:400 with rew_action_l2 = -0.1 (g1_amp_env_cfg.py:33); the imitation terms are not modelled.
        reward = REW_ACTION_L2 * sum(value * value for value in values)
        return self._observation(), reward, self._terminated, self._truncated, {}

    def close(self):
        self._closed = True

    # -- helpers (private: gate G7 does not count them as the fake's public surface) -------------------------------
    def _action_values(self, action):
        values = action.tolist() if hasattr(action, "tolist") else action
        if isinstance(values, dict):
            values = values.get("values")
        if not isinstance(values, (list, tuple)) or len(values) != NUM_JOINTS:
            raise ValueError(f"the action must have {NUM_JOINTS} joint values, got {values!r}")
        out = []
        for value in values:
            number = float(value)
            if not math.isfinite(number):
                raise ValueError(f"the action contains a non-finite value: {value!r}")
            if number < ACTION_LOW or number > ACTION_HIGH:
                raise ValueError(f"the action value {number!r} is outside {ACTION_LOW}..{ACTION_HIGH}")
            out.append(number)
        return out

    def _observation(self):
        # g1_amp_env.py:369-382: joint positions, joint velocities, root z, the quaternion tangent and normal, the
        # key-body positions relative to the root, and progress.  The fake keeps the same width and order.
        progress = self._tick / (MAX_EPISODE_STEPS - 1)  # g1_amp_env.py:110 uses the same denominator
        # placeholder: the root quaternion is the identity, so its tangent and normal are fixed.
        tangent_and_normal = [1.0, 0.0, 0.0, 0.0, 0.0, 1.0]
        return {
            "policy": [
                *self._joint_pos,
                *self._joint_vel,
                self._root_height,
                *tangent_and_normal,
                *self._key_offsets,
                progress,
            ]
        }
