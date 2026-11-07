"""OpenMHS driver for gh.hewlettpackard/sustain-cluster: the TaskSchedulingEnv Gymnasium environment.

SustainCluster is a benchmark and Gymnasium-compatible simulation of a geo-distributed datacenter cluster; the
environment RL agents interact with is ``envs.task_scheduling_env:TaskSchedulingEnv``.  A GymnasiumDriver is
configuration only: ``cap.world.step.v1`` takes ``{ticks, action}`` with the action ``{index}`` bounded by the
environment's ``Discrete`` action space, ``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1``
``{seed}``.  The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no
operator-required limit.

The environment has no ``gymnasium.register`` entry and its constructor needs a DatacenterClusterManager, a start and
end time and a reward function (``envs/task_scheduling_env.py:28-30``).  There is therefore no ``env_id`` to hand to
``gymnasium.make``: the only backend is the package's own pure Python fake (``fake.py``), which is a fixed
five-datacenter test configuration.  The upstream package needs pandas, numpy, torch and the workload dataset, was not
installed and was never run here.  This package is model-authored and unreviewed: it is checked on the fake backend
only.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002):
every member of ``device.schema.json`` that applies to this analytic simulator.  Every constant and rule cites a line
of the clone at the pinned commit (3f6ea95cb835b89ba50b0ef76d66d14b8037643e).
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "envs/task_scheduling_env.py"
SIM_CONFIG = "configs/env/sim_config.yaml"


class SustainClusterTaskSchedulingEnv(GymnasiumDriver):
    device_id = "sustain-cluster"
    # No gymnasium registration exists upstream: the environment is built from a cluster manager and a reward
    # function, so the package's fake supplies the environment object on the fake backend.
    env_id = None
    native = "envs.task_scheduling_env:TaskSchedulingEnv"
    backends = {"fake": ".fake:FakeTaskSchedulingEnv"}
    display_name = "SustainCluster TaskSchedulingEnv (geo-distributed datacenter scheduling benchmark)"
    vendor, model = "Hewlett Packard Enterprise", "SustainCluster"
    tags = ["sustain-cluster", "datacenter", "scheduling", "energy", "carbon",
            "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("TaskSchedulingEnv subclasses gymnasium.Env: it is the Gymnasium interface of the benchmark",
             source="upstream_code", ref=f"{ENV}:18"),
        Fact("The number of datacenters is read from the cluster manager (self.num_dcs = len(...))",
             source="upstream_code", ref=f"{ENV}:51"),
        Fact("One simulation step advances the clock by 15 minutes (pd.Timedelta(minutes=15))",
             source="upstream_code", ref=f"{ENV}:37"),
        Fact("In single-action mode with deferral disabled, the action space is Discrete(num_dcs)",
             source="upstream_code", ref=f"{ENV}:90-92"),
        Fact("With deferral disabled, an agent action 0..N-1 is shifted by one and assigned to datacenter 1..N",
             source="upstream_code", ref=f"{ENV}:280-282"),
        Fact("The aggregated observation dimension is 4 time features + 5 aggregated task features + 5 features "
             "per datacenter", source="upstream_code", ref=f"{ENV}:81-86"),
        Fact("The time features are the sine and cosine of the day of year and of the hour of day",
             source="upstream_code", ref=f"{ENV}:188-195"),
        Fact("The per-task features are origin datacenter id, cores, GPUs, duration and minutes to the SLA deadline",
             source="upstream_code", ref=f"{ENV}:209-220"),
        Fact("The datacenter features are available/total cores, GPUs and memory, carbon intensity/1000 and "
             "price/100", source="upstream_code", ref=f"{ENV}:197-207"),
        Fact("reset(seed) increments the episode count, seeds Python's random generator and the cluster manager, "
             "and returns (observation, info)", source="upstream_code", ref=f"{ENV}:226-252"),
        Fact("step returns (observation, reward, terminated, truncated, info) after advancing the clock and "
             "loading the next tasks", source="upstream_code", ref=f"{ENV}:370-386"),
        Fact("An episode is done and truncated when current_time reaches end_time",
             source="upstream_code", ref=f"{ENV}:375-376"),
        Fact("The reward is 0.0 when the environment is constructed without a reward function",
             source="upstream_code", ref=f"{ENV}:360-362"),
        Fact("The shipped simulation config enables single_action_mode and disable_defer_action",
             source="upstream_code", ref=f"{SIM_CONFIG}:16-17"),
        Fact("The README documents a Gymnasium-compatible environment interface for RL agents",
             source="vendor_doc", ref="README.md:124"),
        Fact("The README documents the simulation timestep as 15 minutes",
             source="vendor_doc", ref="README.md:194"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "sustain-cluster:TaskSchedulingEnv",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) reseeds the environment's task generator (envs/task_scheduling_env.py:239-241) "
                     "and the fake repeats a trajectory for the same seed and actions; the upstream also seeds its "
                     "cluster manager, and the fake was never compared with the upstream environment",
        },
        # envs/task_scheduling_env.py:37: one step advances the clock by 15 minutes.
        "timestep_ms": 900000.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic/analytic model (F0): the environment advances a scheduler clock and state transitions, not "
            "rigid-body dynamics, contacts, actuators or sensors",
            "the fake backend models one fixed five-datacenter test configuration and generates placeholder tasks; "
            "it does not run DatacenterClusterManager, SustainDC, the workload trace, the reward engine or the "
            "energy, carbon and thermal models",
            "upstream needs pandas, numpy, torch and the Alibaba workload dataset; nothing was installed or run, so "
            "the fake was never compared with the upstream environment",
            "no rendering, no snapshot and no restore: the environment exposes no get_state/set_state",
            "wall-clock time is not paced: realtime_factor 0, and simulated time advances 15 minutes per step",
        ],
    }
