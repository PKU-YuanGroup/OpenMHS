"""OpenMHS driver for gh.hewlettpackard/sustain-cluster: the TaskSchedulingEnv Gymnasium environment.

SustainCluster is a benchmark and Gymnasium-compatible simulation of a geo-distributed datacenter cluster; the
environment RL agents interact with is ``envs.task_scheduling_env:TaskSchedulingEnv``.  A GymnasiumDriver is
configuration only: ``cap.world.step.v1`` takes ``{ticks, action}`` with the action ``{index}`` bounded by the
environment's ``Discrete`` action space, ``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1``
``{seed}``.  The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no
operator-required limit.

The environment has no ``gymnasium.register`` entry.  Its constructor needs a DatacenterClusterManager, a start and
end time and a reward function (``envs/task_scheduling_env.py:28-30``), and ``train_SAC_agent.make_env`` is the
upstream function that builds that object from the shipped YAML (``train_SAC_agent.py:63-95``).  The ``sim`` backend
calls the same constructors.  The only path it changes is the workload file: the YAML names a ``.pkl`` that this
commit does not contain (``.gitignore:38``), and the README ships that pickle inside the sibling ``.zip``
(``README.md:846-848``).  The loader reads an existing path with ``pd.read_pickle``
(``simulation/cluster_manager.py:358-362``), so the factory passes the absolute path of that zip, which is already
in the clone.  It does not extract the archive, rewrite a config, or write any file.  The ``fake`` backend remains
the package's pure Python stand-in (``fake.py``).  This package is model-authored and unreviewed.  The upstream
stack was not installed or run in the workspace that wrote this file.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002):
every member of ``device.schema.json`` that applies to this analytic simulator.  Every constant and rule cites a line
of the clone at the pinned commit (3f6ea95cb835b89ba50b0ef76d66d14b8037643e).
"""

from pathlib import Path

from mhs.driver import Fact, GymnasiumDriver

ENV = "envs/task_scheduling_env.py"
SIM_CONFIG = "configs/env/sim_config.yaml"
#: The pickle named by the shipped simulation config (configs/env/sim_config.yaml:9).  .gitignore:38 ignores
#: ``*.pkl``, so this commit tracks only the sibling zip the README describes (README.md:846-848).
WORKLOAD_ZIP = "data/workload/alibaba_2020_dataset/result_df_full_year_2020.zip"


def _clone_root() -> Path:
    """The pinned tree that holds the workload zip and the YAML ``make_env`` reads.

    The sim run puts that tree on ``PYTHONPATH`` (it has no setup.py).  ``envs/task_scheduling_env.py`` then
    lives one directory under the clone root, next to ``configs/`` and ``data/``.
    """
    import envs.task_scheduling_env as scheduling

    root = Path(scheduling.__file__).resolve().parents[1]
    if (root / WORKLOAD_ZIP).is_file() and (root / SIM_CONFIG).is_file():
        return root
    raise FileNotFoundError(
        f"{WORKLOAD_ZIP} is not next to the imported envs.task_scheduling_env ({scheduling.__file__})")


