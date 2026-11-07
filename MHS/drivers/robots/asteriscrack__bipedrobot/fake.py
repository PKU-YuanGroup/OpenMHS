"""Fake backend of the BipedRobot driver: a pure Python stand-in for the MuJoCoV2-v0 environment.

The gate does not install the clone's stack (mujoco, torch, numpy and gymnasium; requirements.txt:1-15) and package
code never imports the clone, so this module re-implements the Gymnasium surface of
``envs.mujoco.biped_env_v2:BipedEnvV2``.  The public members the bridge and the driver use are ``reset``, ``step``,
``close``, ``action_space`` and ``observation_space`` (gate G7 checks them against that class).  The action and
observation shapes follow the class's spaces (``biped_env_v2.py:281-285``), the control period follows STEP_DT
(``biped_env_v2.py:77-79``), the termination rule follows ``_is_terminated`` (``biped_env_v2.py:654-661``) and the
1000-step truncation follows the MujocoV2-v0 registration (``envs/mujoco/__init__.py:9-13``).

What this is not: the MuJoCo model.  There is no rigid-body integration, actuator or servo model, contact, friction,
reward term or rendering.  The observation layout has the upstream lengths but placeholder values, and the start
state comes from Python's ``random.Random`` while upstream reseeds numpy's generator (``biped_env_v2.py:693-694``),
so one seed gives different trajectories on the two.  The fidelity ``gaps`` of driver.py say all of this.
"""

import math
import random

# envs/mujoco/biped_env_v2.py:77-79
PHYSICS_DT = 0.005
DECIMATION = 4
STEP_DT = PHYSICS_DT * DECIMATION
# envs/mujoco/biped_env_v2.py:251-252 and :281-285
ACTOR_DIM = 50
CRITIC_DIM = 60
NUM_JOINTS = 12
# envs/mujoco/__init__.py:9-13
MAX_EPISODE_STEPS = 1000
# envs/mujoco/biped_env_v2.py:654-661
TILT_LIMIT = 0.784
AIR_STEPS_LIMIT = int(1.0 / STEP_DT)

# Start state and dynamics of the stand-in, not measured properties of the robot.
BASE_HEIGHT = 0.75                      # placeholder
JOINT_START_RANGE = 0.1                 # placeholder
COMMAND_RANGES = ((-0.5, 1.0), (-0.3, 0.3), (-0.5, 0.5))   # placeholder
VELOCITY_DECAY = 0.9                    # placeholder
ACTION_GAIN = 0.5                       # placeholder
TILT_PER_UNIT_ACTION = 0.002            # placeholder
REWARD_ACTION_PENALTY = 0.01            # placeholder
AIRBORNE_ACTION_LEVEL = 0.9             # placeholder


class Box:
    """Duck-typed ``gymnasium.spaces.Box`` with a flat lower and upper bound per element."""

    def __init__(self, low, high, shape):
        count = 1
        for size in shape:
            count *= int(size)
        self.low = [float(low)] * count
        self.high = [float(high)] * count
        self.shape = tuple(int(size) for size in shape)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the bridge reads ``spaces``."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


