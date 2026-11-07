"""Fake backend of the pointfoot flat locomotion driver: a pure Python stand-in for the Isaac Lab task.

Why a fake: the registered task ``Isaac-PF-Blind-Flat-v0`` uses the external entry point
``omni.isaac.lab.envs:ManagerBasedRLEnv`` (exts/bipedal_locomotion/bipedal_locomotion/tasks/locomotion/robots/
__init__.py:64-71) and needs Isaac Sim 4.2.0 and Isaac Lab 1.4.0 with a GPU (README.md:7-8).  Package code never
imports or runs the clone, and the acceptance gate has no Isaac Sim or Isaac Lab, so this module supplies the
Gymnasium surface the bridge uses: ``action_space``, ``observation_space``, ``reset(seed, options)``, ``step(action)``
and ``close``.  The two space classes duck-type ``gymnasium.spaces.Box`` (the bridge reads ``low``, ``high`` and
``shape``).

What the constants are:

* the six joint targets, the action scale and the default offsets come from the clone's ``ActionsCfg`` and
  ``PFBaseEnvCfg`` (base_env_cfg.py:112-117 and pointfoot_env_cfg.py:31-39);
* the eight joints are the six actuated leg joints plus the two foot joints named by ``POINTFOOT_CFG``
  (pointfoot_cfg.py:29-42);
* the simulation time step is 4 x 0.005 s, an episode is 20.0 s (base_env_cfg.py:435-439) and the configured seed
  is 42 (base_env_cfg.py:440);
* the policy observation terms, their order and ``history_length = 5`` come from base_env_cfg.py:128-154; the gait
  term shapes come from the docstrings of ``get_gait_phase`` and ``get_gait_command`` (mdp/observations.py:117-153).

What this is not: the upstream environment.  The model is kinematic and every value that is not read from the
clone is test data, marked ``# placeholder``.  The 185-value policy observation is a stand-in: its layout follows
the clone's term list (base angular velocity 3, projected gravity 3, joint positions 8, joint velocities 8, last
action 6, velocity command 4, gait phase 2, gait command 3, repeated history_length 5 times), but observation
corruption, command resampling and the real Isaac Lab space were not observed.  The fidelity ``gaps`` of driver.py
list all of this.  Nothing here talks to a device.
"""

import math
import random

# exts/bipedal_locomotion/bipedal_locomotion/tasks/locomotion/cfg/PF/base_env_cfg.py:435-439
DECIMATION = 4
SIM_DT_S = 0.005
EPISODE_LENGTH_S = 20.0
TIMESTEP_S = DECIMATION * SIM_DT_S              # 0.02 s of simulated time per environment step
MAX_STEPS = int(EPISODE_LENGTH_S / TIMESTEP_S)  # 1000 environment steps, the time_out term (base_env_cfg.py:398)
# base_env_cfg.py:440
DEFAULT_SEED = 42
# base_env_cfg.py:114-116
ACTION_SCALE = 0.25
N_ACTIONS = 6
# pointfoot_env_cfg.py:32-39: the six actuated joint positions set by PFBaseEnvCfg
DEFAULT_JOINT_POS = [0.0, 0.0, 0.0918, 0.0918, -0.057, -0.057]
# pointfoot_cfg.py:38-39: the two foot joints named with an initial position of 0.0
FOOT_JOINT_POS = [0.0, 0.0]
N_JOINTS = N_ACTIONS + len(FOOT_JOINT_POS)      # eight named joints (pointfoot_cfg.py:31-39)
# base_env_cfg.py:153: history_length = 5; the eight terms of the policy group are at base_env_cfg.py:128-145
HISTORY_LENGTH = 5
N_OBSERVATIONS = (3 + 3 + N_JOINTS + N_JOINTS + N_ACTIONS + 4 + 2 + 3) * HISTORY_LENGTH
# base_env_cfg.py:103-104: the velocity command ranges
LIN_VEL_X = (-1.0, 1.0)
LIN_VEL_Y = (-0.5, 0.5)
ANG_VEL_Z = (-1.0, 1.0)
# base_env_cfg.py:89-91: the gait command ranges
GAIT_FREQUENCY = (1.5, 2.5)
GAIT_OFFSET = 0.5
GAIT_DURATION = 0.5


