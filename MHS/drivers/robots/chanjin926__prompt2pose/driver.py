"""OpenMHS driver for gh.chanjin926/prompt2pose: the ManiSkill ArrayCan-v1 environment.

A GymnasiumDriver is configuration only: ``env_id`` names the environment and the bridge derives the contract from
the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}``, ``cap.world.reset.v1`` takes
``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The environment is simulated (R0): it has no hardware
backend, no e-stop path to a machine and no operator-required limit.

The upstream repository is not a standalone package: its files are meant to be copied into ManiSkill
(README.md:40-70) and it needs ManiSkill 3.x and SAPIEN 3.x (README.md:7-8).  Those are not installed where the
gate runs, and package code never imports the clone.  The ``fake`` backend is therefore the package's own task-level
Python model of ``ArrayCanEnv`` (fake.py): it models the five cans, the placement region, the success predicate and
the reaching reward, but not the Panda arm, contacts or physics.  The upstream environment inherits ``reset``,
``step``, ``action_space`` and ``observation_space`` from ManiSkill's ``BaseEnv``, which is external to the clone;
the fake does not invent those spaces, so the step action is an open object and the driver's fidelity ``gaps`` and
RESULT.json record that the full action and observation arrays are not covered.  A backend name that ``backends``
does not list (``sim``) would be served by ``gymnasium.make("ArrayCan-v1")`` only after the upstream files are
copied into ManiSkill; that path needs ManiSkill and was not run here.

The ``fidelity`` attribute is the contract of the model as deployed (spec 05-fidelity FID-002): the fake is a
kinematic task model with no dynamics (F0), a zero simulated timestep because the clone does not state ManiSkill's
control period, and explicit gaps.  Every fact cites a line of the clone at the pinned commit
(615098ccc37f2af4e7e1a1ed2d705c5fef279c23).  This package is model-authored and unreviewed: it is checked on the
fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "envs/array_can.py"


class ArrayCan(GymnasiumDriver):
    device_id = "array-can"
    env_id = "ArrayCan-v1"
    native = "envs.array_can:ArrayCanEnv"
    backends = {"fake": ".fake:FakeArrayCanEnv"}
    display_name = "ManiSkill ArrayCan-v1 (can arraying)"
    vendor, model = "chanjin926", "ArrayCan-v1"
    tags = ["arraycan", "maniskill", "sapien", "tabletop", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("ArrayCan-v1 is registered with max_episode_steps=50", source="upstream_code", ref=f"{ENV}:21"),
        Fact("The default robot is panda_wristcam, the initial joint-position noise is 0.02, and the task holds 5 "
             "cans", source="upstream_code", ref=f"{ENV}:27-30"),
        Fact("The supported robots are panda_wristcam, panda and fetch", source="upstream_code", ref=f"{ENV}:23"),
        Fact("The can model is scaled by 0.03 with radius 1 m and height 3.5 m", source="upstream_code",
             ref=f"{ENV}:52-54"),
        Fact("Each can has mass 0.5", source="upstream_code", ref=f"{ENV}:59"),
        Fact("The can xy positions start from torch.rand((b, 2)) * 0.26 - 0.13 and are sampled in the region "
             "[-0.15, -0.15] to [0.15, 0.15]", source="upstream_code", ref=f"{ENV}:85-86"),
        Fact("Equal spacing passes when at least one of the two smallest pairwise distance gaps is at most 0.01",
             source="upstream_code", ref=f"{ENV}:111-114"),
        Fact("The linear arrangement is tested only for 3 cans, with an area tolerance of 0.001",
             source="upstream_code", ref=f"{ENV}:116-124"),
        Fact("Success requires equal spacing, a linear arrangement and no grasped can", source="upstream_code",
             ref=f"{ENV}:128-131"),
        Fact("The dense reaching reward is 2 * (1 - tanh(5 * min_dist)) from the TCP to the nearest can",
             source="upstream_code", ref=f"{ENV}:153-161"),
        Fact("When obs_mode contains state the observation adds the TCP pose, each can pose, the TCP-to-can and "
             "the can-to-can position vectors", source="upstream_code", ref=f"{ENV}:140-150"),
        Fact("The base camera is 512x512 with a pi/2 field of view, near plane 0.01 and far plane 100",
             source="upstream_code", ref=f"{ENV}:36"),
        Fact("The robot base is placed at [-0.615, 0, 0]", source="upstream_code", ref=f"{ENV}:44"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The contract of the model as deployed (spec 05-fidelity section 2).  The fake is kinematic, so F0; the
    #: timestep is 0 because the clone does not state ManiSkill's control period, and the gaps say what is absent.
    fidelity = {
        "engine": "ManiSkill:SAPIEN/ArrayCan-v1",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the fake's initial can positions; the fake is "
                     "deterministic for one seed, but it draws with Python's random.Random while ManiSkill draws "
                     "with torch's RNG, so a seed gives different coordinates on the two",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "no rigid-body dynamics, contacts, actuator or sensor model: the fake only tracks can xy positions "
            "and the task score; the SAPIEN scene, the Panda arm and gripper, collisions and the mplib planner "
            "are not modelled",
            "the action space and observation arrays are inherited from ManiSkill's BaseEnv and the Panda agent, "
            "which are external to the clone; the fake exposes neither space, so the step action is accepted as "
            "an open object with no shape or bounds (NOT COVERED: the full action and observation arrays and the "
            "camera images)",
            "the can placement uses uniform sampling with rejection in the declared region; upstream uses "
            "ManiSkill's UniformPlacementSampler and torch's RNG, so one seed gives different coordinates",
            "timestep_ms is 0 because the clone does not state ManiSkill's control timestep; ticks count fake "
            "transitions, not simulated seconds",
            "no rendering and no snapshots; the fake was never compared with the upstream environment because "
            "ManiSkill and SAPIEN were not installed where the gate ran",
        ],
    }
