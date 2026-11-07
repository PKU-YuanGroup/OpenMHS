"""Fake backend of the gym_multirotor driver: a pure Python stand-in for ``QuadrotorPlusHoverEnv``.

Why a fake: the acceptance gate runs without gym, mujoco_py or the clone (the upstream environment imports
``gym.envs.mujoco`` and ``mujoco_py`` and requires gym==0.21.0 and mujoco_py==2.1.2.14, requirements.txt:4-5), and
package code never imports the clone.  This module re-implements the 18-value observation, the four-motor action
mapping, the reward terms and the episode-end predicate of
``gym_multirotor.envs.mujoco.quadrotor_plus_hover:QuadrotorPlusHoverEnv`` (the class the driver names as ``native``)
with the constants of the clone.  The public members are ``reset`` and ``step`` (gate G7; ``close`` is omitted
because the pure Python object owns no resource), and ``Box`` duck-types ``gym.spaces.Box`` (the bridge reads
``low``, ``high``, ``shape``).

What this is not: the upstream environment.  Differences, all listed in the fidelity ``gaps`` of the driver:

* the dynamics are a damped toy model, not MuJoCo: no rigid-body integration, contacts, thrust vectoring or rotor
  dynamics, and the rotation matrix stays at the identity;
* the action space is the model's four-motor ctrlrange 0 to 1; the upstream space is built by gym's MuJoCo base
  class outside the clone and was not compared with the fake's;
* the initial state comes from Python's ``random.Random(seed)``; upstream draws it with numpy's generator, so a seed
  does not give the same trajectory on both;
* observations are Python floats; upstream returns a float32 numpy array;
* there is no rendering and no ``info`` payload beyond an empty object (upstream returns reward_info, desired_goal,
  mujoco_qpos and mujoco_qvel).

Nothing here talks to a device.
"""

import math
import random

# gym_multirotor/envs/mujoco/base_env.py:234 (desired_position)
DESIRED_POSITION = [0.0, 0.0, 3.0]
# gym_multirotor/envs/mujoco/base_env.py:238
GRAVITY_MAG = 9.81
# gym_multirotor/envs/mujoco/assets/quadrotor_plus.xml:8 (model timestep)
MODEL_TIMESTEP_S = 0.01
# gym_multirotor/__init__.py:11 (registered frame_skip)
FRAME_SKIP = 5
# gym_multirotor/envs/mujoco/base_env.py:99 (env_bounding_box)
ENV_BOUNDING_BOX = 1.2
# gym_multirotor/envs/mujoco/base_env.py:100-101 (init_max_vel, init_max_angular_vel)
INIT_MAX_VEL = 0.5
INIT_MAX_ANGULAR_VEL = 0.1 * math.pi
# gym_multirotor/envs/mujoco/base_env.py:92-93 (error_tolerance, max_time_steps)
ERROR_TOLERANCE = 0.05
MAX_TIME_STEPS = 1000
# gym_multirotor/envs/mujoco/base_env.py:103-111 (reward constants)
BONUS_TO_REACH_GOAL = 15.0
MAX_REWARD_FOR_VELOCITY_TOWARDS_GOAL = 2.0
POSITION_REWARD_CONSTANT = 5.0
ORIENTATION_REWARD_CONSTANT = 0.02
LINEAR_VELOCITY_REWARD_CONSTANT = 0.01
ANGULAR_VELOCITY_REWARD_CONSTANT = 0.001
ACTION_REWARD_CONSTANT = 0.0025
REWARD_FOR_STAYING_ALIVE = 5.0
REWARD_SCALING_COEFFICIENT = 1.0
# gym_multirotor/envs/mujoco/base_env.py:197-203 (policy_range, policy_range_safe)
POLICY_RANGE = (-1.0, 1.0)
# gym_multirotor/envs/mujoco/quadrotor_plus_hover.py:40-41 (motor_range 2.0)
MOTOR_RANGE = 2.0
# gym_multirotor/envs/mujoco/quadrotor_plus_hover.py:28 (hover_force factor)
HOVER_FORCE_FACTOR = 0.25
# gym_multirotor/envs/mujoco/base_env.py:254 and :264 (the norms of three equal components)
ENV_BOUNDING_BOX_NORM = ENV_BOUNDING_BOX * math.sqrt(3)
ERROR_TOLERANCE_NORM = ERROR_TOLERANCE * math.sqrt(3)

