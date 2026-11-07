"""Fake backend of the HimLoco Lab Go2 velocity environment.

The upstream environment is an Isaac Lab ``ManagerBasedRLEnv``: importing it needs Isaac Sim, Isaac Lab, torch and a
GPU, and package code never imports or runs the clone.  This module is therefore a pure Python contract stand-in for
``himloco_lab.envs:HimlocoManagerBasedRLEnv``.  It provides the members the Gymnasium bridge reads (``action_space``,
``observation_space``, ``reset``, ``step``, ``close``) and the observation layout the upstream configuration declares.

What is real here (with the clone line that states it):

* 12 joint actions, one per Go2 joint (``source/.../assets/unitree.py:133-138``);
* the action scale 0.25 and clip -100..100 of ``JointPositionActionCfg`` (``velocity_env_cfg.py:247-249``);
* the 3-component SE(2) velocity command (``commands/commands.py:22-25``);
* the six policy observation terms, clipped to -100..100 (``velocity_env_cfg.py:261-271``);
* the 4 x 0.005 s = 0.02 s environment step and the 20 s episode (``velocity_env_cfg.py:488-492``).

Everything else is a placeholder: the fake does not integrate rigid-body dynamics, contacts, actuators or sensors.  It
keeps a tick counter, maps the action through the configured scale to the relative joint-position block and reports a
zero reward.  Those values are test data, not facts, and are marked ``# placeholder`` below.  The upstream ``step``
returns six values (``him_manager_based_rl_env.py:120``); the fake returns the five-value Gymnasium form the bridge
accepts.  The gaps of this shortcut are listed in the driver's ``fidelity`` contract.
"""

import math
import random

# Source references at the pinned commit c3fbd0173f2a53a86e472c099f8e2e9744cf7639.
ASSET = "source/himloco_lab/himloco_lab/assets/unitree.py"
CFG = "source/himloco_lab/himloco_lab/tasks/locomotion/robots/go2/velocity_env_cfg.py"
COMMANDS = "source/himloco_lab/himloco_lab/tasks/locomotion/mdp/commands/commands.py"

# asset/unitree.py:133-138 lists the 12 joint SDK names: hip, thigh and calf for each of the four legs.
NUM_JOINTS = 12
# commands/commands.py:22-25: the command is linear velocity in x and y plus angular velocity around z.
NUM_COMMANDS = 3
# velocity_env_cfg.py:261-271: three commands + three base angular velocities + three projected gravity values
# + twelve relative joint positions + twelve relative joint velocities + twelve last actions.
NUM_POLICY_OBS = NUM_COMMANDS + 3 + 3 + NUM_JOINTS + NUM_JOINTS + NUM_JOINTS
# velocity_env_cfg.py:262-271: every policy term has clip=(-100, 100).
OBS_CLIP = 100.0
# velocity_env_cfg.py:247-249: scale=0.25 and clip={".*": (-100.0, 100.0)}.
ACTION_SCALE = 0.25
ACTION_CLIP = 100.0
# velocity_env_cfg.py:488-492: decimation=4, episode_length_s=20.0, sim.dt=0.005.
DECIMATION = 4
SIM_DT_S = 0.005
EPISODE_LENGTH_S = 20.0
STEP_DT_S = DECIMATION * SIM_DT_S
MAX_EPISODE_STEPS = int(EPISODE_LENGTH_S / STEP_DT_S)
# velocity_env_cfg.py:232-233: lin_vel_x=(-1, 1), lin_vel_y=(-1.0, 1.0), ang_vel_z=(-2.0, 2.0).
COMMAND_RANGES = ((-1.0, 1.0), (-1.0, 1.0), (-2.0, 2.0))


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


class FakeHimlocoEnv:
    """A deterministic contract stand-in for ``HimlocoManagerBasedRLEnv``; no physics is simulated."""

    def __init__(self, cfg=None, render_mode=None, **kwargs):
        # The upstream constructor is ``__init__(cfg, render_mode=None, **kwargs)``
        # (him_manager_based_rl_env.py:9); the bridge builds the fake without arguments.
        self.cfg = cfg
        self.render_mode = render_mode
        self.action_space = Box([-ACTION_CLIP] * NUM_JOINTS, [ACTION_CLIP] * NUM_JOINTS)
        self.observation_space = Dict({
            "policy": Box([-OBS_CLIP] * NUM_POLICY_OBS, [OBS_CLIP] * NUM_POLICY_OBS),
        })
        self._rng = random.Random()
        self._seed = None
        self._episode = 0
        self._tick = 0
        self._truncated = False
        self._closed = False
        # placeholder: all state values are test data, not measurements of a Go2.
        self._command = [0.0] * NUM_COMMANDS
        self._joint_pos_rel = [0.0] * NUM_JOINTS
        self._last_action = [0.0] * NUM_JOINTS

    def reset(self, seed=None, options=None):
        """Reset the fake to a seeded, zeroed episode and return the policy observation.

        ``options`` is accepted because the bridge may pass it; the upstream Isaac Lab reset has no documented option
        keys in the clone, so the fake ignores it.
        """
        if seed is not None:
            self._seed = int(seed)
            self._rng = random.Random(self._seed)
        elif self._seed is None:
            # placeholder: the first unseeded reset uses seed 0, as the bridge does for the first episode.
            self._seed = 0
            self._rng = random.Random(0)
        # placeholder: draw a command from the configured ranges instead of running the command manager, which also
        # applies heading control, the high-velocity split and the minimum-command filter (commands.py:54-83).
        self._command = [self._rng.uniform(low, high) for low, high in COMMAND_RANGES]
        self._joint_pos_rel = [0.0] * NUM_JOINTS
        self._last_action = [0.0] * NUM_JOINTS
        self._episode += 1
        self._tick = 0
        self._truncated = False
        return self._observation(), {}

    def step(self, action):
        """Apply one action for one 0.02 s environment step; returns the Gymnasium five-tuple."""
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        values = self._action_values(action)
        self._last_action = values
        # placeholder dynamics: the processed joint target of JointPositionAction is default + scale * action
        # (velocity_env_cfg.py:247-249), so the relative joint-position observation is scale * action.
        self._joint_pos_rel = [ACTION_SCALE * value for value in values]
        self._tick += 1
        self._truncated = self._tick >= MAX_EPISODE_STEPS
        # placeholder: the fake reports no reward; the reward terms of the upstream env are not modelled.
        reward = 0.0
        return self._observation(), reward, False, self._truncated, {}

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
            out.append(number)
        return out

    def _observation(self):
        # placeholder: the base angular velocity, projected gravity and joint velocity blocks are static; the gravity
        # block is the upright value [0, 0, -1], not an attitude computed from the action.
        return {
            "policy": [
                *self._command,
                0.0, 0.0, 0.0,
                0.0, 0.0, -1.0,
                *self._joint_pos_rel,
                *([0.0] * NUM_JOINTS),
                *self._last_action,
            ]
        }