def _build_sim_env(**_options):
    """Build the real ``TaskSchedulingEnv`` the way ``train_SAC_agent.make_env`` does (train_SAC_agent.py:63-95).

    Two upstream paths are relative to the process working directory, so construction runs with the working
    directory set to the clone and restores it afterwards: the transmission matrix
    (``utils/transmission_cost_loader.py:16-20``) and each datacenter's ``dc_config_file``, which ``DC_Config``
    turns into an absolute path (``utils/dc_config_reader.py:20``, ``configs/env/datacenters.yaml:9``).  Carbon,
    weather and price files are opened next to ``utils/managers.py``, not from the working directory
    (``utils/managers.py:232-239``, ``:351-358``, ``:509-517``).
    """
    import datetime
    import os

    import pandas as pd

    from envs.task_scheduling_env import TaskSchedulingEnv
    from rewards.predefined.composite_reward import CompositeReward
    from simulation.cluster_manager import DatacenterClusterManager
    from utils.config_loader import load_yaml

    root = _clone_root()
    previous = os.getcwd()
    try:
        os.chdir(root)
        sim_cfg = load_yaml(SIM_CONFIG)["simulation"]
        # The YAML names a missing .pkl (configs/env/sim_config.yaml:9).  The loader's existing-file branch is
        # pd.read_pickle (simulation/cluster_manager.py:358-362).  Pandas infers zip compression from a .zip
        # path and unpickles the archive's single member in memory, which is that pickle
        # (README.md:846-848).  Pointing at the zip avoids the extractall into the clone at
        # simulation/cluster_manager.py:368-369, which a read-only tree cannot accept.
        sim_cfg["workload_path"] = str(root / WORKLOAD_ZIP)
        dc_cfg = load_yaml("configs/env/datacenters.yaml")["datacenters"]
        reward_cfg = load_yaml("configs/env/reward_config.yaml")["reward"]

        start = pd.Timestamp(datetime.datetime(
            sim_cfg["year"], sim_cfg["month"], sim_cfg["init_day"], sim_cfg["init_hour"], 0,
            tzinfo=datetime.timezone.utc))
        end = start + datetime.timedelta(days=sim_cfg["duration_days"])
        cluster = DatacenterClusterManager(
            config_list=dc_cfg, simulation_year=sim_cfg["year"],
            init_day=int(sim_cfg["month"] * 30.5 + sim_cfg["init_day"]),
            init_hour=sim_cfg["init_hour"], strategy=sim_cfg["strategy"],
            tasks_file_path=sim_cfg["workload_path"],
            shuffle_datacenter_order=sim_cfg.get("shuffle_datacenters", True),
            cloud_provider=sim_cfg["cloud_provider"], logger=None)
        reward_fn = CompositeReward(
            components=reward_cfg["components"],
            normalize=reward_cfg.get("normalize", False),
            freeze_stats_after_steps=reward_cfg.get("freeze_stats_after_steps", None))
        # make_env forwards a SummaryWriter only when the caller supplies one (train_SAC_agent.py:94).  None
        # writes no TensorBoard directory.  sim_config still selects single_action_mode (train_SAC_agent.py:95).
        return TaskSchedulingEnv(
            cluster_manager=cluster, start_time=start, end_time=end, reward_fn=reward_fn,
            writer=None, sim_config=sim_cfg)
    finally:
        os.chdir(previous)


class SustainClusterTaskSchedulingEnv(GymnasiumDriver):
    device_id = "sustain-cluster"
    # No gymnasium.register call exists.  The fake backend is the package stand-in; sim builds the real class
    # through the same constructors as train_SAC_agent.make_env (train_SAC_agent.py:63-95).
    env_id = None
    native = "envs.task_scheduling_env:TaskSchedulingEnv"
    backends = {"fake": ".fake:FakeTaskSchedulingEnv", "sim": _build_sim_env}
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
        Fact("The constructor takes a cluster manager, a start and end time, a reward function and an optional "
             "sim_config",
             source="upstream_code", ref=f"{ENV}:28-30"),
        Fact("train_SAC_agent.make_env is the upstream factory: it loads the shipped YAML, builds the cluster "
             "manager and the composite reward, and passes the simulation section as sim_config",
             source="upstream_code", ref="train_SAC_agent.py:63-95"),
        Fact("The shipped workload path is the pickle named in the simulation config",
             source="upstream_code", ref=f"{SIM_CONFIG}:9"),
        Fact("When that path already exists, the cluster manager loads it with pandas.read_pickle and does not "
             "extract the zip",
             source="upstream_code", ref="simulation/cluster_manager.py:358-362"),
        Fact("The README says the pickle is distributed inside the sibling zip in the same directory, and the "
             "loader extracts that zip only when the pickle path is absent",
             source="vendor_doc", ref="README.md:846-848"),
        Fact("The transmission-cost matrix is opened from data/network_cost relative to the working directory",
             source="upstream_code", ref="utils/transmission_cost_loader.py:16-20"),
        Fact("DC_Config stores dc_config_file as an absolute path, so a relative config is resolved from the "
             "working directory at construction",
             source="upstream_code", ref="utils/dc_config_reader.py:20"),
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
                     "and the cluster manager (simulation/cluster_manager.py:103-106).  The fake repeats a "
                     "trajectory for the same seed and actions.  It does not share the upstream random stream, "
                     "and it was not compared with the sim backend in the workspace that wrote this file",
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
            "the sim backend builds that stack through the same constructors as train_SAC_agent.make_env "
            "(train_SAC_agent.py:63-95), reading the workload zip in place (simulation/cluster_manager.py:358-362, "
            "README.md:846-848).  This workspace did not install or run the upstream, so the fake was not compared "
            "with it",
            "no rendering, no snapshot and no restore: the environment exposes no get_state/set_state",
            "wall-clock time is not paced: realtime_factor 0, and simulated time advances 15 minutes per step",
        ],
    }
