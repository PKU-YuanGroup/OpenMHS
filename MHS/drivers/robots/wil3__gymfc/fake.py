"""Fake backend of the GymFC driver: a pure Python stand-in for the registered ``gymfc_nf-step-v1`` environment.

Why a fake: the upstream environment needs Gazebo 10.1.0 with Dart, the C++ Aircraft plugins built by ``setup.py``, a
digital-twin SDF and a UDP protobuf channel to the simulator (gymfc/envs/fc_env.py:168-172 and :488-493,
setup.py:9-32), and package code never imports or runs the clone.  This module re-implements the environment's
observable interface and the deterministic parts of its control logic, not the Gazebo physics.

What is modelled, with the upstream lines that state it:

* the legacy gym interface of ``StepEnv``: ``reset()`` returns the observation, ``step(action)`` returns a four-tuple
  and ``seed(seed)`` seeds the generator (examples/gymfc_nf/envs/base.py:67-105, :144-152,
  examples/gymfc_nf/envs/step.py:56-68);
* a four-element Box action space between -1 and 1 and an unbounded six-element observation Box
  (examples/gymfc_nf/envs/base.py:37-41, examples/gymfc_nf/envs/states.py:19-21);
* the action clipping to [0, 1]: ``step`` calls ``action_to_control_signal(action, 0, 1)``
  (examples/gymfc_nf/envs/base.py:79 and :107-116);
* the registered episode: max_rate 100, pulse_width 2.048 s, max_sim_time 4.608 s
  (examples/gymfc_nf/envs/__init__.py:6-14);
* the step target timing and the reset draw (examples/gymfc_nf/envs/step.py:46-68);
* a fixed physics step of 0.001 s (gymfc/envs/assets/gazebo/worlds/attitude.world:16);
* the reward terms of examples/gymfc_nf/envs/rewards.py:33-88.

What is not modelled: the Gazebo/Dart rigid-body, contact and aerodynamic dynamics, the IMU/ESC/battery sensors,
noise, the UDP channel and packet loss, gzserver startup and the digital-twin SDF.  The motor mixing and the
first-order rate response below are stand-ins, not the upstream model, and were not compared with a real run.  The
public members are the ones the upstream environment has (``reset``, ``step``, ``seed``, ``close``, ``sample_target``,
``update_setpoint``, ``action_to_control_signal`` and ``compute_reward``); ``action_space`` and ``observation_space``
are instance data.  Nothing here talks to a device.
"""

import math
import random

#: Registered kwargs of gymfc_nf-step-v1 (examples/gymfc_nf/envs/__init__.py:9-14).
MAX_RATE = 100
PULSE_WIDTH = 2.048
MAX_SIM_TIME = 4.608
#: Physics step of the configured world (gymfc/envs/assets/gazebo/worlds/attitude.world:16).
STEP = 0.001
#: First pulse time and pulse duration timing (examples/gymfc_nf/envs/step.py:43, :50 and :60).
FIRST_PULSE = 0.512
#: Reward terms (examples/gymfc_nf/envs/rewards.py:48-73).
ERROR_BAND = 5
PERCENT_IDLE = 0.12
MAX_MIN_Y_REWARD = 1000
#: Stand-in motor mixer and first-order rate response: placeholder, not the Gazebo/Dart model.
RATE_GAIN = 12.0
RATE_TAU = 0.12


