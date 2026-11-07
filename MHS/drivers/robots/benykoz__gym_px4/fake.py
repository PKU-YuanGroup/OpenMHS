"""Pure-Python fake backend for the legacy Gym PX4 environment.

The fake preserves the upstream ``gymPX4`` surface the bridge uses:
``action_space`` and ``observation_space`` (the one-value thrust Box and the
two-value observation Box), the legacy ``reset()`` return value and
``step(action)`` four-tuple, and ``close()``.  It replaces the live PX4
Gazebo SITL/MAVROS backend with a small vertical-only altitude model.

Every number in this file is test data, not a fact, a limit or a source
reference.  The fake imports no ROS, gym, PX4 or upstream module.
"""


class Box:
    """Duck-typed ``gym.spaces.Box``: ``low``/``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high, shape=(), dtype="float32"):
        self.low = low
        self.high = high
        self.shape = tuple(shape)
        self.dtype = dtype


class FakeGymPx4:
    """The public legacy-Gym surface of ``gym_px4.envs.gymPX4_env:gymPX4``."""

    def __init__(self, **_options):
        # placeholder: the upstream Box is Box(0.0, 1.0, shape=(1,))
        self.min_action = 0.0
        self.max_action = 1.0
        self.action_space = Box(self.min_action, self.max_action, shape=(1,))
        # placeholder: the upstream observation Box is Box([0.1, -3], [25, 3])
        self.observation_space = Box([0.1, -3.0], [25.0, 3.0], shape=(2,))
        self._closed = False
        self._reset_state()

    def reset(self):
        """Reset to the fixed upstream start state and return the legacy observation only.

        Like the upstream ``gymPX4.reset(self)``, it takes no seed or options, so the bridge
        falls back to a plain ``reset()`` call as it would for the upstream environment.
        """
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        self._reset_state()
        return self._observation()

    def step(self, action):
        """Apply one thrust action and return the legacy ``(ob, reward, done, info)`` tuple."""
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        thrust = self._thrust(action)
        # placeholder: a simple vertical model; no PX4, Gazebo or MAVROS integration
        self.local_velocity[2] += (thrust - 0.5) * 0.01
        self.local_position[2] += self.local_velocity[2] * 0.005

        ob = self._observation()
        reward = -(self.desired - self.local_position[2]) ** 2
        done = False
        reason = "No"

        # placeholder: the same terminal regions the upstream code documents
        if abs(self.local_position[0]) > 2 or abs(self.local_position[1]) > 2 \
                or self.local_position[2] > 3 or self.local_position[2] < 1:
            done = True
            reason = "out of region"
            reward = -1000.0
        if self.steps > 5000:                       # placeholder: upstream step-count bound
            done = True
            reason = "limit time steps"
        if abs(ob[0]) < 0.1:                        # placeholder: upstream altitude tolerance
            self.success_steps += 1
            if self.success_steps > 50:             # placeholder: upstream success run length
                done = True
                reason = "sim success"
                reward += 10000.0

        self.steps += 1
        self.last_pos = list(self.local_position)
        info = {
            "state": list(ob),
            "action": action,
            "reward": reward,
            "step": self.steps,
            "step length": 0.0,                     # placeholder: no wall-clock pacing in the fake
            "reset reason": reason,
        }
        return ob, reward, done, info

    def close(self):
        self._closed = True

    def render(self):
        pass

    def _reset_state(self):
        self.desired = 2.0                          # placeholder: upstream fixed reset target
        self.initial = 2.0                          # placeholder: upstream fixed start altitude
        self.local_position = [0.0, 0.0, self.initial]
        self.local_velocity = [0.0, 0.0, 0.0]
        self.last_pos = list(self.local_position)
        self.steps = 0
        self.success_steps = 0

    def _observation(self):
        return [self.desired - self.local_position[2], self.local_velocity[2]]

    @staticmethod
    def _thrust(action):
        """Accept the scalar the upstream sets and the one-value Box the bridge sends."""
        if isinstance(action, (list, tuple)):
            value = action[0] if action else 0.0
        else:
            value = action
        return float(value)