# placeholder: the toy model's gains and its hover command are test data, not device facts
HOVER_COMMAND = 0.5
POSITION_SPRING = 0.2
VELOCITY_DAMPING = 0.4
THRUST_GAIN = 1.0
ANGULAR_DAMPING = 0.98
# placeholder: the fake keeps an identity attitude instead of integrating the quaternion
IDENTITY_ROTATION = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]


class Box:
    """Duck-typed ``gym.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeQuadrotorPlusEnv:
    """QuadrotorPlusHoverEnv without gym, numpy or mujoco_py: ``reset`` and ``step`` return plain Python values."""

    def __init__(self, xml_name="quadrotor_plus.xml", frame_skip=FRAME_SKIP, env_bounding_box=ENV_BOUNDING_BOX,
                 randomize_reset=True, **options):
        del options
        self.xml_name = xml_name
        self.frame_skip = int(frame_skip)
        self.env_bounding_box = float(env_bounding_box)
        self.randomize_reset = bool(randomize_reset)
        # quadrotor_plus.xml:73-76: four motors ctrl-limited to 0..1
        self.action_space = Box([0.0, 0.0, 0.0, 0.0], [1.0, 1.0, 1.0, 1.0])
        # quadrotor_plus_hover.py:92: the observation has 18 values
        self.observation_space = Box([-math.inf] * 18, [math.inf] * 18)
        self._rng = random.Random()
        self._time = 0
        self._position = list(DESIRED_POSITION)
        self._velocity = [0.0, 0.0, 0.0]
        self._angular_velocity = [0.0, 0.0, 0.0]

    # quadrotor_plus_hover.py:214-225 (reset_model) and base_env.py:243 (MujocoEnv reset)
    def reset(self, seed=None, options=None):
        if options is not None and not isinstance(options, dict):
            raise ValueError("options must be a mapping")
        if seed is not None:
            if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
                raise ValueError("seed must be a non-negative integer")
            self._rng = random.Random(seed)
        self._time = 0
        if self.randomize_reset:
            # quadrotor_plus_hover.py:197-210: position offset within env_bounding_box - 0.2, velocity and
            # angular velocity within their initial maxima
            span = self.env_bounding_box - 0.2
            offset = [self._rng.uniform(-span, span) for _ in range(3)]
            self._position = [DESIRED_POSITION[index] + offset[index] for index in range(3)]
            self._velocity = [self._rng.uniform(-INIT_MAX_VEL, INIT_MAX_VEL) for _ in range(3)]
            self._angular_velocity = [self._rng.uniform(-INIT_MAX_ANGULAR_VEL, INIT_MAX_ANGULAR_VEL)
                                      for _ in range(3)]
        else:
            # quadrotor_plus_hover.py:183-186
            self._position = list(DESIRED_POSITION)
            self._velocity = [0.0, 0.0, 0.0]
            self._angular_velocity = [0.0, 0.0, 0.0]
        return self._observation()

    # quadrotor_plus_hover.py:44-85 (step)
    def step(self, action):
        try:
            values = [float(item) for item in action]
        except (TypeError, ValueError) as exc:
            raise ValueError(f"action must be a sequence of four numbers: {exc}") from exc
        if len(values) != 4:
            raise ValueError(f"action must have 4 elements, got {len(values)}")
        if not all(math.isfinite(item) for item in values):
            raise ValueError("action elements must be finite")
        # quadrotor_plus_hover.py:60: clip_action(action, policy_range[0], policy_range[1])
        values = [min(max(item, POLICY_RANGE[0]), POLICY_RANGE[1]) for item in values]
        self._time += 1
        thrust = sum(values) / len(values) - HOVER_COMMAND          # placeholder toy control
        error = [self._position[index] - DESIRED_POSITION[index] for index in range(3)]
        acceleration = [-POSITION_SPRING * error[index] - VELOCITY_DAMPING * self._velocity[index]
                        for index in range(3)]                       # placeholder toy spring and damping
        acceleration[2] += THRUST_GAIN * thrust                     # placeholder toy thrust
        dt = MODEL_TIMESTEP_S * self.frame_skip
        for index in range(3):
            self._velocity[index] += acceleration[index] * dt
            self._position[index] += self._velocity[index] * dt
        self._angular_velocity = [item * ANGULAR_DAMPING for item in self._angular_velocity]  # placeholder damping
        observation = self._observation()
        reward = self._reward(observation, values)
        done = self._done(observation)
        # the fake omits the upstream info payload (reward_info, desired_goal, mujoco_qpos, mujoco_qvel)
        return observation, reward, done, {}

    # quadrotor_plus_hover.py:87-116 (_get_obs)
    def _observation(self):
        error = [self._position[index] - DESIRED_POSITION[index] for index in range(3)]
        return error + list(IDENTITY_ROTATION) + list(self._velocity) + list(self._angular_velocity)

    # quadrotor_plus_hover.py:118-168 (get_reward)
    def _reward(self, observation, action):
        error = observation[0:3]
        velocity = observation[12:15]
        angular_velocity = observation[15:18]
        error_norm = self._norm(error)
        reward_position = error_norm * -POSITION_REWARD_CONSTANT
        reward_orientation = 0.0 * -ORIENTATION_REWARD_CONSTANT
        reward_linear_velocity = self._norm(velocity) * -LINEAR_VELOCITY_REWARD_CONSTANT
        reward_angular_velocity = self._norm(angular_velocity) * -ANGULAR_VELOCITY_REWARD_CONSTANT
        reward_action = self._norm(action) * -ACTION_REWARD_CONSTANT
        extra_bonus = BONUS_TO_REACH_GOAL if error_norm < ERROR_TOLERANCE_NORM else 0.0
        extra_penalty = 0.0 if self._within_env_bounds(error) else -BONUS_TO_REACH_GOAL
        velocity_towards_goal = 0.0
        if error_norm > ERROR_TOLERANCE_NORM:
            unit_error = [item / (error_norm + 1e-6) for item in error]
            velocity_norm = self._norm(velocity)
            unit_velocity = [item / (velocity_norm + 1e-6) for item in velocity]
            velocity_towards_goal = self._clip(sum(unit_error[index] * unit_velocity[index] for index in range(3)),
                                               -math.inf, MAX_REWARD_FOR_VELOCITY_TOWARDS_GOAL)
        rewards = (reward_position, reward_orientation, reward_linear_velocity, reward_angular_velocity,
                   reward_action, REWARD_FOR_STAYING_ALIVE, extra_bonus, extra_penalty, velocity_towards_goal)
        return sum(rewards) * REWARD_SCALING_COEFFICIENT

    # base_env.py:493-505 (is_done)
    def _done(self, observation):
        finite = all(math.isfinite(item) for item in observation)
        within_bounds = self._within_env_bounds(observation[0:3])
        return not (finite and within_bounds and (self._time < MAX_TIME_STEPS))

    # base_env.py:414-428 (is_within_env_bounds)
    def _within_env_bounds(self, error):
        return self._norm(error) < ENV_BOUNDING_BOX_NORM

    # base_env.py:430-439 (norm)
    @staticmethod
    def _norm(vector):
        return math.sqrt(sum(item * item for item in vector))

    @staticmethod
    def _clip(value, minimum, maximum):
        return min(max(value, minimum), maximum)