class Box:
    """Duck-typed one-dimensional ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = [float(value) for value in low]
        self.high = [float(value) for value in high]
        self.shape = (len(self.low),)
        self.dtype = "float32"

    def contains(self, value):
        if not isinstance(value, (list, tuple)) or len(value) != self.shape[0]:
            return False
        for item in value:
            if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(float(item)):
                return False
        return True


class FakePointfootEnv:
    """A deterministic kinematic stand-in: ``reset(seed, options)`` and ``step(action)`` as Gymnasium uses them."""

    def __init__(self, **options):
        del options                              # the bridge passes no backend options in the fake view
        # The clone configures no action clip (base_env_cfg.py:112-117), so the real bounds come from the external
        # ManagerBasedRLEnv / JointPositionAction implementation and are not claimed here.
        self.action_space = Box([-math.inf] * N_ACTIONS, [math.inf] * N_ACTIONS)
        # placeholder: the observation bounds were not observed from the upstream environment
        self.observation_space = Box([-math.inf] * N_OBSERVATIONS, [math.inf] * N_OBSERVATIONS)
        self._rng = random.Random(DEFAULT_SEED)
        self._episode = 0
        self._steps = 0
        self._joint_pos = list(DEFAULT_JOINT_POS) + list(FOOT_JOINT_POS)
        self._joint_vel = [0.0] * N_JOINTS      # placeholder: the state before the first reset
        self._last_action = [0.0] * N_ACTIONS   # placeholder: no action has been applied yet
        self._command = [0.0, 0.0, 0.0, 0.0]     # placeholder: the velocity command of the current episode
        self._gait = [2.0, GAIT_OFFSET, GAIT_DURATION]  # placeholder: the gait command of the current episode
        self._phase = 0.0                        # placeholder: gait phase at reset

    def reset(self, seed=None, options=None):
        del options                              # this environment declares no reset options
        if seed is not None:
            self._rng = random.Random(int(seed))
        # A uniform draw from the clone's ranges is this fake's stand-in for UniformVelocityCommand and
        # UniformGaitCommand; the heading component is a placeholder because the command term computes it.
        self._command = [self._rng.uniform(*LIN_VEL_X), self._rng.uniform(*LIN_VEL_Y),
                         self._rng.uniform(*ANG_VEL_Z), 0.0]  # placeholder: heading component
        self._gait = [self._rng.uniform(*GAIT_FREQUENCY), GAIT_OFFSET, GAIT_DURATION]
        self._joint_pos = list(DEFAULT_JOINT_POS) + list(FOOT_JOINT_POS)
        self._joint_vel = [0.0] * N_JOINTS      # placeholder
        self._last_action = [0.0] * N_ACTIONS   # placeholder
        self._phase = 0.0                        # placeholder
        self._steps = 0
        self._episode += 1
        return self._observation(), {"episode": self._episode}  # placeholder info value

    def step(self, action):
        if not self.action_space.contains(action):
            raise AssertionError(f"{action!r} is not an action of shape {self.action_space.shape}")
        values = [float(item) for item in action]
        # base_env_cfg.py:112-117: target = default joint position + scale * action (use_default_offset=True).
        self._joint_pos = [default + ACTION_SCALE * value
                           for default, value in zip(DEFAULT_JOINT_POS, values)] + list(FOOT_JOINT_POS)
        self._joint_vel = [0.0] * N_JOINTS      # placeholder: no velocity model
        self._last_action = values
        self._phase = (self._phase + self._gait[0] * TIMESTEP_S) % 1.0
        self._steps += 1
        reward = 0.0                             # placeholder: the reward terms are not modelled
        terminated = False                       # placeholder: the base-contact termination is not modelled
        truncated = self._steps >= MAX_STEPS     # base_env_cfg.py:398 and :436: the 20 s time_out
        return self._observation(), reward, terminated, truncated, {}

    def close(self):
        self._steps = 0                          # placeholder: nothing is held open

    def _observation(self):
        phase = [math.sin(2.0 * math.pi * self._phase), math.cos(2.0 * math.pi * self._phase)]
        terms = [
            [0.0, 0.0, 0.0],                     # placeholder: base_ang_vel (base_env_cfg.py:130)
            [0.0, 0.0, -1.0],                    # placeholder: proj_gravity at rest (base_env_cfg.py:131)
            self._joint_pos,                     # base_env_cfg.py:134
            self._joint_vel,                     # base_env_cfg.py:135
            self._last_action,                   # base_env_cfg.py:138
            self._command,                       # base_env_cfg.py:141
            phase,                               # base_env_cfg.py:144, observations.py:117-140
            self._gait,                          # base_env_cfg.py:145, observations.py:143-153
        ]
        flat = [value for term in terms for value in term]
        return flat * HISTORY_LENGTH             # base_env_cfg.py:153-154
