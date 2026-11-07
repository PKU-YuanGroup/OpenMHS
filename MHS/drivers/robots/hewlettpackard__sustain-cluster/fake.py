"""Fake backend for the SustainCluster Gymnasium driver (pure Python, no upstream import).

The driver names ``envs.task_scheduling_env:TaskSchedulingEnv`` as its native class.  This module re-implements the
public Gymnasium surface the bridge uses -- ``reset``, ``step``, ``action_space`` and ``observation_space`` -- for
one fixed test configuration, without pandas, numpy, torch, the workload trace or the datacenter physics.

The shipped ``configs/env/sim_config.yaml`` selects ``single_action_mode: true`` and ``disable_defer_action: true``
(lines 16-17), so the action space is ``Discrete(num_dcs)`` (``envs/task_scheduling_env.py:90-92``) and an agent
action ``0..N-1`` maps to datacenters ``1..N`` (``envs/task_scheduling_env.py:280-282``).  The observation is the
aggregated vector of ``envs/task_scheduling_env.py:81-86`` and ``:119-168``: four time features, five aggregated task
features and five datacenter features per datacenter.  ``reset`` reseeds Python's generator and returns
``(observation, info)`` (``envs/task_scheduling_env.py:226-252``); ``step`` advances 15 minutes
(``envs/task_scheduling_env.py:37``) and returns the five-tuple of ``envs/task_scheduling_env.py:372-386``.

Every literal below that the upstream does not state is test data and is marked ``# placeholder``.  The fake has never
been compared with the upstream environment, which needs pandas, numpy, torch and the workload dataset; the gate
imports neither.  Nothing here talks to a device.
"""

import datetime
import math
import random

# envs/task_scheduling_env.py:37: each step advances the clock by 15 minutes.
TIME_STEP = datetime.timedelta(minutes=15)
# envs/task_scheduling_env.py:79 and :86: 4 time features + 5 task features + 5 features per datacenter.
NUM_DC = 5  # placeholder: the fake models one fixed five-datacenter test configuration
OBS_DIM = 4 + 5 + (5 * NUM_DC)
# placeholder: start time and episode length of the fake's fixed test scenario
START_TIME = datetime.datetime(2023, 8, 1, 5, 0, tzinfo=datetime.timezone.utc)
EPISODE_LENGTH = datetime.timedelta(days=7)


class Discrete:
    """Duck-typed ``gymnasium.spaces.Discrete``: the integers ``start .. start + n - 1``."""

    def __init__(self, n, start=0):
        self.n = int(n)
        self.start = int(start)
        self.shape = ()
        self.dtype = "int64"

    def contains(self, value):
        return isinstance(value, int) and not isinstance(value, bool) and self.start <= value < self.start + self.n


