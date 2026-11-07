"""OpenMHS driver for gh.isaac-sim/isaaclab-arena: the Isaac Lab-Arena Gymnasium environment layer.

Isaac Lab-Arena composes a scene, an embodiment and a task into an Isaac Lab ``ManagerBasedRLEnv`` and registers the
result with Gymnasium (``ArenaEnvBuilder.build_registered``, arena_env_builder.py:578 and :600-605;
``make_registered``, :655-656).  ``IsaacLabArenaManagerBasedRLEnv`` is that vectorized Isaac Lab environment
(isaaclab_arena_manager_based_env.py:34): it takes a torch action tensor and returns the vectorized step tuple
(:183-189), and its reset forwards to ``ManagerBasedRLEnv.reset`` (:173-181).  The family bridge serves it through
``cap.world.step.v1``, ``cap.world.reset.v1`` and ``cap.world.seed.v1``.

There is no fixed ``env_id`` in the clone: the builder registers the composed environment under the name carried by
the user's ``IsaacLabArenaEnvironment`` (arena_env_builder.py:578 and :600-605), so the family's ``gym.make(env_id)`` path
cannot name an environment from configuration alone.  This package therefore ships only the package fake backend;
the upstream simulator path was not run (README.md:79-80 requires Linux and an NVIDIA GPU, and pyproject.toml:12
requires Python 3.12).  This package is simulated R0, model-authored and unreviewed: the evidence is
``contract_checked`` on the fake backend, never an MHS-Device level and never a hardware run.

The ``fidelity`` contract describes the model as deployed: a kinematic F0 stand-in with no Isaac Sim physics.  The
composed embodiment selects the action terms (embodiment docs:32-35), so the fake's one-element action Box is a
reduction stated in the fidelity gaps.
"""

from mhs.driver import Fact, GymnasiumDriver

ARENA_ENV = "isaaclab_arena/environments/isaaclab_arena_manager_based_env.py"
ARENA_BUILDER = "isaaclab_arena/environments/arena_env_builder.py"
ARENA_CFG = "isaaclab_arena/environments/isaaclab_arena_manager_based_env_cfg.py"
DOCS_BUILDER = "docs/pages/concepts/environment/env_builder.rst"
DOCS_POLICY = "docs/pages/concepts/policy/index.rst"
DOCS_EMBODIMENT = "docs/pages/concepts/embodiment/index.rst"


