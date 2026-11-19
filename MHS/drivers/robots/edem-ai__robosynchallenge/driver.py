"""OpenMHS driver for gh.edem-ai/robosynchallenge: the ClickBell Gymnasium task environment.

ClickBellEnv is a task environment of RoboSynChallenge, a bimanual manipulation benchmark built on the external
EmbodiChain simulator.  The environment class registers the id ClickBell at click_bell.py:34, subclasses
EmbodiedEnv from the external embodichain package, and adds the ClickBell task state: the press depth of a button
articulation, a latched success flag and the task metrics.  ``step`` and both spaces are inherited from EmbodiedEnv;
the task's ``reset`` delegates to that base before clearing its success flag.  The external base implementation is
absent from the clone; the action configuration of the task declares 6 DoF
for each arm and one value for each gripper (14 values, ``configs/click_bell/action_config.json:2-56``), which the
replay helper calls the 14 active CobotMagic joints (``robosynchallenge/replay.py:158``).

The card names the GymnasiumDriver family and that fits the environment: the bridge serves ``cap.world.step.v1``
(the action is the environment's action space), ``cap.world.reset.v1`` and ``cap.world.seed.v1``.  The device is
simulated (R0): there is no hardware backend and no operator-required limit.  The fake backend is the package's own
analytic stand-in because EmbodiChain, dexsim, a CUDA/Vulkan GPU and the CobotMagic robot model are not available in
the gate and are not part of the clone; its action and observation spaces are placeholders (see the fidelity gaps).
A backend name that ``backends`` does not list (``sim``) is served by ``gymnasium.make("ClickBell")``
(GymnasiumDriver.open_native), which needs the upstream package imported for registration and a cfg built by the
EmbodiChain launcher; that path was not run here.

Every fact cites a line of the clone at the pinned commit 8818c82df5fa2522809b8105e7018950dcc9a9a8.  This package is
model-authored and unreviewed: it is checked on the fake backend only, and fake evidence establishes no upstream run.
"""

from mhs.driver import Fact, GymnasiumDriver

TASK = "robosynchallenge/tasks/click_bell/click_bell.py"
CONFIG = "configs/click_bell/random/gym_config.json"
ACTION_CONFIG = "configs/click_bell/action_config.json"


