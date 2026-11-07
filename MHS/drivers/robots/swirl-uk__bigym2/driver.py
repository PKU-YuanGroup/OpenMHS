"""OpenMHS driver for gh.swirl-uk/bigym2: the BiGym 2.0 G1 drawer task as a Gymnasium family driver.

The card names the family ``mujoco`` and the helper ``MujocoDriver``, but the card's confirmed entry symbol is
``bigym.loco.gym_adapter:GymnasiumEnv``, a ``gymnasium.Env`` view of the controller-in-the-loop ``bigym.loco``
environment.  A MuJoCo family driver would bind the raw model (qpos/qvel/ctrl), not this class's
reset/step/action_space/observation_space interface, so this package uses a ``GymnasiumDriver`` and serves the
``cap.world.step.v1``, ``cap.world.reset.v1`` and ``cap.world.seed.v1`` classes derived from the environment's
spaces.  See RESULT.json notes for the deviation from the card.

The package exposes one registered task of the card's entry classes, ``drawer_top_open`` (``DrawerTopOpenG1``).
The upstream adapter does not register an environment with ``gymnasium.make``: ``make_gym(task_name)`` builds
``GymnasiumEnv(make(task_name, ...))``, so ``env_id`` is not set.  The gate cannot import the upstream package (it
needs MuJoCo, dm-env and the rest of pyproject.toml), and package code never imports the clone, so the fake backend
is the package's own kinematic stand-in (fake.py); the upstream simulator path was not run.

Every fact cites a line of the clone at the pinned commit f1b846216b3f985d8640e5703112980de05c0d22.  The fidelity
contract describes the model as deployed: the fake backend is kinematic (F0), with the documented gaps.  This
package is model-authored and unreviewed; it is checked on the fake backend only, which is served as mode
``simulated`` with evidence ``contract_checked``.
"""

from mhs.driver import Fact, GymnasiumDriver

ADAPTER = "bigym/loco/gym_adapter.py"
ENV = "bigym/loco/env.py"
CONFIG = "bigym/loco/config.py"
TASKS = "bigym/loco/tasks.py"
G1 = "bigym/robots/configs/g1.py"
MODEL = "bigym/envs/xmls/g1/g1_29dof_with_dex1_1.xml"


