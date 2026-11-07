"""Fake backend of the Genesis humanoid driver: a pure Python stand-in for ``HumanoidWalkingEnv``.

Why a fake: the upstream environment needs Python 3.10 and ``genesis-world``, ``torch`` and ``stable-baselines3``
(pyproject.toml:6-12), none of which is available where the gate runs (Python 3.14), and package code never imports
or runs the clone.  This module mirrors the public surface of
``genesis_humanoid_rl.environments.humanoid_env:HumanoidWalkingEnv`` -- ``reset``, ``step``, ``render`` and
``close`` (gate G7) -- with the same ``Box`` action space (low -1.0, high 1.0), the same observation layout and the
same reward and termination rules of that class.  The two space classes duck-type ``gymnasium.spaces.Box``: the
bridge reads ``low``, ``high``, ``shape`` and ``dtype``.

What this is not: the upstream environment.  It does not run Genesis, does not integrate rigid-body contacts or
actuator torques, and was never compared with the upstream simulator.  Every number that is not read from the clone
is test data and is marked ``# placeholder``; the driver's fidelity ``gaps`` list what is not modelled, including
the stand-in joint count.  Nothing here talks to a device.
"""

# Placeholder joint count: the real environment sizes both spaces from ``robot.n_dofs`` after loading
# ``assets/robots/g1/g1_29dof.urdf`` (humanoid_env.py:98 and :124).  This fake uses a smaller, fixed array so receipts
# stay small; the real size is named in the driver fidelity gaps and in RESULT.json notes.
NUM_JOINTS = 6                                          # placeholder
# Placeholder spawn position: the environment spawns the G1 at (0, 0, 1.0) (humanoid_env.py:104) and then lowers it
# by an automatically computed grounding height; the fake keeps the spawn point and does not model grounding.
SPAWN = [0.0, 0.0, 1.0]                                 # placeholder (spawn z is humanoid_env.py:104)
IDENTITY_QUAT = [0.0, 0.0, 0.0, 1.0]                    # placeholder: upright start orientation (x, y, z, w)
POSITION_STEP = 0.1                                     # humanoid_env.py:163-165: action * 0.1
TARGET_HEIGHT = 0.8                                     # humanoid_env.py:263
HEIGHT_COEFF = 0.3                                      # humanoid_env.py:266
STABILITY_COEFF = 0.5                                   # humanoid_env.py:259
ENERGY_COEFF = 0.1                                      # humanoid_env.py:272
SMOOTHNESS_COEFF = 0.1                                  # humanoid_env.py:279


