"""Fake backend of the Unitree RL Gym Go2 driver: a pure-Python stand-in for LeggedRobot.

Gate G7: the public methods defined here are members the clone's
``legged_gym.envs.base.legged_robot:LeggedRobot`` class (or its ``BaseTask`` base) has: ``step``,
``reset``, ``reset_idx``, ``get_observations`` and ``get_privileged_observations``.  The attributes
the driver reads are the upstream buffer names (``num_envs``, ``num_actions``, ``num_obs``,
``num_privileged_obs``, ``obs_buf``, ``privileged_obs_buf``, ``rew_buf``, ``reset_buf``,
``time_out_buf``, ``episode_length_buf``, ``extras``) and the constructor parameter names are the
upstream ones.

What this is not: the upstream Isaac Gym environment.  It runs no PhysX, URDF, contact, terrain,
command, reward or PD computation.  The observation layout follows the upstream concatenation order
(``legged_gym/envs/base/legged_robot.py:182-192``) but every value and the initial joint positions
below are placeholder test data.  One transition is one closed-form update; the 20 ms control period
and the four physics substeps of the upstream step are not simulated.  The fake was not compared
with the upstream simulator.

Nothing here talks to a device.  ``_commands`` records the calls received (a private test hook), and
``_force_termination`` lets a test put one environment into the native terminal path.
"""

# The upstream base config defaults to 12 actions, 48 observations, 12 DOFs and decimation 4 at a
# 0.005 s physics timestep.  These are stand-in dimensions for the fake, not asserted device bounds.
NUM_ACTIONS = 12          # placeholder
NUM_OBSERVATIONS = 48     # placeholder
NUM_DOFS = 12             # placeholder
MAX_EPISODE_LENGTH = 1000  # placeholder: 20 s / 0.02 s
CONTROL_PERIOD_S = 0.02   # placeholder
CLIP_ACTIONS = 100.0      # placeholder
ACTION_SCALE = 0.25       # placeholder
DOF_NAMES = tuple(f"joint_{number}" for number in range(1, NUM_DOFS + 1))  # placeholder
START_DOF_POS = (0.0,) * NUM_DOFS  # placeholder


