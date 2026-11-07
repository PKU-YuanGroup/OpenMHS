"""OpenMHS driver for gh.isaaczh/himloco_lab: the ``Unitree-Go2-Velocity`` Gymnasium environment.

The repository ports HimLoco to Isaac Lab.  The registered environment is an Isaac Lab ``ManagerBasedRLEnv`` subclass
(``himloco_lab.envs:HimlocoManagerBasedRLEnv``); its ``step`` returns six values, not the Gymnasium five-tuple.  This
package exposes the simulation through ``GymnasiumDriver``: ``cap.world.step.v1`` takes ``ticks`` and an action of 12
joint values, ``cap.world.reset.v1`` takes ``seed``/``options`` and ``cap.world.seed.v1`` takes ``seed``.

The environment cannot be opened where the gate runs: it imports Isaac Lab, Isaac Sim, torch and needs a GPU
(README.md:55-72).  The ``fake`` backend is therefore the package's own pure Python contract stand-in (fake.py).  A
backend name that ``backends`` does not list (``sim``) is served by ``gymnasium.make(env_id)`` (GymnasiumDriver
.open_native); that path needs the upstream installation and was not run here.

The device is a simulated R0 world.  It has no hardware backend and no physical e-stop path; the runtime's software
latch is the stop.  The C++ DDS controller in ``deploy/robots/go2`` that can drive a real Go2 is a different interface
and is not covered by this package.  This package is model-authored and unreviewed: its evidence is
``contract_checked`` on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

GO2_ROOT = "source/himloco_lab/himloco_lab/tasks/locomotion/robots/go2"
ASSET = "source/himloco_lab/himloco_lab/assets/unitree.py"
CFG = f"{GO2_ROOT}/velocity_env_cfg.py"
ENV = "source/himloco_lab/himloco_lab/envs/him_manager_based_rl_env.py"
COMMANDS = "source/himloco_lab/himloco_lab/tasks/locomotion/mdp/commands/commands.py"


class HimlocoGo2(GymnasiumDriver):
    device_id = "go2-velocity"
    env_id = "Unitree-Go2-Velocity"
    native = "himloco_lab.envs:HimlocoManagerBasedRLEnv"
    backends = {"fake": ".fake:FakeHimlocoEnv"}
    display_name = "HimLoco Unitree Go2 velocity (Isaac Lab simulation)"
    vendor, model = "IsaacZH", "Unitree Go2"
    mode, risk = "simulated", "R0"
    tags = ["quadruped", "unitree-go2", "locomotion", "velocity-tracking", "isaac-lab", "reinforcement-learning",
            "simulation", "gymnasium"]
    facts = [
        Fact("Unitree-Go2-Velocity is registered with entry point himloco_lab.envs:HimlocoManagerBasedRLEnv and the "
             "training configuration velocity_env_cfg:RobotEnvCfg", source="upstream_code",
             ref=f"{GO2_ROOT}/__init__.py:3-13"),
        Fact("HimlocoManagerBasedRLEnv extends isaaclab.envs.ManagerBasedRLEnv", source="upstream_code",
             ref=f"{ENV}:3-6"),
        Fact("The environment's step returns six values: observations after reset, observations before reset, "
             "rewards, terminated flags, timeout flags and extras", source="upstream_code", ref=f"{ENV}:120"),
        Fact("The Go2 asset lists 12 joints: hip, thigh and calf for each of the four legs", source="upstream_code",
             ref=f"{ASSET}:133-138"),
        Fact("The joint-position action applies scale 0.25 with the default joint offset and clips the processed "
             "action to -100 to 100", source="upstream_code", ref=f"{CFG}:247-249"),
        Fact("The velocity command is an SE(2) command: linear velocity in x and y plus angular velocity around z",
             source="upstream_code", ref=f"{COMMANDS}:22-25"),
        Fact("The policy observation group has velocity commands, base angular velocity, projected gravity, relative "
             "joint positions, relative joint velocities and the last action", source="upstream_code",
             ref=f"{CFG}:261-271"),
        Fact("Every policy observation term is clipped to -100 to 100", source="upstream_code",
             ref=f"{CFG}:262-271"),
        Fact("The environment advances 4 physics steps of 0.005 s per environment step and an episode lasts 20 s",
             source="upstream_code", ref=f"{CFG}:488-492"),
        Fact("The upstream licence metadata is inconsistent: the setup.py SPDX header says BSD-3-Clause while the "
             "setup() call declares Apache-2.0", source="upstream_code", ref="source/himloco_lab/setup.py:4-35"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop no step or reset is accepted until "
                  "mhs.safety.reset clears the latch, and the last observation stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity).  The fake is a contract stand-in, not a
    #: physics model, so the level is F0 and the gaps say what is not modelled.
    fidelity = {
        "engine": "isaaclab:Unitree-Go2-Velocity",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) reseeds the fake's command draw, so one seed repeats the initial policy observation; "
                     "the fake does not model the upstream's numpy/torch random streams or its domain randomisation",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a contract stand-in, not the Isaac Lab simulator: it does not integrate the Go2 rigid-body "
            "dynamics, contacts, actuators, sensors, terrain or domain randomisation; the reward is always 0",
            "the fake exposes the policy observation group only (45 values); the upstream environment also has a "
            "critic group with base linear velocity, external force and a height scan whose sensor dimension is not "
            "visible in the clone",
            "the upstream step returns six values (observation, pre-reset observation, reward, terminated, timeout, "
            "extras); the fake returns the five-value Gymnasium form the bridge accepts",
            "the fake's action space uses the configured joint-position clip (-100, 100) as its bounds; the raw "
            "action space of the Isaac Lab environment is provided by Isaac Lab and was not observed here",
            "gymnasium, torch, Isaac Lab and Isaac Sim are not installed where the gate runs; the sim backend "
            "(gymnasium.make('Unitree-Go2-Velocity')) was not run and needs a GPU",
            "no rendering, no video recording and no exact state snapshot/restore are offered",
        ],
    }
