"""Fake backend of the X1DHStandEnv driver: a pure-Python stand-in for the upstream Isaac Gym environment.

The public surface is the upstream ``step(actions)`` and ``reset()`` of
``humanoid.envs.x1.x1_dh_stand_env:X1DHStandEnv`` and its ``LeggedRobot`` base
(x1_dh_stand_env.py:353-356; legged_robot.py:111-162).  ``step`` takes a
``(num_envs, num_actions)`` batch and returns ``(obs_buf, privileged_obs_buf, rew_buf, reset_buf, extras)``;
``reset`` returns ``(obs, privileged_obs)``.  The array sizes follow the shipped ``X1DHStandCfg``:
66 * 47 = 3102 observation values, 3 * 73 = 219 privileged values and 12 actions
(x1_dh_stand_config.py:41-49).

What this is not: the Isaac Gym simulator.  There is no rigid body, contact, terrain, PD controller, domain
randomization, command sampler or reward term here.  Every numeric value below is test data marked ``# placeholder``;
the fake was never compared with the upstream environment, which needs Isaac Gym, torch and a GPU.  The driver's
fidelity ``gaps`` list these omissions.
"""

#: The shipped sizes: 66 frames of 47 values, 3 frames of 73 values and 12 actions (x1_dh_stand_config.py:41-49).
OBSERVATION_SIZE = 66 * 47              # placeholder: size only, the layout is not the upstream one
PRIVILEGED_OBSERVATION_SIZE = 3 * 73    # placeholder
ACTION_SIZE = 12                        # placeholder

#: The fake's own stand-in dynamics and episode limit; none of these is an upstream number.
ACTION_CLIP = 100.0                     # placeholder: stands in for the shipped clip_actions
ACTION_SCALE = 0.5                      # placeholder: stands in for the shipped action_scale
VELOCITY_DECAY = 0.9                    # placeholder
POSITION_GAIN = 0.01                    # placeholder
EPISODE_STEPS = 2400                    # placeholder


class FakeX1DHStandEnv:
    """A stand-in for ``X1DHStandEnv``: the same two public methods and the same return shapes."""

    def __init__(self, **_options):
        self._dof_pos = [0.0] * ACTION_SIZE
        self._dof_vel = [0.0] * ACTION_SIZE
        self._last_action = [0.0] * ACTION_SIZE
        self._step_count = 0
        self._reward = 0.0
        self._calls = []

    def _reset_state(self) -> None:
        self._dof_pos = [0.0] * ACTION_SIZE          # placeholder
        self._dof_vel = [0.0] * ACTION_SIZE          # placeholder
        self._last_action = [0.0] * ACTION_SIZE      # placeholder
        self._step_count = 0
        self._reward = 0.0                           # placeholder

    def _observation(self) -> list:
        """A full-size 3102-value vector filled from the fake's 12 joints (not the upstream layout)."""
        observation = [0.0] * OBSERVATION_SIZE       # placeholder
        observation[0:ACTION_SIZE] = self._dof_pos
        observation[ACTION_SIZE:2 * ACTION_SIZE] = self._dof_vel
        observation[2 * ACTION_SIZE:3 * ACTION_SIZE] = self._last_action
        return observation

    def _privileged_observation(self) -> list:
        """A full-size 219-value vector filled from the fake's 12 joints (not the upstream layout)."""
        privileged = [0.0] * PRIVILEGED_OBSERVATION_SIZE  # placeholder
        privileged[0:ACTION_SIZE] = self._dof_pos
        return privileged

    def _action_values(self, actions) -> list:
        """Read the first environment's row out of the upstream ``(num_envs, num_actions)`` batch."""
        if isinstance(actions, dict) or not isinstance(actions, (list, tuple)) or not actions:
            raise ValueError("step expects a (num_envs, num_actions) batch")
        row = actions[0]
        if not isinstance(row, (list, tuple)) or len(row) != ACTION_SIZE:
            raise ValueError(f"step expects {ACTION_SIZE} action values per environment")
        return [float(value) for value in row]

    def reset(self):
        """``legged_robot.py:157-162``: reset and return ``(obs, privileged_obs)``."""
        self._calls.append(("reset", {}))
        self._reset_state()
        return self._observation(), self._privileged_observation()

    def step(self, actions):
        """``legged_robot.py:111-155``: return ``(obs, privileged_obs, reward, reset_flag, extras)``."""
        values = self._action_values(actions)
        self._calls.append(("step", list(values)))
        clipped = [max(-ACTION_CLIP, min(ACTION_CLIP, value)) for value in values]  # placeholder
        for index, value in enumerate(clipped):
            target = ACTION_SCALE * value                                          # placeholder
            self._dof_vel[index] = (VELOCITY_DECAY * self._dof_vel[index]
                                    + 0.1 * (target - self._dof_pos[index]))  # placeholder: 0.1
            self._dof_pos[index] = max(-1.0, min(1.0, self._dof_pos[index]
                                                 + POSITION_GAIN * self._dof_vel[index]))  # placeholder
        self._last_action = clipped
        self._step_count += 1
        self._reward = 1.0 / (1.0 + sum(abs(value) for value in clipped))          # placeholder
        reward = self._reward
        terminated = self._step_count >= EPISODE_STEPS                             # placeholder
        if terminated:
            self._reset_state()
        return (self._observation(), self._privileged_observation(), reward, terminated,
                {"tick": self._step_count})