class ClickBell(GymnasiumDriver):
    device_id = "robosynchallenge-click-bell"
    env_id = "ClickBell"
    native = "robosynchallenge.tasks.click_bell.click_bell:ClickBellEnv"
    backends = {"fake": ".fake:FakeClickBellEnv"}
    display_name = "RoboSynChallenge ClickBell (EmbodiChain)"
    vendor, model = "EDEM-AI", "ClickBell"
    tags = ["robosynchallenge", "click-bell", "bimanual", "manipulation", "reinforcement-learning", "simulation",
            "gymnasium"]
    facts = [
        Fact("ClickBellEnv is registered as ClickBell with max_episode_steps=600", source="upstream_code",
             ref=f"{TASK}:34"),
        Fact("ClickBellEnv subclasses EmbodiedEnv, imported from the external embodichain package", source="upstream_code",
             ref=f"{TASK}:20-35"),
        Fact("ClickBellEnv.__init__ forwards cfg and keyword arguments to EmbodiedEnv and stores action_config when "
             "one is given", source="upstream_code", ref=f"{TASK}:37-42"),
        Fact("compute_task_state reads the button articulation's joint positions with get_qpos", source="upstream_code",
             ref=f"{TASK}:132-133"),
        Fact("The source comment describes button.urdf as a single prismatic joint with range [-0.005, 0.0]", source="upstream_code",
             ref=f"{TASK}:135"),
        Fact("press_depth is minus the button joint position", source="upstream_code", ref=f"{TASK}:137"),
        Fact("The ClickBell success threshold movement_threshold is 0.0048", source="upstream_code",
             ref=f"{TASK}:138"),
        Fact("The ClickBell success flag is latched within an episode with |= current_success", source="upstream_code",
             ref=f"{TASK}:142"),
        Fact("compute_task_state returns success, fail and the metrics press_depth and movement_threshold",
             source="upstream_code", ref=f"{TASK}:144-150"),
        Fact("is_task_success returns the latched success flag", source="upstream_code", ref=f"{TASK}:152-153"),
        Fact("reset clears the success flag for the reset ids, defaulting to every environment", source="upstream_code",
             ref=f"{TASK}:154-163"),
        Fact("ClickBellTest uses the smaller movement_threshold 0.004", source="upstream_code", ref=f"{TASK}:176"),
        Fact("The click-bell action configuration declares right_arm 6, left_arm 6, left_eef 1 and right_eef 1 action "
             "dimensions", source="upstream_code", ref=f"{ACTION_CONFIG}:2-56"),
        Fact("The documentation states that an arm action dimension is 6 DoF and a gripper action dimension is 1",
             source="vendor_doc", ref="docs/tutorials/configuration.md:319"),
        Fact("The legacy replay format stores the robot's 14 active CobotMagic joints", source="upstream_code",
             ref="robosynchallenge/replay.py:158"),
        Fact("The click-bell random protocol sets max_episode_steps to 361", source="vendor_doc",
             ref=f"{CONFIG}:4"),
        Fact("The click-bell random protocol sets control_freq to 25", source="vendor_doc",
             ref=f"{CONFIG}:243"),
        Fact("The evaluation launcher passes the resolved max_episode_steps to gym.make", source="upstream_code",
             ref="scripts/eval_policy.py:468-472"),
        Fact("The observation configuration modifies the robot/qpos observation at joint ids 6 and 13",
             source="upstream_code", ref=f"{CONFIG}:225-232"),
        Fact("The OpenPI CLI defaults state_key to robot/qpos and image_key to color",
             source="upstream_code", ref="scripts/eval_openpi0_embodichain.py:277-278"),
        Fact("The released evaluation records ClickBell success rates for the simulation checkpoints",
             source="vendor_doc", ref="evaluation_results/released_checkpoint_results.json:37-43"),
        Fact("prepare_episode_reset seeds Python random, NumPy and Torch; its docstring says EmbodiChain's "
             "reset(seed) seeds Torch only", source="upstream_code", ref="scripts/eval_policy.py:301-315"),
    ]
    safe_state = ("on the fake backend the software latch refuses step, reset and seed until mhs.safety.reset; "
                  "the cached world state stays readable and reset of the latch does not advance it; "
                  "no native stop or halted EmbodiChain simulator is established")
    #: The fidelity contract of the model as deployed (spec 05-fidelity FID-002).  The fake is an analytic contract
    #: stand-in with no dynamics, so the level is F0; every placeholder is named in the gaps.
    fidelity = {
        "engine": "embodichain:robosynchallenge/ClickBell",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the package's fake seeds Python's random.Random from reset(seed) or cap.world.seed.v1 and "
                     "repeats its placeholder start state for a seed; upstream reset(seed) seeds EmbodiChain, and the "
                     "evaluation also seeds Python random, NumPy and Torch (scripts/eval_policy.py:301-315), so the "
                     "upstream path is not reproduced; neither path was compared",
        },
        "timestep_ms": 40.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is an analytic contract stand-in for ClickBellEnv: it has no CobotMagic robot, no "
            "EmbodiChain/dexsim physics, no contacts, no camera and no torch, so it cannot move the button "
            "(press_depth stays 0 and is_task_success stays false); its action-to-observation transition and reset "
            "jitter are placeholders, not robot motion",
            "the fake action space is a placeholder Box(-1, 1) with 14 values: the real space, its bounds and the "
            "joint order are defined by the external EmbodiChain EmbodiedEnv and the CobotMagic robot, which are not "
            "in the clone; action_space_ref is therefore unset and the derived bounds have no source",
            "the fake observation is a placeholder dict with only the robot/qpos key (14 values); the real "
            "observation is produced by the external base and includes camera streams (sensor/<camera>/color)",
            "the 14 action values come from the task's action_config and the replay helper, and the 361-step limit is "
            "the random protocol's max_episode_steps (configs/click_bell/random/gym_config.json:4); the class "
            "registration default is 600 (click_bell.py:34), and the fake uses the deployed protocol's 361",
            "the fake treats one tick as 40 ms from the random protocol's control_freq 25; the EmbodiChain physics "
            "timestep and control decimation are not stated in the clone, so this is a recording period, not a "
            "sourced physics timestep",
            "the fake reset accepts a seed but only draws a placeholder robot/qpos jitter with Python's "
            "random.Random; the upstream task randomizers and their seeds were not run or compared",
            "the upstream simulator and the sim backend (gym.make('ClickBell')) were not run: they need EmbodiChain "
            "v0.2.4.post1, dexsim, a CUDA/Vulkan GPU, the CobotMagic assets and a cfg built by the EmbodiChain "
            "launcher (docs/getting_started/installation.md:3-93); only the fake backend is declared and checked; "
            "the external base's construction, stepping and native-stop semantics are unverified",
            "snapshot and restore are not offered: the fake exposes no get_state/set_state and the bridge binds no "
            "cap.world.snapshot.v1",
        ],
    }