class Box:
    """Duck-typed one-dimensional ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeTaskSchedulingEnv:
    """A small TaskSchedulingEnv stand-in: ``reset(seed, options)`` and ``step(actions)`` return what it returns."""

    def __init__(self):
        self.num_dcs = NUM_DC
        self.single_action_mode = True
        self.disable_defer_action = True
        # envs/task_scheduling_env.py:87-89 and :91: a fixed-size Box and Discrete(num_dcs) in this mode.
        self.observation_space = Box([-math.inf] * OBS_DIM, [math.inf] * OBS_DIM)
        self.action_space = Discrete(self.num_dcs)
        self.start_time = START_TIME
        self.end_time = START_TIME + EPISODE_LENGTH
        self.current_time = self.start_time
        self.base_seed = 0  # placeholder: the upstream draws a random base seed at line 53
        self.current_episode_count = 0
        self.current_tasks = []
        self.deferred_tasks = []
        self.in_transit_tasks = []
        self.last_assigned_dc = None
        self._seed = None
        self._rng = random.Random(self.base_seed)
        self.datacenters = [self._new_datacenter(index) for index in range(self.num_dcs)]

    def _new_datacenter(self, index):
        """One datacenter with placeholder resource and price state (the real one is a SustainDC object)."""
        total_cores = 1000.0 * (index + 1)  # placeholder
        total_gpus = 10.0 * (index + 1)  # placeholder
        total_mem = 2000.0 * (index + 1)  # placeholder
        return {
            "total_cores": total_cores,
            "available_cores": total_cores,
            "total_gpus": total_gpus,
            "available_gpus": total_gpus,
            "total_mem_GB": total_mem,
            "available_mem": total_mem,
            "ci": 100.0 + (10.0 * index),  # placeholder: carbon intensity used by the observation
            "price": 50.0 + (5.0 * index),  # placeholder: energy price used by the observation
        }

    def _new_task(self):
        """One placeholder task with the fields the upstream observation reads."""
        return {
            "origin_dc_id": self._rng.randint(1, self.num_dcs),  # placeholder
            "cores_req": self._rng.choice([1.0, 2.0, 4.0]),  # placeholder
            "gpu_req": self._rng.choice([0.0, 1.0, 2.0]),  # placeholder
            "duration": self._rng.choice([30.0, 60.0, 120.0]),  # placeholder: minutes
            "sla_deadline": self.current_time + datetime.timedelta(minutes=self._rng.choice([60, 120, 240])),  # placeholder
        }

    def reset(self, seed=None, options=None):
        """Reseed and restart the episode; ``options`` is accepted and ignored, as upstream does (line 250)."""
        if seed is not None:
            current_seed = int(seed)
        else:
            current_seed = self.base_seed + self.current_episode_count
        self.current_episode_count += 1
        self._seed = current_seed
        self._rng = random.Random(current_seed)
        self.current_time = self.start_time
        self.deferred_tasks = []
        self.in_transit_tasks = []
        self.last_assigned_dc = None
        self.datacenters = [self._new_datacenter(index) for index in range(self.num_dcs)]
        self.current_tasks = [self._new_task()]
        return self._get_obs(), {}

    def _time_features(self):
        """The four sine/cosine time features of envs/task_scheduling_env.py:188-195."""
        day_of_year = self.current_time.timetuple().tm_yday
        hour_of_day = self.current_time.hour + self.current_time.minute / 60.0
        return [
            math.sin(2 * math.pi * day_of_year / 365.0),
            math.cos(2 * math.pi * day_of_year / 365.0),
            math.sin(2 * math.pi * hour_of_day / 24.0),
            math.cos(2 * math.pi * hour_of_day / 24.0),
        ]

    def _aggregated_task_features(self):
        """The five aggregated task features of envs/task_scheduling_env.py:131-151."""
        tasks = self.current_tasks
        num_tasks = float(len(tasks))
        if num_tasks > 0:
            avg_cores = sum(task["cores_req"] for task in tasks) / num_tasks
            avg_gpus = sum(task["gpu_req"] for task in tasks) / num_tasks
            avg_duration = sum(task["duration"] for task in tasks) / num_tasks
            min_deadline = min(
                max(0.0, (task["sla_deadline"] - self.current_time).total_seconds() / 60.0) for task in tasks
            )
        else:
            avg_cores = avg_gpus = avg_duration = min_deadline = 0.0
        return [num_tasks, avg_cores, avg_gpus, avg_duration, min_deadline]

    def _get_obs(self):
        """The aggregated observation vector (envs/task_scheduling_env.py:81-86, :119-168, :188-220)."""
        values = self._time_features()
        values += self._aggregated_task_features()
        for datacenter in self.datacenters:
            # envs/task_scheduling_env.py:200-206
            values.append(datacenter["available_cores"] / datacenter["total_cores"]
                          if datacenter["total_cores"] > 0 else 0.0)
            values.append(datacenter["available_gpus"] / datacenter["total_gpus"]
                          if datacenter["total_gpus"] > 0 else 0.0)
            values.append(datacenter["available_mem"] / datacenter["total_mem_GB"]
                          if datacenter["total_mem_GB"] > 0 else 0.0)
            values.append(datacenter["ci"] / 1000.0)
            values.append(datacenter["price"] / 100.0)
        return [float(value) for value in values]

    def step(self, actions):
        """Apply one action to every pending task, advance 15 minutes and return the five-tuple of line 386."""
        if isinstance(actions, bool) or not isinstance(actions, int) or not 0 <= actions < self.num_dcs:
            raise ValueError(f"action {actions!r} is outside Discrete({self.num_dcs})")
        processed = 0
        if self.current_tasks:
            processed = len(self.current_tasks)
            datacenter = self.datacenters[actions]
            for task in self.current_tasks:
                datacenter["available_cores"] = max(0.0, datacenter["available_cores"] - task["cores_req"])
                datacenter["available_gpus"] = max(0.0, datacenter["available_gpus"] - task["gpu_req"])
                datacenter["available_mem"] = max(0.0, datacenter["available_mem"] - task["cores_req"])
            # envs/task_scheduling_env.py:280-282: action 0..N-1 maps to datacenter 1..N when deferral is disabled.
            self.last_assigned_dc = actions + 1
        self.current_time += TIME_STEP  # envs/task_scheduling_env.py:372
        self.current_tasks = [self._new_task()]  # envs/task_scheduling_env.py:373
        done = self.current_time >= self.end_time  # envs/task_scheduling_env.py:375-376
        reward = 0.0  # envs/task_scheduling_env.py:360-362: no reward function is constructed here
        info = {
            "total_energy_kwh": 0.0,  # placeholder
            "total_emissions_kg": 0.0,  # placeholder
            "scheduled_tasks_this_step": processed,
            "datacenter_infos": [
                {"dc_id": index + 1, "available_cores": datacenter["available_cores"]}
                for index, datacenter in enumerate(self.datacenters)
            ],
            "transmission_cost_total_usd": 0.0,  # placeholder
        }
        return self._get_obs(), reward, done, done, info
