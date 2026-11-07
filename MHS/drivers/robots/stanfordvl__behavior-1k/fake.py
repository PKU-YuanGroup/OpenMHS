"""Fake backend of the BEHAVIOR-1K driver: a reduced stand-in for the OmniGibson ``Environment``.

Why a fake: the upstream ``Environment`` loads an Isaac Sim scene on an NVIDIA RTX GPU
(``docs/getting_started/installation.md:9-10``; ``setup.sh:339`` pins ``isaacsim[all,extscache]==5.1.0``) and the
gate neither imports the clone nor has that stack.  This module models only the surface the Gymnasium bridge uses,
with the same member names as ``omnigibson.envs.env_base:Environment`` (gate G7): ``reset``, ``step`` and ``close``.
The real class sets ``action_space`` as a Dict of robot name to ``robot.action_space``
(``OmniGibson/omnigibson/envs/env_base.py:429``) and ``observation_space`` as a Dict of robot, task and sensor spaces
(``:386-423``); this stand-in reduces both to one robot with two position-controlled joints and proprioception only.

What this is not: the upstream simulator.  There is no scene, no object, no contact, no sensor and no physics
engine here; the joint positions jump to the commanded values (a null position controller), the reward is 0.0 and
the episode never terminates, which mirrors the default ``DummyTask`` (no termination conditions, no reward
functions, ``OmniGibson/omnigibson/tasks/dummy_task.py:15-21``).  The environment was never imported or run.

Every number below is placeholder test data: the real joint count, poses, control limits and observation contents
depend on the scene and robot configuration, so none of them is a fact about the device.
"""

# The fake models one environment (env_base.py:1031 defaults num_envs to 1).  # placeholder
JOINT_COUNT = 2                     # placeholder: the real robot's action dimension is config-dependent
# Placeholder control bounds for the two position commands.  The real bounds are the robot's control limits,
# which depend on the selected robot and controller definition; they are not stated in the clone.
JOINT_LOW, JOINT_HIGH = -1.0, 1.0   # placeholder
# Placeholder proprioception bounds, wide enough to contain the reset pose and any accepted command.
PROPRIO_LOW, PROPRIO_HIGH = -3.5, 3.5   # placeholder
# Placeholder reset pose of the two joints (the real pose is the robot's reset_joint_pos).
RESET_POSITION = (0.0, 0.0)         # placeholder


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: a lower and an upper bound per element.

    The bridge reads ``low``, ``high``, ``shape`` and ``dtype`` and derives the step input limits from them
    (``MHS/sdk/src/mhs/bridge/gymnasium.py``); no upstream member is claimed here.
    """

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
            low <= item <= high for low, item, high in zip(self.low, values, self.high))


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: a mapping of names to subspaces.

    The bridge reads ``spaces`` (a Mapping) to derive the JSON action schema and observation encoding.
    """

    def __init__(self, spaces):
        self.spaces = dict(spaces)

    def contains(self, value):
        return isinstance(value, dict) and all(
            key in value and space.contains(value[key]) for key, space in self.spaces.items())


class FakeEnvironment:
    """One reduced OmniGibson environment: ``reset``, ``step`` and ``close`` as the upstream class has them.

    ``reset`` keeps the upstream signature ``reset(env_indices=None, get_obs=True, **kwargs)``
    (``env_base.py:838``): the bridge passes ``seed`` and ``options`` as keywords and the upstream reset has no
    parameter that reads them, so they are accepted and ignored here too.  ``step`` keeps
    ``step(action, n_render_iterations=1)`` (``env_base.py:718``) and returns a single environment's
    ``(observation, reward, terminated, truncated, info)``; upstream returns per-environment lists and tensors.
    """

    def __init__(self, configs=None, **options):
        # The upstream constructor takes configs (env_base.py:43); this stand-in ignores them.  # placeholder
        self.num_envs = 1                                                     # placeholder
        self.render_mode = "rgb_array"                                        # env_base.py:55
        self.metadata = {"render.modes": ["rgb_array"]}                       # env_base.py:56
        self.action_space = Dict({"robot": Box([JOINT_LOW] * JOINT_COUNT,
                                               [JOINT_HIGH] * JOINT_COUNT)})  # placeholder
        self.observation_space = Dict({"robot": Dict({
            "proprio": Box([PROPRIO_LOW] * JOINT_COUNT, [PROPRIO_HIGH] * JOINT_COUNT)})})  # placeholder
        self._joint_positions = list(RESET_POSITION)                          # placeholder
        self._current_steps = 0
        self._current_episodes = 0

    def reset(self, env_indices=None, get_obs=True, **kwargs):
        # Upstream resets the task and the counters (env_base.py:849-854).  # placeholder episode/step counters
        self._current_episodes += 1
        self._current_steps = 0
        self._joint_positions = list(RESET_POSITION)                          # placeholder
        if not get_obs:                                                       # env_base.py:856
            return None
        # upstream returns (obs_list, {"obs_info": info_list}) at env_base.py:903; this stand-in returns one env
        return self._observation(), {"obs_info": {}}

    def step(self, action, n_render_iterations=1):
        # The render count is ignored: this stand-in has no renderer (upstream returns None without external
        # sensors, env_base.py:809-813).  A dict action is keyed by robot name (env_base.py:724-727).
        if isinstance(action, dict):
            commanded = list(action.get("robot", ()))
        else:
            commanded = list(action)
        if len(commanded) != len(self._joint_positions):
            raise ValueError(f"expected {len(self._joint_positions)} joint commands, got {len(commanded)}")
        self._joint_positions = [float(value) for value in commanded]
        self._current_steps += 1                                              # env_base.py:806
        # DummyTask has no termination condition and no reward function, so done stays false and reward 0.
        return self._observation(), 0.0, False, False, {}                     # placeholder reward

    def close(self):
        """No-op to satisfy certain RL frameworks (env_base.py:523-525)."""
        pass

    def _observation(self):
        """The proprioception observation of the one robot (upstream gathers robot spaces, env_base.py:390-396)."""
        return {"robot": {"proprio": list(self._joint_positions)}}