class Box:
    """Duck-typed one-dimensional ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"

    def contains(self, value):
        try:
            values = [float(item) for item in value]
        except (TypeError, ValueError):
            return False
        return len(values) == len(self.low) and all(
            low <= item <= high for item, low, high in zip(values, self.low, self.high))


class FakeHumanoidWalkingEnv:
    """A kinematic stand-in for ``HumanoidWalkingEnv`` with the upstream spaces, observation and reward layout."""

    def __init__(
        self,
        render_mode=None,
        simulation_fps=100,
        control_freq=20,
        episode_length=1000,
        target_velocity=1.0,
        **kwargs,
    ):
        self.render_mode = render_mode
        self.simulation_fps = simulation_fps
        self.control_freq = control_freq
        self.episode_length = episode_length
        self.target_velocity = target_velocity
        self.num_joints = NUM_JOINTS
        self.joint_names = None
        # humanoid_env.py:129-131: Box(low=-1.0, high=1.0, shape=(num_joints,), dtype=np.float32)
        self.action_space = Box([-1.0] * self.num_joints, [1.0] * self.num_joints)
        # humanoid_env.py:136-139: 3 + 4 + 3 * num_joints + 1 unbounded observation values
        observation_dim = 3 + 4 + 3 * self.num_joints + 1
        self.observation_space = Box([float("-inf")] * observation_dim, [float("inf")] * observation_dim)
        self.current_step = 0
        self.previous_action = [0.0] * self.num_joints
        self._pos = list(SPAWN)
        self._quat = list(IDENTITY_QUAT)
        self._joint_pos = [0.0] * self.num_joints
        self._joint_vel = [0.0] * self.num_joints
        self._previous_pos = list(self._pos)

    def reset(self, seed=None, options=None):
        """Restore the initial state; the upstream reset rebuilds the Genesis scene (humanoid_env.py:71-148)."""
        # The upstream reset calls gymnasium.Env.reset(seed=seed) (line 75) but draws no random initial state: the
        # robot is spawned, grounded and settled deterministically.  The fake reproduces that; ``options`` is
        # accepted and ignored, as it is upstream.
        self.current_step = 0
        self.previous_action = [0.0] * self.num_joints
        self._pos = list(SPAWN)
        self._quat = list(IDENTITY_QUAT)
        self._joint_pos = [0.0] * self.num_joints
        self._joint_vel = [0.0] * self.num_joints
        self._previous_pos = list(self._pos)
        return self._get_observation(), {}

    def step(self, action):
        """Apply one control step: clip, move the joints and evaluate the upstream reward and termination rules."""
        values = self._clip(action)                       # humanoid_env.py:152-153
        # humanoid_env.py:160-166: target_pos = current_pos + action * 0.1, then position control.  The fake moves
        # the joints to that target and reports the velocity the move implies over one control period.
        dt = 1.0 / float(self.control_freq)               # humanoid_env.py:239
        self._joint_vel = [(value * POSITION_STEP) / dt for value in values]
        self._joint_pos = [position + value * POSITION_STEP
                           for position, value in zip(self._joint_pos, values)]
        observation = self._get_observation()             # humanoid_env.py:174
        reward = self._calculate_reward(values)           # humanoid_env.py:177
        self.current_step += 1                            # humanoid_env.py:180
        terminated = self._is_terminated()                # humanoid_env.py:183
        truncated = self.current_step >= self.episode_length  # humanoid_env.py:184
        self.previous_action = list(values)               # humanoid_env.py:187
        info = {"step": self.current_step, "terminated": terminated, "truncated": truncated}
        return observation, reward, terminated, truncated, info

    def render(self):
        """The upstream render is a no-op unless render_mode is "human" with a Genesis viewer (humanoid_env.py:329-334)."""
        return None

    def close(self):
        """The upstream close is a no-op: Genesis cleans up itself (humanoid_env.py:336-339)."""
        return None

    def _clip(self, action):
        """``np.clip(action, -1.0, 1.0)`` of humanoid_env.py:153, with the upstream array length enforced."""
        try:
            values = [float(item) for item in action]
        except (TypeError, ValueError) as exc:
            raise ValueError("action must be a sequence of numbers") from exc
        if len(values) != self.num_joints:
            raise ValueError(f"action has {len(values)} values; the environment has {self.num_joints} joints")
        return [max(-1.0, min(1.0, value)) for value in values]

    def _get_observation(self):
        """The concatenation of humanoid_env.py:210-222 in the same order."""
        return (list(self._pos) + list(self._quat) + list(self._joint_pos) + list(self._joint_vel)
                + list(self.previous_action) + [float(self.target_velocity)])

    def _calculate_reward(self, action):
        """The reward terms of humanoid_env.py:224-291 evaluated on the fake's kinematic state."""
        total_reward = 0.0
        pos = self._pos
        # 1. forward velocity reward (humanoid_env.py:236-244); the fake's base does not move, so this term is 0
        dt = 1.0 / float(self.control_freq)
        forward_velocity = (pos[0] - self._previous_pos[0]) / dt
        if self.target_velocity:
            total_reward += 1.0 * min(forward_velocity / self.target_velocity, 2.0)
        # 2. stability reward (humanoid_env.py:246-259); the fake keeps the base upright (identity quaternion)
        tilt_magnitude = (self._quat[0] ** 2 + self._quat[1] ** 2) ** 0.5
        total_reward += STABILITY_COEFF * max(0.0, 1.0 - 2.0 * tilt_magnitude)
        # 3. height maintenance reward (humanoid_env.py:261-266)
        height_diff = abs(pos[2] - TARGET_HEIGHT)
        total_reward += HEIGHT_COEFF * max(0.0, 1.0 - height_diff)
        # 4. energy efficiency penalty (humanoid_env.py:268-272), capped at 10.0
        joint_vel_penalty = sum(value * value for value in self._joint_vel) / self.num_joints
        total_reward -= ENERGY_COEFF * min(joint_vel_penalty, 10.0)
        # 5. action smoothness penalty (humanoid_env.py:274-279), capped at 2.0
        action_diff = sum((value - previous) ** 2
                          for value, previous in zip(action, self.previous_action)) / self.num_joints
        total_reward -= SMOOTHNESS_COEFF * min(action_diff, 2.0)
        # 6. the too-high penalty of humanoid_env.py:281-286
        if pos[2] > 1.2:
            total_reward -= 0.5
        self._previous_pos = list(pos)
        return float(total_reward)

    def _is_terminated(self):
        """The termination rules of humanoid_env.py:293-323 on the fake's base position."""
        if self._pos[2] < 0.3:                           # humanoid_env.py:303
            return True
        if abs(self._pos[0]) > 10.0 or abs(self._pos[1]) > 5.0:  # humanoid_env.py:316
            return True
        if self._pos[2] > 2.0:                           # humanoid_env.py:320
            return True
        return False
