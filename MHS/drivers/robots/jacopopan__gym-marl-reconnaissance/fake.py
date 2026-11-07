"""Fake backend of the gym-marl-reconnaissance driver: a pure Python stand-in for ``ReconArena``.

Why a fake: the upstream environment imports ``gym`` and ``pybullet`` (``recon_arena.py:5-8``), neither of which is
installed where the gate runs, and package code never imports the clone.  This module re-implements the observable
contract of ``gym_marl_reconnaissance.envs.recon_arena:ReconArena`` in plain Python: the default task-assignment
world of one Tello, one RoboMaster, two adversaries and one neutral agent, its ``MultiDiscrete`` action space, the
global observation layout, the reward functions and the episode-length rule.  The public members are the ones
``ReconArena`` has (``reset``, ``step``, ``close``; gate G7), and the two space classes duck-type the ``gym.spaces``
objects the bridge reads (``nvec``, ``start``, ``low``, ``high``, ``shape``).

What this is not: the upstream environment.  It replaces the PyBullet rigid-body simulation with direct kinematic
motion at the speeds the upstream code sets, so it has no contacts, no URDF collision meshes, no gravity or lift
force, no ray-cast visibility and no rendering; it also draws from Python's ``random.Random`` where upstream uses
numpy's global generator.  All of that is listed in the driver's fidelity ``gaps`` and in facts.md.  Every number
below is placeholder test data, not a fact and not a bound of a device.

Nothing here talks to a device.
"""

import math
import random

# Placeholder test data: the default setup and the upstream behaviour constants, copied here only to make a
# deterministic stand-in world.  They are not facts, not limits, and the reference files do not derive from them.
EDGE = 10.0                     # placeholder: default setup edge
NUM_OBSTACLES = 0               # placeholder: default setup obstacles
NUM_TT = 1                      # placeholder: default setup tellos
NUM_S1 = 1                      # placeholder: default setup robomasters
NUM_ADVERSARY = 2               # placeholder: default setup adversaries
NUM_NEUTRAL = 1                 # placeholder: default setup neutrals
CTRL_FREQ = 5                   # placeholder: default control frequency
PYB_FREQ = 60                   # placeholder: default PyBullet frequency
EPISODE_LENGTH_SEC = 30         # placeholder: default episode length
VISIBILITY_THRESHOLD = 8.0      # placeholder: default visibility range
TASK_ASSIGN_SPEED = 2.0         # placeholder: velocity towards the assigned task
S1_SPEED_CORRECTION = 1.5       # placeholder: RoboMaster speed correction
TRACKING_SPEED = 1.2            # placeholder: tracking velocity scale
AVOID_DISTANCE = 3.0            # placeholder: avoidant adversary flee range
AVOID_SPEED = 2.25              # placeholder: avoidant adversary flee scale
PATROL_LOW, PATROL_HIGH = 0.5, 1.5   # placeholder: patrol speed range
FLIP_PROBABILITY = 0.05         # placeholder: patrol direction flip probability
REWARD_RADIUS = 1.5             # placeholder: distance that counts as a catch
TT_Z = 1.5                      # placeholder: Tello start altitude
S1_Z = 0.5                      # placeholder: ground robot start altitude
OBSTACLE_Z = 0.0                # placeholder: obstacle start altitude
GRAVITY_ACC = 9.8               # placeholder: gravity constant
TT_MASS = 0.08                  # placeholder: Tello mass
RENDER_WIDTH = 640              # placeholder: upstream render width
RENDER_HEIGHT = 480             # placeholder: upstream render height


class MultiDiscrete:
    """Duck-typed ``gym.spaces.MultiDiscrete``: one integer range per agent (``nvec``)."""

    def __init__(self, nvec):
        self.nvec = [int(value) for value in nvec]
        self.shape = (len(self.nvec),)
        self.dtype = "int64"

    def contains(self, value):
        try:
            items = list(value)
        except TypeError:
            return False
        return (len(items) == len(self.nvec)
                and all(isinstance(item, int) and not isinstance(item, bool) and 0 <= item < size
                        for item, size in zip(items, self.nvec)))