class FakeBipedEnvV2:
    """The Gymnasium surface of ``BipedEnvV2`` without MuJoCo, numpy, torch or gymnasium."""

    def __init__(self, xml_path=None, render_mode=None, history_size=0, use_history=False,
                 critic_has_privileged_info=True, env_config=None, seed=None):
        if render_mode is not None:
            raise ValueError("the fake BipedEnvV2 cannot render; use render_mode=None")
        self.history_size = int(history_size)
        self.use_history = bool(use_history and history_size > 1)
        self.critic_has_privileged_info = bool(critic_has_privileged_info)
        self.action_space = Box(-1.0, 1.0, (NUM_JOINTS,))
        actor_dim = ACTOR_DIM * (self.history_size if self.use_history else 1)
        critic_dim = CRITIC_DIM if self.critic_has_privileged_info else ACTOR_DIM
        self.observation_space = Dict({
            "actor": Box(-math.inf, math.inf, (actor_dim,)),
            "critic": Box(-math.inf, math.inf, (critic_dim,)),
        })
        self._rng = random.Random(seed)
        self._closed = False
        self._joint_pos = [0.0] * NUM_JOINTS
        self._joint_vel = [0.0] * NUM_JOINTS
        self._prev_action = [0.0] * NUM_JOINTS
        self._commands = [0.0, 0.0, 0.0]
        self._gait_phase = [0.0, 0.0]
        self._base_height = BASE_HEIGHT
        self._tilt = 0.0
        self._both_air_steps = 0
        self._elapsed_steps = 0
        self._last_observation = None
        self.reset(seed=seed)

    def _actor_values(self):
        """The 50-value actor observation layout of biped_env_v2.py:3-5, with placeholder values."""
        values = [0.0, 0.0, 0.0]                  # lin_acc_b                 # placeholder
        values += [0.0, 0.0, 0.0]                 # ang_vel_b                 # placeholder
        values += [0.0, 0.0, -1.0]                # projected_gravity (upright) # placeholder
        values += list(self._commands)
        values += list(self._joint_pos)
        values += list(self._joint_vel)
        values += list(self._prev_action)
        values += list(self._gait_phase)
        return values

    def _observation(self):
        base_actor = self._actor_values()
        actor = base_actor * self.history_size if self.use_history else base_actor
        extras = [0.0, 0.0, 0.0, self._base_height] + [0.0] * 6   # placeholder: base_lin_vel_b(3), height(1), feet_forces(6)
        return {"actor": list(actor), "critic": list(base_actor + extras)}

    def reset(self, seed=None, options=None):
        if seed is not None:
            self._rng.seed(int(seed))
        self._joint_pos = [self._rng.uniform(-JOINT_START_RANGE, JOINT_START_RANGE)
                           for _ in range(NUM_JOINTS)]                       # placeholder
        self._joint_vel = [0.0] * NUM_JOINTS
        self._prev_action = [0.0] * NUM_JOINTS
        self._commands = [self._rng.uniform(low, high) for low, high in COMMAND_RANGES]   # placeholder
        self._gait_phase = [self._rng.uniform(0.0, 2.0 * math.pi) for _ in range(2)]     # placeholder
        self._base_height = BASE_HEIGHT
        self._tilt = 0.0
        self._both_air_steps = 0
        self._elapsed_steps = 0
        self._last_observation = self._observation()
        return self._last_observation, {}

    def step(self, action):
        values = [float(value) for value in action]
        if len(values) != NUM_JOINTS:
            raise ValueError(f"expected {NUM_JOINTS} action values, got {len(values)}")
        values = [max(-1.0, min(1.0, value)) for value in values]        # biped_env_v2.py:733
        for index in range(NUM_JOINTS):
            self._joint_vel[index] = (VELOCITY_DECAY * self._joint_vel[index]
                                      + ACTION_GAIN * values[index])       # placeholder
            self._joint_pos[index] += self._joint_vel[index] * STEP_DT
        self._tilt += TILT_PER_UNIT_ACTION * sum(abs(value) for value in values)          # placeholder
        if all(abs(value) > AIRBORNE_ACTION_LEVEL for value in values):                    # placeholder
            self._both_air_steps += 1
        else:
            self._both_air_steps = 0
        self._prev_action = values
        self._elapsed_steps += 1
        reward = 1.0 - REWARD_ACTION_PENALTY * sum(abs(value) for value in values)         # placeholder
        terminated = self._tilt > TILT_LIMIT or self._both_air_steps > AIR_STEPS_LIMIT
        truncated = self._elapsed_steps >= MAX_EPISODE_STEPS
        self._last_observation = self._observation()
        return self._last_observation, reward, terminated, truncated, {}

    def close(self):
        self._closed = True