class BiGym2(GymnasiumDriver):
    """BiGym 2.0 ``drawer_top_open`` (G1 humanoid) behind the gymnasium bridge, fake backend only."""

    device_id = "bigym2-drawer-top-open"
    native = "bigym.loco.gym_adapter:GymnasiumEnv"
    backends = {"fake": ".fake:FakeGymnasiumEnv"}
    display_name = "BiGym 2.0 DrawerTopOpenG1 (G1 humanoid manipulation)"
    vendor, model = "swirl-uk", "BiGym 2.0 / drawer_top_open"
    tags = ["bigym2", "humanoid", "manipulation", "mujoco", "simulation", "reinforcement-learning", "gymnasium"]
    facts = [
        Fact("GymnasiumEnv is the gymnasium.Env view of a bigym.loco controller-in-the-loop environment; the "
             "adapter owns no physics and reports everything from the wrapped environment",
             source="upstream_code", ref=f"{ADAPTER}:16-19"),
        Fact("make_gym(task_name) builds GymnasiumEnv(make(task_name, config, **overrides)); it does not call "
             "gymnasium.make", source="upstream_code", ref=f"{ADAPTER}:305-322"),
        Fact("The action space is a Box that copies the wrapped environment's low, high and shape",
             source="upstream_code", ref=f"{ADAPTER}:104-112"),
        Fact("step casts the action to float32, reshapes it to the action space and clips it into the action space "
             "before stepping the environment", source="upstream_code", ref=f"{ADAPTER}:160-164"),
        Fact("The observation space is a Dict with an rgb uint8 0..255 field and a state float32 field",
             source="upstream_code", ref=f"{ADAPTER}:91-102"),
        Fact("reset(seed=s) passes the seed to the wrapped environment; a reset without a seed draws one from the "
             "adapter's np_random", source="upstream_code", ref=f"{ADAPTER}:139-150"),
        Fact("A step returns terminated = last and discount == 0, and truncated = last and not terminated",
             source="upstream_code", ref=f"{ADAPTER}:166-170"),
        Fact("The observation returned by reset and step is a dict with rgb and state arrays",
             source="upstream_code", ref=f"{ADAPTER}:270-276"),
        Fact("The render metadata is render_fps = round(1 / control_step_seconds)",
             source="upstream_code", ref=f"{ADAPTER}:117-119"),
        Fact("The step info carries success, fell, event_progress and discount, and a terminal step adds "
             "termination and truncation_reason", source="upstream_code", ref=f"{ADAPTER}:278-293"),
        Fact("The default camera keys are head, right_wrist and left_wrist",
             source="upstream_code", ref=f"{CONFIG}:33"),
        Fact("The default state keys are proprioception, proprioception_grippers and proprioception_floating_base",
             source="upstream_code", ref=f"{CONFIG}:34-38"),
        Fact("The episode budget is in inner environment steps and one outer control step is demo_down_sample_rate "
             "inner steps; the default 10 is 50 Hz", source="upstream_code", ref=f"{CONFIG}:138-141"),
        Fact("The default camera shape is 84x84 and the default frame_stack is 1",
             source="upstream_code", ref=f"{CONFIG}:154-164"),
        Fact("The outer action dimension is the outer base slots plus the selected limb actuators plus the gripper "
             "count", source="upstream_code", ref=f"{ENV}:921-923"),
        Fact("The outer action space is Box(-1, 1) over the computed action dimension",
             source="upstream_code", ref=f"{ENV}:1004-1009"),
        Fact("The low-dim observation length is summed over the configured state keys and frame-stacked",
             source="upstream_code", ref=f"{ENV}:1011-1039"),
        Fact("The rgb observation space is uint8 0..255 with shape (num_cameras, 3 * frame_stack, H, W)",
             source="upstream_code", ref=f"{ENV}:1048-1056"),
        Fact("The task drawer_top_open is registered with DrawerTopOpenG1 and a 13500-step budget",
             source="upstream_code", ref=f"{TASKS}:158"),
        Fact("The default robot is the Unitree G1 with Dex1-1 parallel two-finger grippers",
             source="upstream_code", ref=f"{G1}:237-238"),
        Fact("The G1 MJCF is bigym/envs/xmls/g1/g1_29dof_with_dex1_1.xml with model name g1_29dof_with_dex1_1",
             source="upstream_code", ref=f"{MODEL}:1"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: Fidelity of the model as deployed (spec 05-fidelity): the fake backend is a kinematic stand-in, not a
    #: physics re-implementation, so the claim is F0.  The timestep is the upstream outer control step (50 Hz).
    fidelity = {
        "engine": "bigym2:gym_adapter (fake backend: kinematic stand-in for the MuJoCo bigym.loco environment)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) pins the fake's initial state and the fake advances it deterministically; the "
                     "upstream environment draws its episode seed from numpy and simulates with MuJoCo, so one "
                     "seed does not give the same trajectory on the fake and upstream",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic fake: the fake backend advances a placeholder state directly and models no rigid-body "
            "dynamics, contacts, actuators, sensors or noise; the upstream bigym.loco environment is a MuJoCo "
            "rigid-body simulation (bigym/envs/xmls/g1/g1_29dof_with_dex1_1.xml:1) and was not run here",
            "the fake observation is a 3-channel 4x4 rgb placeholder plus a 12-value state; the upstream default "
            "rgb observation is 3 cameras x 3 channels x 84x84 uint8 and the state length is summed over the "
            "configured state keys (bigym/loco/config.py:33,154-156,164; bigym/loco/env.py:1011-1056)",
            "the fake action vector is 24 placeholder values; the upstream action length is computed from the "
            "robot's selected actuators and the controller (bigym/loco/env.py:921-923,1004-1009)",
            "no rendering: the fake implements no render() and returns no image",
            "no wall-clock pacing: realtime_factor 0 and ticks advance simulated time by timestep_ms only",
            "the fake was not compared with the upstream environment: the upstream package is not installed where "
            "the gate runs and package code never imports the clone",
            "snapshot and restore are not offered: the fake exposes no get_state/set_state",
        ],
    }
