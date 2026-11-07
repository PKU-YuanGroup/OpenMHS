"""Fake backend of the AASEnv-v0 driver: a pure Python clock recording stand-in for ``aas_gym.aas_env:AASEnv``.

Why a fake: the upstream class imports numpy, gymnasium, docker and pyzmq and its constructor creates Docker
containers from the simulation and aircraft images (aas-gym/src/aas_gym/aas_env.py:1-12 and :163-228); package code
never imports or runs the clone, and the gate has no Docker/Gazebo stack.  This module mirrors the public surface
the bridge uses (``reset``, ``step`` and ``close``; gate G7) and the observable scalar rules of ``AASEnv``: the
observation is the Gazebo /clock ``[sim_sec, sim_nanosec]`` (aas_env.py:284-288 and :41-46), a reset restarts the
world and returns the clock after the init run (aas_env.py:290-357), and a step returns reward -1.0, terminated
False and truncated when ``step_count >= max_steps`` (aas_env.py:359-400).  The two space classes duck-type
``gymnasium.spaces.Box`` (the bridge reads ``low``, ``high``, ``shape`` and ``dtype``).

What this is not: the upstream Gazebo/PX4 simulator.  It records the action and advances a clock by the nominal
control period; it has no rigid-body dynamics, contacts, actuator, sensor, wind, camera or LiDAR model.  Every
number below is test data that mirrors a constructor default or a step rule of the clone, is marked ``# placeholder``
and is never a Fact or a Limit by itself.  The driver's fidelity ``gaps`` say what is missing.

Nothing here talks to a device.
"""

# Placeholder values: the constructor defaults of aas_env.py:20-33 and the action/observation spaces of :35-46.
DEFAULT_GYM_FREQ_HZ = 50                     # placeholder: aas_env.py:20
INIT_DURATION_S = 80.0                       # placeholder: aas_env.py:32
MAX_EPISODE_LENGTH_S = 300.0                 # placeholder: aas_env.py:33
ACTION_LOW = -1.0                            # placeholder: aas_env.py:37
ACTION_HIGH = 1.0                            # placeholder: aas_env.py:38
OBSERVATION_LOW = [0.0, 0.0]                 # placeholder: aas_env.py:43
OBSERVATION_HIGH_SEC = float("inf")          # placeholder: aas_env.py:44
OBSERVATION_HIGH_NANOSEC = 1e9               # placeholder: aas_env.py:44
NANOSECONDS_PER_SECOND = 1_000_000_000       # placeholder: the nanosecond unit of the /clock payload (aas_env.py:333)


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high, dtype="float64"):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = dtype


class FakeAASEnv:
    """AASEnv without Docker or Gazebo: ``reset(seed, options)``, ``step(action)`` and ``close()`` as upstream."""

    def __init__(self, gym_freq_hz=DEFAULT_GYM_FREQ_HZ, instance=0, autopilot="px4", camera=True, lidar=True,
                 odom="none", num_quads=1, render_mode=None, gpu=True):
        self.GYM_FREQ_HZ = gym_freq_hz
        self.GYM_INIT_DURATION = INIT_DURATION_S
        self.MAX_EPISODE_LENGTH_SEC = MAX_EPISODE_LENGTH_S
        self.max_steps = int(self.MAX_EPISODE_LENGTH_SEC * self.GYM_FREQ_HZ)
        self.step_count = 0
        self.sim_sec = 0.0
        self.sim_nanosec = 0
        self.render_mode = render_mode
        self.action_space = Box([ACTION_LOW], [ACTION_HIGH], dtype="float32")
        self.observation_space = Box(OBSERVATION_LOW, [OBSERVATION_HIGH_SEC, OBSERVATION_HIGH_NANOSEC])
        self.INSTANCE = instance
        self.AUTOPILOT = autopilot
        self.CAMERA = camera
        self.LIDAR = lidar
        self.ODOM = odom
        self.NUM_QUADS = num_quads
        self._seed = None
        self._last_action = None
        self._closed = False

    def reset(self, seed=None, options=None):
        """Restart the world and return ``(clock_observation, info)`` (aas_env.py:290-357).

        The seed is recorded only: upstream passes it to gym.Env's generator and the ZeroMQ reset payload is the
        constant 9999.0 (aas_env.py:291 and :327-328), so the fake does not use it either.
        """
        self._seed = seed
        self.step_count = 0
        self._last_action = None
        self._advance(self.GYM_INIT_DURATION)
        return self._observation(), self._info()

    def step(self, action):
        """Apply ``action[0]`` and return the clock, reward, terminated, truncated and info (aas_env.py:359-400)."""
        force = float(action[0])
        self._last_action = force
        self.step_count += 1
        self._advance(1.0 / float(self.GYM_FREQ_HZ))
        reward = -1.0                                                   # aas_env.py:387
        terminated = False                                              # aas_env.py:389
        truncated = self.step_count >= self.max_steps                   # aas_env.py:391
        return self._observation(), reward, terminated, truncated, self._info()

    def close(self):
        """Release the state; upstream stops and removes the containers (aas_env.py:416-428)."""
        self._closed = True

    def _advance(self, seconds):
        """Advance the simulated clock by ``seconds`` (the /clock payload is sec and nanosec)."""
        self.sim_nanosec += int(round(seconds * NANOSECONDS_PER_SECOND))
        self.sim_sec += self.sim_nanosec // NANOSECONDS_PER_SECOND
        self.sim_nanosec %= NANOSECONDS_PER_SECOND

    def _observation(self):
        """``np.array([sim_sec, sim_nanosec])`` without numpy (aas_env.py:284-285)."""
        return [self.sim_sec, self.sim_nanosec]

    def _info(self):
        """``{"sim_time_sec": ..., "sim_time_nanosec": ...}`` (aas_env.py:287-288)."""
        return {"sim_time_sec": self.sim_sec, "sim_time_nanosec": self.sim_nanosec}
