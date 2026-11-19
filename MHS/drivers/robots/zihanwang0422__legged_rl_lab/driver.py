"""OpenMHS driver for gh.zihanwang0422/legged_rl_lab: the cross-embodied G1+Go2 flat locomotion environment.

The card's entry symbol is a concrete Isaac Lab environment:
``legged_rl_lab.tasks.locomotion.cross_emboided.config.g1go2_mixed.g1go2_flat_env_cfg:CrossEmbodiedG1Go2Env``
(``g1go2_flat_env_cfg.py:553``), registered as
``LeggedRLLab-Isaac-CrossEmboided-Flat-G1Go2-Mixed-v0`` (``config/g1go2_mixed/__init__.py:25-33``).  A GymnasiumDriver
is configuration only: the bridge derives ``cap.world.step.v1`` (``{ticks, action}``) from the environment's
29-dimensional action space and the observation from its ``policy``/``critic`` groups; ``cap.world.reset.v1`` and
``cap.world.seed.v1`` call the environment's seeded reset.  The device is simulated (R0): there is no hardware
backend, no e-stop path to a machine and no operator-required limit.

The upstream environment is an Isaac Sim 5.1.0 / Isaac Lab 2.3.0 GPU simulation (``README.md:3-5``).  Neither is
installed where the gate runs, so the ``fake`` backend is the package's pure-Python kinematic G1 slice
(:mod:`fake`). Only the fake backend is declared. The family's implicit ``gymnasium.make(env_id)`` fallback is
not a usable live adapter: it supplies no required ``cfg``, app lifecycle or batched tensor conversion. A live
backend would need those pieces and a source-backed simulator stop; none was run here.

The ``fidelity`` attribute is the complete contract of the model as deployed (spec 05-fidelity FID-002): the fake is
a kinematic F0 model, not the Isaac Sim rigid-body simulation.  Every constant and rule cites a line of the clone at
the pinned commit 386ee24bc62c8033641d65b940dc2cf1dec56545.  This package is model-authored and unreviewed: it is
checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV_CFG = ("source/legged_rl_lab/legged_rl_lab/tasks/locomotion/cross_emboided/config/g1go2_mixed/"
           "g1go2_flat_env_cfg.py")
ENV_INIT = "source/legged_rl_lab/legged_rl_lab/tasks/locomotion/cross_emboided/config/g1go2_mixed/__init__.py"
ACTION_TERM = "source/legged_rl_lab/legged_rl_lab/tasks/locomotion/cross_emboided/mdp/cross_embodied_mdp.py"
ASSETS = "source/legged_rl_lab/legged_rl_lab/assets/unitree.py"


class CrossEmbodiedG1Go2(GymnasiumDriver):
    device_id = "g1go2-cross-embodied"
    env_id = "LeggedRLLab-Isaac-CrossEmboided-Flat-G1Go2-Mixed-v0"
    native = ("legged_rl_lab.tasks.locomotion.cross_emboided.config.g1go2_mixed.g1go2_flat_env_cfg:"
              "CrossEmbodiedG1Go2Env")
    backends = {"fake": ".fake:FakeCrossEmbodiedG1Go2Env"}
    display_name = "LeggedRLLab cross-embodied G1+Go2 flat locomotion (Isaac Lab)"
    vendor, model = "zihanwang0422", "LeggedRLLab-Isaac-CrossEmboided-Flat-G1Go2-Mixed-v0"
    tags = ["legged-robot", "locomotion", "cross-embodied", "reinforcement-learning", "isaac-lab", "simulation",
            "gymnasium"]
    facts = [
        Fact("The repository targets Isaac Sim 5.1.0 and Isaac Lab 2.3.0 and its documented environment uses "
             "Python 3.11", source="vendor_doc", ref="README.md:3-5"),
        Fact("The cross-embodied G1+Go2 flat task is registered as "
             "LeggedRLLab-Isaac-CrossEmboided-Flat-G1Go2-Mixed-v0 with CrossEmbodiedG1Go2Env as its entry point",
             source="upstream_code", ref=f"{ENV_INIT}:20-33"),
        Fact("The scene spawns a 29-DOF Unitree G1 and a 12-DOF Unitree Go2 in every environment; the first "
             "n // 2 environments make G1 active and the second half make Go2 active", source="upstream_code",
             ref=f"{ENV_CFG}:4-10"),
        Fact("The shipped configuration sets num_envs to 512 with an environment spacing of 4.0 m",
             source="upstream_code", ref=f"{ENV_CFG}:519-522"),
        Fact("The inactive-robot parking constant _PARK_ALTITUDE is 100.0",
             source="upstream_code", ref=f"{ENV_CFG}:549-550"),
        Fact("The policy action is one unified 29-dimensional vector; G1 uses all 29 dims and Go2 applies only the "
             "first 12 and discards dims 12-28", source="upstream_code", ref=f"{ACTION_TERM}:645-653"),
        Fact("The raw action is scaled by 0.5 for G1 and 0.25 for Go2", source="upstream_code",
             ref=f"{ENV_CFG}:197-198"),
        Fact("The action term computes scaled = action * scale and joint targets = default joint position + scaled, "
             "and stores the Go2-masked scaled action in _last_scaled", source="upstream_code",
             ref=f"{ACTION_TERM}:689-710"),
        Fact("last_action_cross clones action_manager.action and zeroes unused Go2 dimensions",
             source="upstream_code", ref=f"{ACTION_TERM}:117-127"),
        Fact("The policy joint velocity observation has scale 0.05 and last_action uses last_action_cross",
             source="upstream_code", ref=f"{ENV_CFG}:150-155"),
        Fact("The critic joint velocity observation has scale 0.05 and last_action uses last_action_cross",
             source="upstream_code", ref=f"{ENV_CFG}:176-178"),
        Fact("The actor observation is 98 dimensions [robot_id(2), base angular velocity(3), projected gravity(3), "
             "command(3), joint position(29), joint velocity(29), last action(29)] and the critic observation is "
             "101 dimensions, adding base linear velocity(3)", source="upstream_code", ref=f"{ENV_CFG}:15-30"),
        Fact("The velocity command samples x and y linear velocity and yaw rate uniformly from -1.0 to 1.0 and "
             "resamples them every 10 s", source="upstream_code", ref=f"{ENV_CFG}:216-227"),
        Fact("Termination selects base_below_threshold_cross with min_height 0.25 and mdp.time_out with "
             "time_out=True", source="upstream_code", ref=f"{ENV_CFG}:493-497"),
        Fact("The control period is four 5 ms simulation steps (20 ms) and the configured episode length is 20 s",
             source="upstream_code", ref=f"{ENV_CFG}:533-535"),
        Fact("The G1 initial-state configuration sets pos=(0.0, 0.0, 0.8)", source="upstream_code",
             ref=f"{ASSETS}:332-333"),
        Fact("The shared alive reward term has weight 0.15", source="upstream_code", ref=f"{ENV_CFG}:366"),
        Fact("is_alive_cross returns the inverse of termination_manager.terminated as floats",
             source="upstream_code", ref=f"{ACTION_TERM}:187-193"),
        Fact("The package setup metadata declares license Apache 2.0", source="upstream_code",
             ref="source/legged_rl_lab/setup.py:30"),
    ]
    safe_state = ("on the declared fake backend, the lockstep stand-in stops advancing: no step, world reset or "
                  "seed command is accepted until mhs.safety.reset clears the latch; the cached state stays "
                  "readable and clearing the latch alone changes no state; this establishes no Isaac Sim stop")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "analytic:legged_rl_lab-g1go2-kinematic-fake",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the fake's command draw and the episode state; the "
                     "kinematic transition is deterministic, so one seed and action sequence repeats a trajectory "
                     "on this fake.  The upstream environment draws randomisation from torch and Isaac Lab "
                     "generators, so a seed does not give the same trajectory on the two.",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "no rigid-body dynamics: joint positions are set directly from the scaled action, with no contacts, "
            "friction, gravity, actuator, sensor or noise model (F0 kinematic model, not the Isaac Sim physics)",
            "the fake models one G1 environment, not the configured 512 environments (half G1, half Go2); the Go2 "
            "branch, its 12-joint action slice and the 12-28 zero padding are not modelled",
            "the real environment is vectorized: its observations are batched (num_envs, 98) and (num_envs, 101) "
            "tensors and reward/terminated/truncated are (num_envs,) tensors, while the fake returns one "
            "environment's 98 and 101 values and scalar reward and flags",
            "the fake publishes an unbounded 29-element action Box because the clone's action term "
            "(cross_embodied_mdp.py:689-710) defines no clip; the external Isaac Lab action manager's own space was "
            "not inspected, so no finite action bound is claimed",
            "the base-height transition is a synthetic kinematic placeholder, so the 0.25 m base-fall termination "
            "is exercised by the fake's height rule, not by rigid-body dynamics",
            "the fake uses weight 0.15 as a synthetic per-step alive score, zero on termination; the external "
            "reward manager's integration and every tracking, gait, contact and joint penalty term are omitted",
            "the observation values are analytic: projected gravity is constant, base angular and linear velocity "
            "are zero and joint velocity is a finite difference of commanded offsets with the configured 0.05 "
            "observation scale; last_action reports the raw action, not the action term's scaled target",
            "the fake samples commands with Python's random.Random and does not model the 2 percent standing "
            "environments or the command manager's own generator",
            "no rendering, no snapshot and restore (the environment exposes no get_state/set_state) and no GPU or "
            "Isaac Sim work",
            "the upstream environment needs Isaac Sim 5.1.0, Isaac Lab 2.3.0 and a GPU (README.md:3-5); it was not "
            "installed or run here and the fake was never compared with it",
            "only fake is declared: the implicit gymnasium.make fallback supplies no required cfg "
            "(g1go2_flat_env_cfg.py:573-578), AppLauncher lifecycle (scripts/rsl_rl/train.py:59-61), task "
            "registration import, tensor action batch or vector reward/flag adapter; it is not a supported live route",
            "the fake ends an episode at its synthetic 1000-step counter and requires an explicit world reset; "
            "the inherited Isaac Lab automatic-reset and timeout-counter lifecycle were not reproduced",
            "the source parking helper sets world z to _PARK_ALTITUDE (g1go2_flat_env_cfg.py:607-615), rather "
            "than adding that value to the origin z; the fake omits inactive-robot parking entirely",
            "the repository also ships Go1/G1 hardware deployment scripts and Unitree SDK submodules; none is "
            "imported or served by this fake-only package",
            "the card retains NOASSERTION and publication review is required despite Apache 2.0 setup metadata "
            "and source headers; no root-wide license grant is inferred from those files",
        ],
    }