class Box:
    """Duck-typed one-dimensional ``gym.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high, dtype="float32"):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = dtype


class FakeReconArena:
    """``ReconArena`` without gym or PyBullet: ``reset``, ``step`` and ``close`` mirror the upstream class."""

    def __init__(self, seed=-1, ctrl_freq=CTRL_FREQ, pyb_freq=PYB_FREQ, gui=False, record=False,
                 episode_length_sec=EPISODE_LENGTH_SEC, action_type="task_assignment", obs_type="global",
                 reward_choice="reward_a", adv_type="avoidant", visibility_threshold=VISIBILITY_THRESHOLD,
                 setup=None, debug=False):
        if seed == -1:
            self._rng = random.Random()
        else:
            self._rng = random.Random(int(seed))
        self.CTRL_FREQ = int(ctrl_freq)
        self.PYB_FREQ = int(pyb_freq)
        if self.PYB_FREQ % self.CTRL_FREQ != 0 or self.PYB_FREQ < self.CTRL_FREQ:
            raise ValueError("[ERROR] in ReconArena.__init__(), pyb_freq is not divisible by ctrl_freq.")
        self._PYB_UPDATES_PER_STEP = int(self.PYB_FREQ / self.CTRL_FREQ)
        self._CTRL_TIMESTEP = 1.0 / self.CTRL_FREQ
        self._PYB_TIMESTEP = 1.0 / self.PYB_FREQ
        self.EPISODE_LENGTH_SEC = episode_length_sec
        self._GRAVITY_ACC = GRAVITY_ACC
        self._TT_MASS = TT_MASS
        self._VEL_SCALE = 1
        self._VISIBILITY_THRESHOLD = visibility_threshold
        self._ACTION_TYPE = str(action_type)
        self._OBS_TYPE = str(obs_type)
        self._REWARD_CHOICE = str(reward_choice)
        self._ADV_TYPE = str(adv_type)
        if setup is None:
            setup = {"edge": EDGE, "obstacles": NUM_OBSTACLES, "tt": NUM_TT, "s1": NUM_S1,
                     "adv": NUM_ADVERSARY, "neu": NUM_NEUTRAL}
        self._ARENA_EDGE = setup["edge"]
        self._NUM_OBSTACLES = setup["obstacles"]
        self._NUM_TT = setup["tt"]
        self._NUM_S1 = setup["s1"]
        self._NUM_ADVERSARY = setup["adv"]
        self._NUM_NEUTRAL = setup["neu"]
        if self._ACTION_TYPE == "task_assignment":
            self._NUM_OBSTACLES = 0
            self._VISIBILITY_THRESHOLD = math.inf
        self._GUI = gui
        self._RECORD = record
        self._RENDER_WIDTH = RENDER_WIDTH
        self._RENDER_HEIGHT = RENDER_HEIGHT
        self.PYB_CLIENT = -1
        self._DEBUG = debug
        self._initial_reset = False
        self.action_space = self._set_action_space()
        self.observation_space = self._set_observation_space()
        self.state = {}
        self._agents = []
        self._learners = []
        self._targets = []
        self._ctrl_step_counter = 0
        self._pyb_step_counter = 0

    # -- spaces ---------------------------------------------------------------
    def _set_action_space(self):
        num_agents = self._NUM_TT + self._NUM_S1
        if self._ACTION_TYPE == "task_assignment":
            num_options = self._NUM_ADVERSARY + self._NUM_NEUTRAL   # As many as the assignable tasks.
            return MultiDiscrete([num_options] * num_agents)
        if self._ACTION_TYPE == "tracking":
            return MultiDiscrete([5] * num_agents)                  # Stay, forward, backward, left, right.
        raise ValueError("[ERROR] invalid action type.")

    def _set_observation_space(self):
        if self._OBS_TYPE == "global":
            obs_size = 5 * (self._NUM_TT + self._NUM_S1 + self._NUM_ADVERSARY + self._NUM_NEUTRAL
                            + self._NUM_OBSTACLES)
            return Box([-math.inf] * obs_size, [math.inf] * obs_size)
        raise ValueError("[ERROR] the fake implements obs_type 'global' only.")

    # -- gym API --------------------------------------------------------------
    def reset(self, *, seed=None, options=None):
        """Reset the world and return the initial observation (upstream returns the observation only)."""
        if options:
            raise ValueError("[ERROR] the fake ReconArena accepts no reset options")
        if seed is not None:
            self._rng = random.Random(int(seed))
        self._initial_reset = True
        self._pyb_step_counter = 0
        self._ctrl_step_counter = 0
        self._create_agents()
        self._update_env_state()
        return self._compute_obs()

    def step(self, action):
        """Advance one control step and return ``(observation, reward, done, {})`` like the upstream four-tuple."""
        if not self._initial_reset:
            raise RuntimeError("[ERROR] You must call ReconArena.reset() at least once before using "
                               "ReconArena.step().")
        self._apply_action(action)
        self._nonstationary_adversary()
        self._nonstationary_neutral()
        self._pyb_step_counter += self._PYB_UPDATES_PER_STEP
        self._update_env_state()
        observation = self._compute_obs()
        reward = self._compute_reward()
        done = self._compute_done()
        self._ctrl_step_counter += 1
        return observation, reward, done, {}

    def close(self):
        """Close the environment (the fake has no PyBullet client to disconnect)."""
        self.PYB_CLIENT = -1

    # -- world ----------------------------------------------------------------
    def _create_agents(self):
        self._agents = []
        next_id = 1                                                  # placeholder: pybullet body ids start at 1
        for index in range(self._NUM_OBSTACLES):
            self._agents.append({
                "key": "obst_%d" % index, "kind": "obstacle", "id": next_id, "class": 5,
                "pos": [self._rng.uniform(self._ARENA_EDGE / 3, 2 * self._ARENA_EDGE / 3),
                        self._rng.uniform(self._ARENA_EDGE / 3, 2 * self._ARENA_EDGE / 3), OBSTACLE_Z],
            })
            next_id += 1
        for index in range(self._NUM_TT):
            self._agents.append({
                "key": "tt_%d" % index, "kind": "tt", "id": next_id, "class": 1,
                "pos": [self._rng.uniform(0, self._ARENA_EDGE / 3),
                        self._rng.uniform(0, self._ARENA_EDGE / 3), TT_Z],
            })
            next_id += 1
        for index in range(self._NUM_S1):
            self._agents.append({
                "key": "s1_%d" % index, "kind": "s1", "id": next_id, "class": 2,
                "pos": [self._rng.uniform(0, self._ARENA_EDGE / 3),
                        self._rng.uniform(0, self._ARENA_EDGE / 3), S1_Z],
            })
            next_id += 1
        for index in range(self._NUM_ADVERSARY):
            self._agents.append({
                "key": "adv_%d" % index, "kind": "adv", "id": next_id, "class": 3,
                "pos": [self._rng.uniform(2 * self._ARENA_EDGE / 3, self._ARENA_EDGE),
                        self._rng.uniform(2 * self._ARENA_EDGE / 3, self._ARENA_EDGE), S1_Z],
                "direction": 1, "speed": self._rng.uniform(PATROL_LOW, PATROL_HIGH),
            })
            next_id += 1
        for index in range(self._NUM_NEUTRAL):
            self._agents.append({
                "key": "neu_%d" % index, "kind": "neu", "id": next_id, "class": 4,
                "pos": [self._rng.uniform(2 * self._ARENA_EDGE / 3, self._ARENA_EDGE),
                        self._rng.uniform(2 * self._ARENA_EDGE / 3, self._ARENA_EDGE), S1_Z],
                "direction": 1, "speed": self._rng.uniform(PATROL_LOW, PATROL_HIGH),
            })
            next_id += 1
        self._learners = [agent for agent in self._agents if agent["kind"] in ("tt", "s1")]
        self._targets = [agent for agent in self._agents if agent["kind"] in ("adv", "neu")]

    def _move(self, agent, vx, vy):
        agent["pos"][0] += vx * self._CTRL_TIMESTEP
        agent["pos"][1] += vy * self._CTRL_TIMESTEP

    def _apply_action(self, action):
        try:
            values = list(action)
        except TypeError as exc:
            raise ValueError("[ERROR] the action must be a sequence of integers") from exc
        if len(values) != len(self._learners):
            raise ValueError("[ERROR] the action has %d values for %d learning agents"
                             % (len(values), len(self._learners)))
        if self._ACTION_TYPE == "task_assignment":
            for index, value in enumerate(values):
                if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value < len(self._targets):
                    raise ValueError("[ERROR] invalid task index %r" % (value,))
                agent = self._learners[index]
                target = self._targets[value]
                dx = target["pos"][0] - agent["pos"][0]
                dy = target["pos"][1] - agent["pos"][1]
                norm = math.hypot(dx, dy)
                if norm == 0:
                    continue
                speed = TASK_ASSIGN_SPEED * self._VEL_SCALE
                if agent["kind"] == "s1":
                    speed *= S1_SPEED_CORRECTION
                self._move(agent, speed * dx / norm, speed * dy / norm)
            return
        if self._ACTION_TYPE == "tracking":
            vectors = {0: (0, 0), 1: (1, 1), 2: (-1, -1), 3: (-1, 1), 4: (1, -1)}
            for index, value in enumerate(values):
                if not isinstance(value, int) or isinstance(value, bool) or value not in vectors:
                    raise ValueError("[ERROR] invalid tracking index %r" % (value,))
                vx, vy = vectors[value]
                self._move(self._learners[index], TRACKING_SPEED * self._VEL_SCALE * vx,
                           TRACKING_SPEED * self._VEL_SCALE * vy)
            return
        raise ValueError("[ERROR] invalid action type.")

    def _nearest_learner(self, agent):
        best = None
        best_distance = math.inf
        for learner in self._learners:
            distance = math.hypot(learner["pos"][0] - agent["pos"][0],
                                  learner["pos"][1] - agent["pos"][1])
            if distance < best_distance:
                best, best_distance = learner, distance
        return best, best_distance

    def _patrol(self, agent):
        if self._rng.random() < FLIP_PROBABILITY:
            agent["direction"] = -agent["direction"]
        self._move(agent, agent["direction"] * agent["speed"], -agent["direction"] * agent["speed"])

    def _nonstationary_adversary(self):
        if self._ADV_TYPE == "blind":
            for agent in self._agents:
                if agent["kind"] == "adv":
                    self._patrol(agent)
            return
        if self._ADV_TYPE == "avoidant":
            for agent in self._agents:
                if agent["kind"] != "adv":
                    continue
                nearest, distance = self._nearest_learner(agent)
                if nearest is not None and 0 < distance < AVOID_DISTANCE:
                    dx = nearest["pos"][0] - agent["pos"][0]
                    dy = nearest["pos"][1] - agent["pos"][1]
                    speed = -AVOID_SPEED * agent["speed"] * self._VEL_SCALE
                    self._move(agent, speed * dx / distance, speed * dy / distance)
                else:
                    self._patrol(agent)
            return
        raise ValueError("[ERROR] invalid adversary type type.")

    def _nonstationary_neutral(self):
        for agent in self._agents:
            if agent["kind"] == "neu":
                self._patrol(agent)

    # -- state, observation, reward and termination ---------------------------
    def _visible(self, agent):
        nearest, distance = self._nearest_learner(agent)
        if nearest is None:
            return False
        return distance < self._VISIBILITY_THRESHOLD

    def _update_env_state(self):
        self.state = {}
        for agent in self._agents:
            entry = {"id": agent["id"], "class": agent["class"], "pos": list(agent["pos"]),
                     "quat": [0.0, 0.0, 0.0, 1.0], "rpy": [0.0, 0.0, 0.0], "vel": [0.0, 0.0, 0.0]}
            if agent["kind"] in ("adv", "neu"):
                entry["visibility"] = self._visible(agent)
            self.state[agent["key"]] = entry

    def _append_agent(self, observation, key):
        entry = self.state[key]
        if entry.get("visibility", True):
            observation.extend([entry["id"], entry["class"]] + list(entry["pos"]))
        else:
            observation.extend([0, 0, 0, 0, 0])

    def _compute_obs(self):
        observation = []
        for index in range(self._NUM_TT):
            self._append_agent(observation, "tt_%d" % index)
        for index in range(self._NUM_S1):
            self._append_agent(observation, "s1_%d" % index)
        for index in range(self._NUM_ADVERSARY):
            self._append_agent(observation, "adv_%d" % index)
        for index in range(self._NUM_NEUTRAL):
            self._append_agent(observation, "neu_%d" % index)
        for index in range(self._NUM_OBSTACLES):
            entry = self.state["obst_%d" % index]
            observation.extend([entry["id"], entry["class"]] + list(entry["pos"]))
        return [float(value) for value in observation]

    def _compute_reward(self):
        adversaries = [agent for agent in self._agents if agent["kind"] == "adv"]
        if not adversaries or not self._learners:
            return 0.0
        distances = [self._nearest_learner(agent)[1] for agent in adversaries]
        if self._REWARD_CHOICE == "reward_a":
            return float(sum(1 for distance in distances if distance < REWARD_RADIUS))
        if self._REWARD_CHOICE == "reward_b":
            return float(sum(1.0 / (distance + 0.01) for distance in distances))
        if self._REWARD_CHOICE == "reward_c":
            reward = sum(1.0 / (distance ** 2 + 0.01) for distance in distances)
            for learner in self._learners:
                nearest = min(math.hypot(learner["pos"][0] - agent["pos"][0],
                                         learner["pos"][1] - agent["pos"][1]) for agent in adversaries)
                reward += 0.25 / (nearest ** 2 + 0.01)
            return float(reward)
        raise ValueError("[ERROR] invalid reward choice.")

    def _compute_done(self):
        return (self._ctrl_step_counter + 1) / self.CTRL_FREQ >= self.EPISODE_LENGTH_SEC
