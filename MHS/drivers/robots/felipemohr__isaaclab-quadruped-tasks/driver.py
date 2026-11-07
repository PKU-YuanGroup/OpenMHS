"""OpenMHS driver for gh.felipemohr/isaaclab-quadruped-tasks: the ANYmal D blind-flat Isaac Lab task.

A ``GymnasiumDriver`` is configuration only.  ``env_id`` is the Gymnasium ID this repository registers
(``Isaac-Quadruped-AnymalD-Blind-Flat-v0``) and the bridge derives the contract from the environment's spaces:
``cap.world.step.v1`` takes ``{ticks, action}``, ``cap.world.reset.v1`` takes ``{seed, options}`` and
``cap.world.seed.v1`` takes ``{seed}``.  The device is a simulator (R0): there is no hardware backend, no e-stop
path to a machine and no operator-required limit.

``native`` is the card's confirmed in-tree entry symbol, the environment configuration class
``AnymalDBlindFlatEnvCfg``.  The registered environment class itself is ``omni.isaac.lab.envs:ManagerBasedRLEnv``,
which is external to this clone (anymal_d/__init__.py:45); the card's other entry symbols are the Go2 and Spot
configuration classes.  The package's ``fake`` backend stands in for the registered environment, and the gate
compares its Gymnasium interface with the configuration class, whose base ``ManagerBasedRLEnvCfg`` is also outside
the clone; those interface names are reported as ``G7.MAYBE_ABSENT`` warnings by design.

The gate cannot import Isaac Sim or Isaac Lab, so the ``fake`` backend is the package's own analytic stand-in
(fake.py).  A backend name that ``backends`` does not list (``sim``) is served by ``gymnasium.make(env_id)``
(``GymnasiumDriver.open_native``); that path needs the external Isaac Sim/Isaac Lab stack and was not run here.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002).
The constants and rules that describe the clone cite its files at the pinned commit
(6d2f0b39c162330f9697db132238b64855cb6ae3).  This package is model-authored and unreviewed: it is checked on the
fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ANYMAL_INIT = "exts/omni.isaac.lab_quadruped_tasks/omni/isaac/lab_quadruped_tasks/robots/anymal_d/__init__.py"
ANYMAL_CFG = ("exts/omni.isaac.lab_quadruped_tasks/omni/isaac/lab_quadruped_tasks/robots/anymal_d/"
              "anymal_d_env_cfg.py")
QUADRUPED_CFG = ("exts/omni.isaac.lab_quadruped_tasks/omni/isaac/lab_quadruped_tasks/cfg/"
                 "quadruped_env_cfg.py")
SETUP = "exts/omni.isaac.lab_quadruped_tasks/setup.py"


class AnymalDBlindFlat(GymnasiumDriver):
    device_id = "anymal-d-blind-flat"
    env_id = "Isaac-Quadruped-AnymalD-Blind-Flat-v0"
    native = "omni.isaac.lab_quadruped_tasks.robots.anymal_d.anymal_d_env_cfg:AnymalDBlindFlatEnvCfg"
    backends = {"fake": ".fake:FakeAnymalDBlindFlatEnv"}
    display_name = "Isaac Lab ANYmal D blind flat (Isaac-Quadruped-AnymalD-Blind-Flat-v0)"
    vendor, model = "Felipe Mohr Santos", "Isaac-Quadruped-AnymalD-Blind-Flat-v0"
    tags = ["quadruped", "anymal-d", "reinforcement-learning", "isaac-lab", "simulation", "gymnasium"]
    facts = [
        Fact("The repository is an Isaac Lab extension with tasks for training quadruped robots using "
             "reinforcement learning", source="upstream_code", ref="README.md:15"),
        Fact("Five task types train three quadruped robots, ANYmal D, Go2 and Spot", source="upstream_code",
             ref="README.md:17-23"),
        Fact("The installation begins by installing NVIDIA Isaac Sim and Isaac Lab separately", source="upstream_code",
             ref="README.md:26"),
        Fact("The extension is installed with pip install -e exts/omni.isaac.lab_quadruped_tasks",
             source="upstream_code", ref="README.md:33"),
        Fact("The task registrations import gymnasium as gym", source="upstream_code", ref=f"{ANYMAL_INIT}:6"),
        Fact("Isaac-Quadruped-AnymalD-Blind-Flat-v0 is registered with entry_point "
             "omni.isaac.lab.envs:ManagerBasedRLEnv and env_cfg_entry_point AnymalDBlindFlatEnvCfg",
             source="upstream_code", ref=f"{ANYMAL_INIT}:43-50"),
        Fact("AnymalDBlindFlatEnvCfg is defined in the clone and extends AnymalDBaseEnvCfg", source="upstream_code",
             ref=f"{ANYMAL_CFG}:65"),
        Fact("The blind flat task disables the height scanner, the height-map observation, the velocity-command "
             "event and the terrain-level curriculum", source="upstream_code", ref=f"{ANYMAL_CFG}:69-73"),
        Fact("The action term is JointPositionActionCfg with asset_name 'robot', joint_names ['.*'], scale 0.5 "
             "and use_default_offset True", source="upstream_code", ref=f"{QUADRUPED_CFG}:118"),
        Fact("The policy observation terms are the velocity command, base linear velocity, base angular velocity, "
             "projected gravity, joint positions, joint velocities, last action and, when enabled, a clipped height "
             "map; the base and joint measurements carry Gaussian noise", source="upstream_code",
             ref=f"{QUADRUPED_CFG}:130-150"),
        Fact("The policy observation group concatenates its terms and enables corruption by default",
             source="upstream_code", ref=f"{QUADRUPED_CFG}:152-155"),
        Fact("The environment applies decimation 4 with sim.dt 1/200 s, episode_length_s 20.0 and seed 42",
             source="upstream_code", ref=f"{QUADRUPED_CFG}:300-306"),
        Fact("INSTALL_REQUIRES lists numpy, torch 2.4.0, torchvision, protobuf, h5py, tensorboard and moviepy",
             source="upstream_code", ref=f"{SETUP}:15-29"),
        Fact("The extension package requires Python 3.10 or newer", source="upstream_code", ref=f"{SETUP}:58"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The fake is analytic (F0):
    #: there is no physics engine, so no contact or actuator claim is made.
    fidelity = {
        "engine": "gymnasium:Isaac-Quadruped-AnymalD-Blind-Flat-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the fake's initial joint positions and every later "
                     "transition is a deterministic kinematic update, so one seed and one action sequence repeat "
                     "the state hashes; the registered Isaac Lab environment, which was not run, seeds its own "
                     "simulation and randomization (quadruped_env_cfg.py:306)",
        },
        "timestep_ms": 5.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "F0: the fake backend is an analytic kinematic stand-in, not Isaac Lab; it moves its joint positions "
            "directly toward the action and models no rigid-body dynamics, contacts, actuators, sensors or noise",
            "the fake's action and observation dimensions are placeholders (RESULT.json notes); the configured "
            "task writes one joint-position target per joint matched by joint_names ['.*'] of the external robot "
            "asset and concatenates the observation terms, whose real dimensions depend on that asset and are "
            "not in the clone",
            "the fake never terminates or truncates; the configured episode_length_s is 20 s "
            "(quadruped_env_cfg.py:300-301) but no episode limit is modelled",
            "no wall-clock pacing: realtime_factor 0; one environment step applies decimation 4 physics steps "
            "and timestep_ms names the physics timestep 1/200 s, so one tick is 20 ms of simulated time "
            "(quadruped_env_cfg.py:300-305)",
            "the fake was never compared with the registered Isaac Lab environment: Isaac Sim and Isaac Lab are "
            "external and were not installed, and the sim backend (gymnasium.make) was not run",
            "snapshot and restore are not offered: the fake exposes no get_state/set_state",
        ],
    }