class FakeLeggedRobot:
    """A minimal stand-in for the Go2 ``LeggedRobot`` environment: buffers plus step/reset."""

    def __init__(self, cfg=None, sim_params=None, physics_engine=None, sim_device=None, headless=True, **options):
        self.cfg = cfg
        self.sim_params = sim_params
        self.physics_engine = physics_engine
        self.sim_device = sim_device
        self.headless = headless
        self.device = "cpu"
        self.gym = None
        self.sim = None
        self.viewer = None
        self.envs = []
        self.actor_handles = []
        self.num_envs = int(options.get("num_envs", 1))
        if self.num_envs < 1:
            raise ValueError("num_envs must be at least 1")
        self.num_obs = NUM_OBSERVATIONS
        self.num_privileged_obs = None
        self.num_actions = NUM_ACTIONS
        self.num_dof = NUM_DOFS
        self.num_dofs = NUM_DOFS
        self.dof_names = list(DOF_NAMES)
        self.dt = CONTROL_PERIOD_S
        self.max_episode_length = MAX_EPISODE_LENGTH
        self.max_episode_length_s = self.dt * self.max_episode_length
        self.common_step_counter = 0
        self.init_done = True
        self.episode_length_buf = [0] * self.num_envs
        self.reset_buf = [1] * self.num_envs
        self.time_out_buf = [False] * self.num_envs
        self.rew_buf = [0.0] * self.num_envs
        self.privileged_obs_buf = None
        self.extras = {}
        self.actions = [[0.0] * self.num_actions for _ in range(self.num_envs)]
        self.last_actions = [[0.0] * self.num_actions for _ in range(self.num_envs)]
        self.last_dof_vel = [[0.0] * self.num_dof for _ in range(self.num_envs)]
        self.last_root_vel = [[0.0] * 6 for _ in range(self.num_envs)]
        self.dof_pos = [list(START_DOF_POS) for _ in range(self.num_envs)]
        self.dof_vel = [[0.0] * self.num_dof for _ in range(self.num_envs)]
        self.default_dof_pos = [list(START_DOF_POS)]
        self.obs_buf = [self._observation(index) for index in range(self.num_envs)]
        self._forced_termination = [False] * self.num_envs
        self._commands = []

    # -- the upstream environment interface ----------------------------------------------------------------
    def step(self, actions):
        """Apply one action, advance every environment and return the native five-tuple."""
        if hasattr(actions, "tolist"):
            actions = actions.tolist()
        clipped = self._clip(actions)
        self._commands.append(("step", {"actions": [list(row) for row in clipped]}))
        self.last_actions = [list(row) for row in self.actions]
        self.actions = [list(row) for row in clipped]
        for index in range(self.num_envs):
            self.dof_pos[index] = [position + ACTION_SCALE * value
                                   for position, value in zip(self.dof_pos[index], clipped[index])]
            self.dof_vel[index] = [0.1 * value for value in clipped[index]]
            self.episode_length_buf[index] += 1
        self.common_step_counter += 1
        for index in range(self.num_envs):
            forced = self._forced_termination[index]
            timed_out = self.episode_length_buf[index] > self.max_episode_length
            self.time_out_buf[index] = bool(timed_out)
            self.reset_buf[index] = 1 if (forced or timed_out) else 0
        for index in range(self.num_envs):
            if self.reset_buf[index]:
                self._reset_environment(index)
        for index in range(self.num_envs):
            self.obs_buf[index] = self._observation(index)
            self.rew_buf[index] = 0.0  # placeholder: the upstream reward functions are not modelled
        self.last_dof_vel = [list(row) for row in self.dof_vel]
        self.extras = {"episode": {}, "time_outs": list(self.time_out_buf)}  # placeholder
        return (self.obs_buf, self.privileged_obs_buf, self.rew_buf, self.reset_buf, self.extras)

    def reset(self):
        """``BaseTask.reset``: reset every environment and take one zero-action step."""
        self._commands.append(("reset", {}))
        self.reset_idx(list(range(self.num_envs)))
        observation, privileged, _, _, _ = self.step(
            [[0.0] * self.num_actions for _ in range(self.num_envs)])
        return observation, privileged

    def reset_idx(self, env_ids):
        """Reset the selected environments, as ``LeggedRobot.reset_idx`` does for native env ids."""
        if hasattr(env_ids, "tolist"):
            env_ids = env_ids.tolist()
        if isinstance(env_ids, int):
            env_ids = [env_ids]
        for index in list(env_ids):
            self._reset_environment(int(index))
        self.extras["episode"] = {}
        self.extras["time_outs"] = list(self.time_out_buf)

    def get_observations(self):
        return self.obs_buf

    def get_privileged_observations(self):
        return self.privileged_obs_buf

    # -- internals -----------------------------------------------------------------------------------------
    def _reset_environment(self, index):
        self.dof_pos[index] = list(START_DOF_POS)
        self.dof_vel[index] = [0.0] * self.num_dof
        self.actions[index] = [0.0] * self.num_actions
        self.last_actions[index] = [0.0] * self.num_actions
        self.episode_length_buf[index] = 0
        self.reset_buf[index] = 1
        self.rew_buf[index] = 0.0
        self._forced_termination[index] = False

    def _clip(self, actions):
        if not isinstance(actions, (list, tuple)) or len(actions) != self.num_envs:
            raise ValueError(f"actions must have {self.num_envs} rows")
        rows = []
        for index, row in enumerate(actions):
            if not isinstance(row, (list, tuple)) or len(row) != self.num_actions:
                raise ValueError(f"actions[{index}] must have {self.num_actions} values")
            rows.append([max(-CLIP_ACTIONS, min(CLIP_ACTIONS, float(value))) for value in row])
        return rows

    def _observation(self, index):
        """The upstream concatenation order, filled with placeholder values."""
        observation = [0.0] * self.num_obs
        observation[0:3] = [0.0, 0.0, 0.0]          # placeholder base linear velocity
        observation[3:6] = [0.0, 0.0, 0.0]          # placeholder base angular velocity
        observation[6:9] = [0.0, 0.0, -1.0]         # placeholder projected gravity
        observation[9:12] = [0.0, 0.0, 0.0]         # placeholder commands
        start = 12
        observation[start:start + self.num_actions] = list(self.dof_pos[index])
        start += self.num_actions
        observation[start:start + self.num_actions] = list(self.dof_vel[index])
        start += self.num_actions
        observation[start:start + self.num_actions] = list(self.actions[index])
        return observation

    # -- hooks for test_driver.py (not LeggedRobot members, never used by the driver) ----------------------
    def _force_termination(self, env_id=0):
        """Make the next step of ``env_id`` report a native contact termination."""
        self._forced_termination[int(env_id)] = True
