"""OpenMHS driver for gh.renforce-dynamics/genesislab: the Genesis-HVelocity-G1-v0 environment.

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives the
``cap.world.step.v1``, ``cap.world.reset.v1`` and ``cap.world.seed.v1`` contract.  The environment is a vectorized
Genesis simulator (R0, simulated): there is no hardware backend, no e-stop path to a machine and no physical effect.

The upstream class does not expose Gymnasium spaces: ``ManagerBasedGenesisEnv._configure_spaces`` assigns a torch
zeros tensor to ``action_space`` and leaves ``observation_space`` as ``None``
(``source/genesislab/genesislab/envs/manager_based_genesis_env.py:156-165``).  The package fake therefore supplies an
unbounded placeholder Box of 29 elements (the G1 asset is the 29-DOF ``g1_29dof_rev_1_0.xml``) and leaves the
observation space ``None``, so the bridge publishes the action as an open numeric vector and the observation as an
open object.  The placeholder shape is test data, not a device limit.

The gate cannot install the upstream package (torch, the Genesis engine and the downloaded assets) and package code
never imports the clone, so the ``fake`` backend is a pure Python kinematic stand-in (``fake.py``).  Every fact cites
a line of the clone at the pinned commit ``0f2e4d96df9b24bcce66f8bdf7a1884a1363a5bb``.  This package is
model-authored and unreviewed: it is checked on the fake backend only, and no upstream environment was run.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV_INIT = "source/genesis_tasks/genesis_tasks/locomotion/hvelocity/g1/__init__.py"
HV = "source/genesis_tasks/genesis_tasks/locomotion/hvelocity"
BASE_ENV = "source/genesislab/genesislab/envs/manager_based_genesis_env.py"
RL_ENV = "source/genesislab/genesislab/envs/manager_based_rl_env.py"


class GenesisLabVelocity(GymnasiumDriver):
    """The flat-ground Unitree G1 human-velocity task as a simulated OpenMHS world."""

    device_id = "genesislab-g1-velocity"
    env_id = "Genesis-HVelocity-G1-v0"
    native = "genesislab.envs:ManagerBasedRlEnv"
    backends = {"fake": ".fake:FakeManagerBasedRlEnv"}
    display_name = "GenesisLab Unitree G1 human velocity (flat)"
    vendor, model = "Renforce Dynamics", "Genesis-HVelocity-G1-v0"
    tags = ["genesis", "genesislab", "gymnasium", "humanoid", "g1", "reinforcement-learning", "simulation"]
    risk = "R0"
    facts = [
        Fact("Genesis-HVelocity-G1-v0 is registered with the entry point genesislab.envs:ManagerBasedRlEnv",
             source="upstream_code", ref=f"{ENV_INIT}:4-13"),
        Fact("ManagerBasedRlEnv subclasses ManagerBasedGenesisEnv and keeps its reset/step semantics",
             source="upstream_code", ref=f"{RL_ENV}:28-34"),
        Fact("The environment is vectorized: is_vector_env is True and metadata declares render modes",
             source="upstream_code", ref=f"{BASE_ENV}:48-55"),
        Fact("reset(seed=None, env_ids=None, options=None) returns (observations, info)",
             source="upstream_code", ref=f"{BASE_ENV}:206-261"),
        Fact("step(action) returns (observations, rewards, terminations, time-outs and info)",
             source="upstream_code", ref=f"{BASE_ENV}:263-293"),
        Fact("The scene physics timestep is dt = 0.005 s",
             source="upstream_code", ref=f"{HV}/components.py:31"),
        Fact("The control step is decimation 4 physics steps",
             source="upstream_code", ref=f"{HV}/hvelocity_env_cfg.py:32"),
        Fact("The episode length is 20.0 s", source="upstream_code",
             ref=f"{HV}/hvelocity_env_cfg.py:33"),
        Fact("The G1 asset is the 29-DOF MJCF g1_29dof_rev_1_0.xml with control_dofs None (all DOF)",
             source="upstream_code", ref="source/genesis_assets/genesis_assets/robots/g1/official.py:44-49"),
        Fact("The joint position action is scaled by 0.25 and uses the default joint offset",
             source="upstream_code", ref=f"{HV}/components.py:92-96"),
        Fact("The policy observation terms are concatenated into one group",
             source="upstream_code", ref=f"{HV}/components.py:133"),
        Fact("A reset with a seed calls seed(seed), which sets cfg.seed and seeds torch and Python random",
             source="upstream_code", ref=f"{BASE_ENV}:106-116"),
        Fact("The observation is a dict of tensors and a step returns five signals",
             source="upstream_code", ref="source/genesislab/genesislab/envs/common/viewer.py:54-63"),
        Fact("The environment assigns a torch zeros tensor to action_space and leaves observation_space None",
             source="upstream_code", ref=f"{BASE_ENV}:156-165"),
        Fact("GenesisLab is built on top of the Genesis physics engine", source="vendor_doc", ref="README.md:13"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the world state is kept and stays readable")
    fidelity_level = "F1"
    #: The contract of the Genesis environment as deployed; the fake backend is not that environment.
    fidelity = {
        "engine": "genesis",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) calls the environment's seed(), which sets cfg.seed and seeds torch and Python "
                     "random; the bridge repeats a trajectory for one seed from a fresh world. The fake uses only "
                     "Python's random.Random, so a seed gives different trajectories on the fake and upstream.",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the upstream action_space is a torch zeros tensor and observation_space is None, not Gymnasium "
            "spaces; the fake supplies an unbounded 29-element placeholder Box so the bridge can shape a "
            "joint-position action vector, and the real action width is resolved from the robot's actuator layout",
            "the fake backend is a deterministic kinematic stand-in: it has no Genesis physics, contacts, "
            "actuators, sensors, terrain, events or noise model, and its observation and state values are test data",
            "the environment is vectorized (num_envs 4096 by default) and GPU-backed; the bridge steps one action "
            "vector and the fake models one world",
            "no snapshot or restore is offered: the environment exposes no get_state/set_state pair",
            "the upstream environment was never run here: torch, the Genesis engine and the robot assets are not "
            "installed, so the fake and the registration were not compared with a real rollout",
        ],
    }