class Box:
    """Duck-typed one-dimensional ``gym.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high, dtype="float32"):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = dtype


class FakeStepEnv:
    """The registered ``gymfc_nf-step-v1`` environment without Gazebo, numpy or the upstream package."""

    def __init__(self, pulse_width=PULSE_WIDTH, max_rate=MAX_RATE, state_fn=None,
                 max_sim_time=MAX_SIM_TIME):
        # BaseEnv.__init__ (examples/gymfc_nf/envs/base.py:27-50)
        self.max_sim_time = max_sim_time
        self.state_fn = state_fn
        self._rng = random.Random()
        self._init()
        self.action_space = Box([-1.0, -1.0, -1.0, -1.0], [1.0, 1.0, 1.0, 1.0])       # base.py:37
        num_inputs = len(self._state())
        self.observation_space = Box([-math.inf] * num_inputs, [math.inf] * num_inputs)  # base.py:39-41
        self.sample_noise = lambda _local: 0                                            # base.py:46
        self.step_callback = None                                                       # base.py:50
        # StepEnv.__init__ (examples/gymfc_nf/envs/step.py:37-43)
        self.pulse_width = pulse_width
        self.max_rate = max_rate
        self.rising = True
        self.outputs = []
        self.generated_input = [0.0, 0.0, 0.0]

    def _init(self):
        """BaseEnv._init (examples/gymfc_nf/envs/base.py:118-142)."""
        self.y = [0.0, 0.0, 0.0, 0.0]
        self.last_y = [0.0, 0.0, 0.0, 0.0]
        self.angular_rate = [0.0, 0.0, 0.0]
        self.angular_rate_sp = [0.0, 0.0, 0.0]
        self.measured_error = [0.0, 0.0, 0.0]
        self.last_measured_error = [0.0, 0.0, 0.0]
        self.true_error = [0.0, 0.0, 0.0]
        self.imu_angular_velocity_rpy = [0.0, 0.0, 0.0]
        self.action = [0.0, 0.0, 0.0, 0.0]
        self.step_counter = 0
        self.sim_time = 0.0
        self.last_sim_time = -STEP
        self.obs = []
        self.prev_shaping = None
        self.ind_rewards = []

    def _state(self):
        """The registered state function: measured error and its delta (examples/gymfc_nf/envs/states.py:19-21)."""
        if callable(self.state_fn):
            return list(self.state_fn(self))
        delta = [self.measured_error[index] - self.last_measured_error[index] for index in range(3)]
        return list(self.measured_error) + delta

    def seed(self, seed=None):
        """BaseEnv.seed (examples/gymfc_nf/envs/base.py:150-152), with Python's generator instead of numpy's."""
        self._rng = random.Random(seed)
        return [seed]

    def sample_target(self):
        """StepEnv.sample_target (examples/gymfc_nf/envs/step.py:66-68)."""
        return [self._rng.gauss(0.0, self.max_rate) for _ in range(3)]

    def update_setpoint(self):
        """StepEnv.update_setpoint (examples/gymfc_nf/envs/step.py:46-54)."""
        if self.sim_time > self.next_pulse_time:
            if all(value == 0.0 for value in self.angular_rate_sp):
                self.angular_rate_sp = list(self.generated_input)
                self.next_pulse_time += self.pulse_width
            else:
                self.angular_rate_sp = [0.0, 0.0, 0.0]
                self.next_pulse_time += self.pulse_width
            self.rising = False

    def reset(self):
        """StepEnv.reset and BaseEnv.reset (examples/gymfc_nf/envs/step.py:56-64, base.py:144-148)."""
        self.rising = True
        self.outputs = []
        self.angular_rate_sp = [0.0, 0.0, 0.0]
        self.next_pulse_time = FIRST_PULSE                                         # step.py:60
        self.generated_input = self.sample_target()                                # step.py:63
        self._init()
        self.obs = self._state()
        return self.obs

    @staticmethod
    def action_to_control_signal(action, action_low, action_high, y_low=0, y_high=1):
        """BaseEnv.action_to_control_signal (examples/gymfc_nf/envs/base.py:107-116)."""
        scale = action_high - action_low
        return [((y_high - y_low) * (min(max(float(value), action_low), action_high) - action_low) / scale)
                + y_low for value in action]

    def compute_reward(self):
        """RewardEnv.compute_reward (examples/gymfc_nf/envs/rewards.py:33-88)."""
        shaping = -sum(value * value for value in self.true_error)
        e_penalty = 0.0 if self.prev_shaping is None else shaping - self.prev_shaping
        self.prev_shaping = shaping
        threshold = [max(abs(value) * 0.1, ERROR_BAND) for value in self.angular_rate_sp]
        inband = all(abs(self.true_error[index]) <= threshold[index] for index in range(3))
        average = sum(self.y) / 4.0
        if not inband:
            min_y_reward = 0.0
        elif average < PERCENT_IDLE:
            min_y_reward = MAX_MIN_Y_REWARD * (1 - PERCENT_IDLE)
        else:
            min_y_reward = MAX_MIN_Y_REWARD * (1 - average)
        oversaturation = sum(max(max(value, 0.0) - 1.0, 0.0) for value in self.action)
        doing_nothing = 0.0
        if sum(1 for value in self.y if value == 0.0) > 2 and any(value != 0.0 for value in self.angular_rate_sp):
            doing_nothing -= 1e9
        if all(value == 1.0 for value in self.y):
            doing_nothing -= 1e9
        rewards = [
            -1000 * max(abs(self.y[index] - self.last_y[index]) for index in range(4)),
            min_y_reward,
            e_penalty,
            -1e9 * oversaturation,
            doing_nothing,
        ]
        self.ind_rewards = rewards
        return sum(rewards)

    def step(self, action):
        """BaseEnv.step (examples/gymfc_nf/envs/base.py:67-105), with a stand-in for step_sim."""
        values = [float(value) for value in action]
        if len(values) != len(self.action_space.low):
            raise ValueError("the action must have one value per motor")
        self.action = values
        self.y = self.action_to_control_signal(self.action, 0, 1)                 # base.py:79
        # placeholder: X-quad motor mixer, not the Gazebo/Dart model
        roll = ((self.y[0] + self.y[3]) - (self.y[1] + self.y[2])) / 4.0
        pitch = ((self.y[0] + self.y[1]) - (self.y[2] + self.y[3])) / 4.0
        yaw = ((self.y[0] + self.y[2]) - (self.y[1] + self.y[3])) / 4.0
        for index, command in enumerate((roll, pitch, yaw)):
            acceleration = RATE_GAIN * command - self.imu_angular_velocity_rpy[index] / RATE_TAU
            self.imu_angular_velocity_rpy[index] += STEP * acceleration
        self.step_counter += 1
        self.sim_time = round(self.step_counter * STEP, 6)
        self.angular_rate = list(self.imu_angular_velocity_rpy)                   # base.py:84-85 (noise 0)
        self.true_error = [self.angular_rate_sp[index] - self.imu_angular_velocity_rpy[index]
                           for index in range(3)]                                  # base.py:86
        self.measured_error = [self.angular_rate_sp[index] - self.angular_rate[index]
                               for index in range(3)]                              # base.py:87
        done = self.sim_time >= self.max_sim_time                                  # base.py:89
        reward = self.compute_reward()                                             # base.py:91
        self.update_setpoint()                                                     # base.py:94
        state = self._state()                                                      # base.py:98
        self.last_measured_error = list(self.measured_error)                       # base.py:100
        self.last_y = list(self.y)                                                 # base.py:101
        if callable(self.step_callback):
            self.step_callback(self, state, reward, done)
        return state, reward, done, {}                                            # base.py:105

    def close(self):
        """Gymfc's close shuts the simulator down; the fake has no simulator process."""
        self.obs = []