class IsaacLabArena(GymnasiumDriver):
    device_id = "isaaclab-arena"
    device_kind = "world.sim"
    mode, risk = "simulated", "R0"
    #: No fixed environment id exists in the clone: ArenaEnvBuilder registers the user's environment name at
    #: composition time (ARENA_BUILDER:578 and :600-605).  The fake backend is the only backend this package provides.
    env_id = None
    native = "isaaclab_arena.environments.isaaclab_arena_manager_based_env:IsaacLabArenaManagerBasedRLEnv"
    backends = {"fake": ".fake:FakeArenaEnv"}
    display_name = "Isaac Lab-Arena (Isaac Lab manager-based Gymnasium environment)"
    vendor, model = "NVIDIA / Isaac Sim", "Isaac Lab-Arena"
    tags = ["isaac-lab", "isaac-sim", "arena", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("IsaacLabArenaManagerBasedRLEnv extends Isaac Lab's vectorized ManagerBasedRLEnv", source="upstream_code",
             ref=f"{ARENA_ENV}:34"),
        Fact("The environment is constructed from a composed IsaacLabArenaManagerBasedRLEnvCfg and an optional "
             "render_mode", source="upstream_code", ref=f"{ARENA_ENV}:39-45"),
        Fact("reset(seed, env_ids, options) forwards to ManagerBasedRLEnv.reset; with an episode limit only the "
             "initial explicit reset is allowed", source="upstream_code", ref=f"{ARENA_ENV}:173-181"),
        Fact("step takes a torch action tensor and returns the vectorized step tuple, reporting completions only for "
             "environments that were assigned an episode before the step", source="upstream_code",
             ref=f"{ARENA_ENV}:183-189"),
        Fact("The Arena environment cfg sets sim.dt to 1/120 s and decimation to 8, a 15 Hz control rate by default",
             source="upstream_code", ref=f"{ARENA_CFG}:103-108"),
        Fact("An embodiment offers one or more control variants, for example franka_ik uses differential IK control "
             "while franka_joint_pos uses direct joint position control, so the composed embodiment selects the "
             "action terms", source="vendor_doc", ref=f"{DOCS_EMBODIMENT}:32-35"),
        Fact("A policy receives the observation as a Gymnasium spaces Dict and returns an action tensor shaped like "
             "env.action_space", source="vendor_doc", ref=f"{DOCS_POLICY}:64-66"),
        Fact("Setting --seed fixes the simulation and the run-time variation draws", source="vendor_doc",
             ref=f"{DOCS_BUILDER}:121"),
        Fact("build_registered takes the Gymnasium id from self.arena_env.name", source="upstream_code",
             ref=f"{ARENA_BUILDER}:578"),
        Fact("ArenaEnvBuilder registers the composed environment with gym.register(id=name, entry_point=...); the "
             "id is therefore chosen by the composed IsaacLabArenaEnvironment", source="upstream_code",
             ref=f"{ARENA_BUILDER}:600-605"),
        Fact("Documentation states that the compiled config is registered with the gym registry under the "
             "environment's name and gym.make() returns the environment", source="vendor_doc",
             ref=f"{DOCS_BUILDER}:125-126"),
        Fact("make_registered calls gym.make(name, cfg=cfg, render_mode=render_mode, **env_kwargs)",
             source="upstream_code", ref=f"{ARENA_BUILDER}:655-656"),
        Fact("The default Gymnasium entry point is IsaacLabArenaManagerBasedRLEnv; mimic mode uses the embodiment's "
             "mimic environment instead", source="upstream_code", ref=f"{ARENA_BUILDER}:548-557"),
        Fact("The README example composes an environment with ArenaEnvBuilder.make_registered and calls env.reset()",
             source="vendor_doc", ref="README.md:167-170"),
        Fact("The package requires Python >=3.12,<3.13", source="vendor_doc", ref="pyproject.toml:12"),
        Fact("The prerequisites are Linux (Ubuntu 22.04+) and an NVIDIA GPU", source="vendor_doc",
             ref="README.md:79-80"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: determinism and clock; they are written out here so the whole contract reads in one place.
    fidelity = {
        "engine": "isaaclab_arena:IsaacLabArenaManagerBasedRLEnv",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake seeds Python's random.Random from reset(seed) or cap.world.seed.v1 and its one "
                     "kinematic update is deterministic; the upstream seed controls Isaac Lab's generators and the "
                     "Arena variation draws, and the two were not compared because the upstream stack was not run",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic F0 stand-in: no Isaac Sim physics, contacts, actuator, sensor, noise or rendering model; the "
            "fake advances one scalar coordinate per tick and claims no dynamics",
            "the real action space is the batched Box of Isaac Lab's action manager whose width is the sum of the "
            "action term dimensions, and the real observation is a Dict of group Boxes, both chosen by the composed "
            "environment; the fake uses a one-element action Box and one policy group, so the arrays are smaller "
            "than the device's",
            "the upstream environment is vectorized over num_envs while the MHS Gymnasium bridge drives one "
            "environment; the upstream path was not executed (it needs Isaac Sim, Isaac Lab, Linux and an NVIDIA GPU)",
            "there is no fixed env_id to gym.make: ArenaEnvBuilder registers the composed environment under its "
            "user-chosen name, so only the package fake backend is provided and the upstream simulator path is not "
            "configured",
            "timestep_ms is 0 because the fake is event-driven per tick; the upstream Arena cfg uses a 15 Hz "
            "control step by default (sim.dt 1/120 s x decimation 8) and an env_cfg_callback can change it",
            "snapshot and restore are not offered: the fake exposes no get_state/set_state",
            "no wall-clock pacing: realtime_factor 0 and clock lockstep",
        ],
    }
