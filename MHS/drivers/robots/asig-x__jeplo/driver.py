"""OpenMHS driver for gh.asig-x/jeplo: the Unitree-Go2-Locomotion Isaac Lab environment.

The clone registers ``Unitree-Go2-Locomotion`` in ``go2_parkour.tasks`` and its entry point is
``go2_parkour.tasks.go2_loco_env:Go2LocoEnv`` (training/go2_parkour/go2_parkour/tasks/__init__.py:6-9).  The class
extends Isaac Lab's ``DirectRLEnv`` and takes a ``Go2LocoEnvCfg`` plus an optional ``render_mode``
(training/go2_parkour/go2_parkour/tasks/go2_loco_env.py:78-82).  The 12-value action is scaled and clamped when the
joint position target is formed (go2_loco_env.py:469-473; go2_loco_env_cfg.py:178-180), and one environment step
covers a physics timestep of 1/200 s with decimation 4 (go2_loco_env_cfg.py:161-165).

The upstream environment is a GPU Isaac Sim application: the play script launches ``AppLauncher`` first and then
calls ``gym.make(task_name, cfg=env_cfg, ...)`` with a prebuilt config object (training/scripts/play.py:63-64 and
:110).  The task package also needs Isaac Lab 2.3.2.post1, torch 2.7.0, Python 3.11 and an NVIDIA GPU
(README.md:28-32 and :75).  The Gymnasium family's ``gym.make(env_id)`` path supplies neither the app launch nor the
config, so this package was exercised on the package fake backend only; the upstream simulator path was not run.

The fake is a kinematic F0 stand-in (see fake.py).  It keeps the upstream policy width and depth shape but its values
are placeholders, and the fidelity ``gaps`` state every reduction.  This package is simulated R0, model-authored and
unreviewed: the evidence is ``contract_checked`` on the fake backend, never an MHS-Device level and never a hardware
run.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "training/go2_parkour/go2_parkour/tasks/go2_loco_env.py"
CFG = "training/go2_parkour/go2_parkour/tasks/go2_loco_env_cfg.py"
TASKS = "training/go2_parkour/go2_parkour/tasks/__init__.py"
PATTERN = "training/go2_parkour/go2_parkour/sensor/lidar_pattern.py"
PLAY = "training/scripts/play.py"


class JeploGo2Loco(GymnasiumDriver):
    device_id = "jeplo-go2"
    device_kind = "world.sim"
    mode, risk = "simulated", "R0"
    env_id = "Unitree-Go2-Locomotion"
    native = "go2_parkour.tasks.go2_loco_env:Go2LocoEnv"
    backends = {"fake": ".fake:FakeGo2LocoEnv"}
    display_name = "JEPLO Unitree Go2 locomotion (Isaac Lab)"
    vendor, model = "ASIG-X", "Unitree-Go2-Locomotion"
    tags = ["unitree-go2", "quadruped", "isaac-lab", "isaac-sim", "lidar", "locomotion",
            "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("The repository targets a quadrupedal Unitree Go2 with a single Mid-360 LiDAR",
             source="vendor_doc", ref="README.md:9"),
        Fact("Unitree-Go2-Locomotion is registered with entry point "
             "go2_parkour.tasks.go2_loco_env:Go2LocoEnv and disable_env_checker=True",
             source="upstream_code", ref=f"{TASKS}:6-9"),
        Fact("Go2LocoEnv extends DirectRLEnv and is constructed from a Go2LocoEnvCfg and an optional render_mode",
             source="upstream_code", ref=f"{ENV}:78-82"),
        Fact("The config sets action_space to 12, action_scale to 0.25 and action_target_clip to "
             "(-100.0, 100.0)", source="upstream_code", ref=f"{CFG}:178-180"),
        Fact("Each action is applied as action * action_scale plus the default joint positions plus the motor zero "
             "offset, and the resulting joint position target is clamped to action_target_clip",
             source="upstream_code", ref=f"{ENV}:469-473"),
        Fact("An episode lasts 25.0 s; the physics timestep is 1/200 s and decimation is 4",
             source="upstream_code", ref=f"{CFG}:161-165"),
        Fact("The default scene has 4096 environments with 10 m spacing",
             source="upstream_code", ref=f"{CFG}:185"),
        Fact("The observation config defines a 10-step history of 45 proprioception values, 300 height-scan values, "
             "50 privileged values and 45 critic proprioception values",
             source="upstream_code", ref=f"{CFG}:248-262"),
        Fact("_get_observations returns a dict with a policy tensor and a depth tensor of num_depth_stack frames",
             source="upstream_code", ref=f"{ENV}:665-671"),
        Fact("The Mid-360 ray pattern defaults to 25 vertical and 60 horizontal rays",
             source="upstream_code", ref=f"{PATTERN}:86-88"),
        Fact("An episode ends when roll or pitch exceeds 1.5 rad, base height is below -5.0, or the episode "
             "timestep reaches max_episode_length - 1", source="upstream_code", ref=f"{ENV}:835-847"),
        Fact("The play script launches AppLauncher before any environment is created",
             source="upstream_code", ref=f"{PLAY}:63-64"),
        Fact("The play script creates the environment with gym.make(task_name, cfg=env_cfg, render_mode=...)",
             source="upstream_code", ref=f"{PLAY}:110"),
        Fact("The install instructions create a Python 3.11 environment and install "
             "isaaclab[isaacsim,all]==2.3.2.post1 and torch 2.7.0", source="vendor_doc",
             ref="README.md:28-32"),
        Fact("The README notes that a decent computer with an Nvidia GPU is needed for simulation and control",
             source="vendor_doc", ref="README.md:75"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity FID-002).  The bridge derives the engine,
    #: determinism and clock; they are written out here so the whole contract reads in one place.
    fidelity = {
        "engine": "isaaclab:Unitree-Go2-Locomotion",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake seeds Python's random.Random from reset(seed) or cap.world.seed.v1 and its "
                     "kinematic update is deterministic; the upstream seed would drive Isaac Lab's generators, and "
                     "the two were not compared because the upstream stack was not run",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic F0 stand-in: no rigid-body dynamics, contacts, actuator, sensor, terrain, noise or "
            "rendering model; each tick replaces the 12 joint coordinates with action * 0.25 plus the reset home "
            "pose, clamped to the configured joint-target clip",
            "the fake returns placeholder values at the upstream policy width (845 values) and depth shape "
            "(2 x 25 x 60); they are not Isaac Sim sensor data, and the depth values are constant",
            "the upstream environment is vectorized over num_envs (default 4096) and steps a batched torch action "
            "tensor, while the MHS Gymnasium bridge drives one environment; the two conventions were not reconciled "
            "or compared",
            "the registered environment cannot be created by GymnasiumDriver's gym.make(env_id) path alone: "
            "play.py:63-64 launches AppLauncher first and play.py:110 passes a prebuilt Go2LocoEnvCfg as cfg, so the "
            "upstream simulator path was not run (it needs Isaac Sim, Isaac Lab, Linux and an NVIDIA GPU)",
            "no termination or goal model: the roll, pitch, base-height and goal cutoffs are not simulated, so "
            "terminated stays False; truncated follows only a derived 1250-step episode budget "
            "(25.0 s / 0.02 s), not Isaac Lab's episode bookkeeping",
            "no wall-clock pacing: realtime_factor 0 and clock lockstep; the physics timestep is 5 ms (1/200 s) "
            "with decimation 4, so one environment step is 20 ms and timestep_ms names that control step",
            "snapshot and restore are not offered: the fake exposes no get_state/set_state",
            "the LiDAR ray casting, dropout and noise parameters of the Mid-360 sensor are not modelled",
        ],
    }
