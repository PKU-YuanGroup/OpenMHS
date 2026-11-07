"""Fake backend of the MolmoSpaces driver: an analytic stand-in for ``GymEnv`` without MuJoCo.

Why a fake: package code never imports the clone (the upstream needs Python 3.11 or newer, gymnasium, numpy and
torch), and the gate serves only the package's own backend.  This class implements the public methods of
``molmo_spaces.tasks.gym_env:GymEnv`` that the bridge uses: ``reset(seed, options)``, ``step(action)`` and
``close()``.  It reproduces the wrapper's episode lifecycle, not the simulator:

* ``reset`` validates the same two options (``house_index`` and ``force_advance_scene``, gym_env.py:44-45),
  seeds its sampler, samples a fresh qpos and returns ``(observation, info)`` with an observation that is a
  ``list[dict]`` of one batch element;
* ``step`` accepts a dict keyed by move group (gym_env.py:74-76), applies the arm and gripper joint positions it
  knows, and returns the task's five-tuple with the task horizon of the selected config (base_pick_config.py:42);
* ``close`` drops the current task.

What this is not: the MuJoCo simulation.  There is no physics, no contact, no object, no controller, no camera and
no reward.  The observation is reduced to the qpos sensor (arm 7 joints and gripper 2 joints, robot_configs.py:
150-153) while upstream returns many more sensors.  The fake's numbers are test data, each marked ``# placeholder``;
they are not facts, limits or a reference for the device.

Nothing here talks to a device.
"""

import random

# placeholder: the Franka start pose is used as the centre of the fake's sample (robot_configs.py:150-153)
ARM_QPOS = [0.0, -0.7853, 0.0, -2.35619, 0.0, 1.57079, 0.0]
GRIPPER_QPOS = [0.00296, 0.00296]
ARM_JOINTS = 7                       # placeholder: the length of ARM_QPOS
GRIPPER_JOINTS = 2                   # placeholder: the length of GRIPPER_QPOS
CONTROL_DT_MS = 2.0                  # placeholder: PickBaseConfig ctrl_dt_ms (base_pick_config.py:39)
TASK_HORIZON = 500                   # placeholder: PickBaseConfig task_horizon (base_pick_config.py:42)
JOINT_NOISE = 0.01                   # placeholder: the fake's reset jitter in radians
HOUSE_COUNT = 8                      # placeholder: the fake's number of scenes


class _FakeTaskSampler:
    """The part of a task sampler the fake models: seed control, house selection and close."""

    def __init__(self):
        self.current_seed = None     # placeholder
        self.house_index = 0         # placeholder
        self._rng = random.Random()
        self.closed = False

    def seed_task_sampling(self, seed):
        """Mirror ``BaseMujocoTaskSampler.seed_task_sampling`` (task_sampler.py:428-431), own RNG only."""
        self.current_seed = int(seed)
        self._rng = random.Random(int(seed))

    def close(self):
        self.closed = True


class _FakeTask:
    """A marker for the current episode; ``GymEnv`` exposes it as ``env.task``."""

    def __init__(self, house_index):
        self.house_index = house_index

    def close(self):
        return None


class FakeGymEnv:
    """A pure Python stand-in for ``GymEnv`` with the same public methods the bridge calls."""

    metadata = {"render_modes": ["rgb_array"]}   # the class attribute of GymEnv (gym_env.py:62)

    def __init__(self, **options):
        # The options the bridge may forward are ignored: this fake needs no renderer or device.
        self.task = None
        self.task_sampler = _FakeTaskSampler()
        self.render_mode = options.get("render_mode")
        self.render_camera = options.get("render_camera")
        self._owns_task_sampler = True
        self._episode = 0            # placeholder
        self._tick = 0               # placeholder
        self._seed = None
        self._qpos = {"arm": list(ARM_QPOS), "gripper": list(GRIPPER_QPOS)}
        self._closed = False

    def _observation(self):
        """One batch element whose observation dict has the upstream qpos key."""
        return [{"qpos": {"arm": list(self._qpos["arm"]), "gripper": list(self._qpos["gripper"])}}]

    def _info(self):
        """The task info shape of task.py:463-472, one entry per batch element."""
        return [{"cumulative_reward": 0.0, "num_steps_taken": self._tick}]   # placeholder

    def reset(self, *, seed=None, options=None):
        """Sample a new episode; the bridge calls this with keyword arguments (gym_env.py:134-140)."""
        if seed is not None:
            if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
                raise ValueError("seed must be a non-negative integer")
            self._seed = seed
            self.task_sampler.seed_task_sampling(seed)
        options = dict(options or {})
        unknown = set(options) - {"house_index", "force_advance_scene"}
        if unknown:
            raise ValueError(f"Unsupported reset options {sorted(unknown)}; supported: "
                             "['house_index', 'force_advance_scene'].")
        if options.get("house_index") is not None:
            self.task_sampler.house_index = int(options["house_index"]) % HOUSE_COUNT
        elif options.get("force_advance_scene"):
            self.task_sampler.house_index = (self.task_sampler.house_index + 1) % HOUSE_COUNT
        if self.task is not None:
            self.task.close()
        self.task = _FakeTask(self.task_sampler.house_index)
        rng = self.task_sampler._rng
        # placeholder: the sampled start pose is test data, not a device bound
        self._qpos = {
            "arm": [value + rng.uniform(-JOINT_NOISE, JOINT_NOISE) for value in ARM_QPOS],
            "gripper": [value + rng.uniform(-JOINT_NOISE, JOINT_NOISE) for value in GRIPPER_QPOS],
        }
        self._tick = 0
        self._episode += 1
        return self._observation(), self._info()

    def step(self, action):
        """Advance one control step with a move-group action dict (gym_env.py:181-184)."""
        if self.task is None:
            raise RuntimeError("Call FakeGymEnv.reset() before step().")
        if not isinstance(action, dict):
            raise TypeError("action must be a dict keyed by move group")
        arm = action.get("arm")
        if arm is not None:
            values = [float(value) for value in arm]
            if len(values) != ARM_JOINTS:
                raise ValueError(f"arm action has {len(values)} joints; expected {ARM_JOINTS}")
            self._qpos["arm"] = values
        gripper = action.get("gripper")
        if gripper is not None:
            values = [float(value) for value in gripper]
            if len(values) != GRIPPER_JOINTS:
                raise ValueError(f"gripper action has {len(values)} joints; expected {GRIPPER_JOINTS}")
            self._qpos["gripper"] = values
        self._tick += 1
        self.task.house_index = self.task_sampler.house_index
        reward = 0.0                                         # placeholder: the fake models no lift
        terminated = False                                   # placeholder: no success test is modelled
        truncated = self._tick >= TASK_HORIZON
        return self._observation(), reward, terminated, truncated, self._info()

    def close(self):
        """Close the current task; the sampler is owned by this env, as in gym_env.py:199-205."""
        if self.task is not None:
            self.task.close()
            self.task = None
        if self._owns_task_sampler:
            self.task_sampler.close()
        self._closed = True
