"""OpenMHS driver for gh.lightwheelai/leisaac: the LeIsaac SO101 PickOrange Direct task.

The card names the in-tree Gymnasium environment
``leisaac.tasks.pick_orange.direct.pick_orange_env:PickOrangeEnv``.  It is a
concrete direct-workflow task (it implements ``_get_observations`` and
``_check_success``), so the Gymnasium family is the right shape: the bridge
derives ``cap.world.step.v1``, ``cap.world.reset.v1`` and
``cap.world.seed.v1`` from the environment's action and observation spaces.

The upstream environment is an Isaac Lab / Isaac Sim GPU environment: its base
class lives in the ``dependencies/IsaacLab`` submodule and its assets need the
external simulator stack.  The gate cannot import or run it, and package code
never imports the clone, so the ``fake`` backend is the package's own analytic
F0 stand-in (``fake.py``).  Only that backend is declared.  The inherited
``gymnasium.make(env_id)`` fallback is not a supported live adapter: the upstream
needs application bootstrap, cfg, registration and torch/batch adaptation, and
its declared observation space differs from its returned observations.

The driver is simulated and R0: the upstream catalogue classes
``cap.world.*`` are simulation-only and the fake has no physical effect.
``safe_state`` is the runtime's software latch; there is no hardware stop to
declare.  This package is model-authored and unreviewed.
"""

from mhs.driver import Fact, GymnasiumDriver

#: Source paths in the clone at 24d3bcd3f1e4585740fc79921782c41617237812.
REGISTER = "source/leisaac/leisaac/tasks/pick_orange/__init__.py"
ENV = "source/leisaac/leisaac/tasks/pick_orange/direct/pick_orange_env.py"
SINGLE_ARM = "source/leisaac/leisaac/tasks/template/direct/single_arm_env.py"
SINGLE_ARM_CFG = "source/leisaac/leisaac/tasks/template/single_arm_env_cfg.py"
TERMINATIONS = "source/leisaac/leisaac/tasks/pick_orange/mdp/terminations.py"
CONSTANTS = "source/leisaac/leisaac/utils/constant.py"
ENHANCE_ENV = "source/leisaac/leisaac/enhance/envs/direct_rl_env.py"
ENHANCE_CFG = "source/leisaac/leisaac/enhance/envs/direct_rl_env_cfg.py"
ISAAC_ENV = "dependencies/IsaacLab/source/isaaclab/isaaclab/envs/direct_rl_env.py"
ISAAC_SIM = "dependencies/IsaacLab/source/isaaclab/isaaclab/sim/simulation_cfg.py"
PYPROJECT = "source/leisaac/pyproject.toml"


class LeIsaacPickOrange(GymnasiumDriver):
    device_id = "leisaac-so101-pickorange"
    device_kind = "world.sim"
    env_id = "LeIsaac-SO101-PickOrange-Direct-v0"
    native = "leisaac.tasks.pick_orange.direct.pick_orange_env:PickOrangeEnv"
    backends = {"fake": ".fake:FakePickOrangeEnv"}
    display_name = "LeIsaac SO101 PickOrange Direct (Isaac Lab simulation)"
    vendor, model = "Lightwheel AI", "LeIsaac-SO101-PickOrange-Direct-v0"
    tags = ["leisaac", "isaaclab", "so101", "pick-orange", "manipulation", "reinforcement-learning",
            "simulation", "gymnasium"]
    facts = [
        Fact("LeIsaac registers LeIsaac-SO101-PickOrange-Direct-v0 with entry point "
             "leisaac.tasks.pick_orange.direct.pick_orange_env:PickOrangeEnv and config "
             "PickOrangeEnvCfg", source="upstream_code", ref=f"{REGISTER}:21-27"),
        Fact("PickOrangeEnv is a concrete direct task: it adds six subtask observations and implements "
             "_check_success with mdp.task_done", source="upstream_code", ref=f"{ENV}:61-90"),
        Fact("The single-arm direct task declares action_space = 6", source="upstream_code",
             ref=f"{SINGLE_ARM}:33"),
        Fact("IsaacLab converts an integer space specification to Box(low=-inf, high=inf, shape=(spec,))",
             source="upstream_code", ref="dependencies/IsaacLab/source/isaaclab/isaaclab/envs/utils/spaces.py:30-32"),
        Fact("The single-arm joint order is shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll, "
             "gripper", source="upstream_code", ref=f"{CONSTANTS}:27"),
        Fact("Each action is multiplied by the configured action_scale and written as the robot joint position "
             "target", source="upstream_code", ref=f"{SINGLE_ARM}:129-134"),
        Fact("The direct task sets action_scale = 1.0", source="upstream_code", ref=f"{SINGLE_ARM}:49"),
        Fact("The base observation_space dictionary declares joint_pos (6), actions (6) and joint_pos_target (6)",
             source="upstream_code", ref=f"{SINGLE_ARM}:33-47"),
        Fact("The front and wrist cameras are 640 x 480 RGB cameras", source="upstream_code",
             ref=f"{SINGLE_ARM_CFG}:50-83"),
        Fact("The policy observation group carries joint_pos, joint_vel, joint_pos_rel, joint_vel_rel, actions, "
             "ee_frame_state, joint_pos_target and the RGB camera images", source="upstream_code",
             ref=f"{SINGLE_ARM}:136-152"),
        Fact("PickOrangeEnv adds the six subtask_terms observations for picking and placing each orange",
             source="upstream_code", ref=f"{ENV}:66-83"),
        Fact("The direct env reward is 0.0", source="upstream_code", ref=f"{SINGLE_ARM}:154-155"),
        Fact("The episode times out when episode_length_buf >= max_episode_length - 1 unless never_time_out is set",
             source="upstream_code", ref=f"{SINGLE_ARM}:162-165"),
        Fact("The direct task sets decimation = 1 and episode_length_s = 25.0", source="upstream_code",
             ref=f"{SINGLE_ARM}:64-65"),
        Fact("The default simulation timestep is 1/60 s", source="upstream_code", ref=f"{ISAAC_SIM}:346"),
        Fact("max_episode_length is ceil(episode_length_s / (sim.dt * decimation))", source="upstream_code",
             ref=f"{ISAAC_ENV}:264-267"),
        Fact("never_time_out, manual_terminate, auto_terminate and return_success_status default to False",
             source="upstream_code", ref=f"{ENHANCE_CFG}:14-20"),
        Fact("The task succeeds only when every orange is within x/y (-0.10, 0.10) and height (-0.07, 0.07) "
             "of the plate, and the arm is at its rest pose", source="upstream_code",
             ref=f"{TERMINATIONS}:14-56"),
        Fact("The reset signature is reset(seed=None, options=None)", source="upstream_code",
             ref=f"{ENHANCE_ENV}:117"),
        Fact("step takes a torch tensor, moves it to self.device and returns obs_buf, reward_buf, "
             "reset_terminated, reset_time_outs and extras", source="upstream_code",
             ref=f"{ENHANCE_ENV}:32-115"),
        Fact("step resets terminated or timed-out environments before collecting the returned observations",
             source="upstream_code", ref=f"{ENHANCE_ENV}:82-107"),
        Fact("SO101Leader constructs a FeetechMotorsBus with port=self.port and calls connect in its constructor",
             source="upstream_code", ref="source/leisaac/leisaac/devices/lerobot/so101_leader.py:36-51"),
        Fact("The pinned IsaacLab submodule states SPDX-License-Identifier BSD-3-Clause", source="vendor_doc",
             ref="dependencies/IsaacLab/LICENSE:1-5"),
        Fact("The upstream package requires Python >=3.10", source="upstream_code", ref=f"{PYPROJECT}:21"),
        Fact("The isaaclab extra pins isaaclab[isaacsim,all]==2.3.0", source="upstream_code",
             ref=f"{PYPROJECT}:41"),
    ]
    safe_state = ("the declared analytic fake stops advancing and keeps its state and cached targets readable; "
                  "no step or world reset is accepted while latched. mhs.safety.reset releases only the latch "
                  "and advances no ticks. No pause or stop of an external Isaac Sim application or serial "
                  "SO101Leader is provided; the serial device is outside this package")
    #: The model as deployed by the upstream simulator.  The fake backend replaces the engine, the level and
    #: the gaps below with the analytic F0 contract in ``fidelity_by_backend``.
    fidelity = {
        "engine": "isaaclab:LeIsaac-SO101-PickOrange-Direct-v0",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) seeds the Isaac Lab RNG; the fake uses Python's random.Random, so one seed "
                     "gives different trajectories on the two implementations",
        },
        "timestep_ms": 16.666666666666668,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "rigid-body Isaac Lab/PhysX dynamics with contacts; not validated here and never compared with "
            "the upstream run",
            "the environment needs Isaac Sim, the IsaacLab 2.3.0 extra and a GPU; neither the sim path nor the "
            "upstream package was run where this package was checked",
            "the native environment is vectorized with a leading num_envs dimension; the bridge serves one "
            "environment per device",
            "no snapshot or restore: the upstream environment exposes no get_state/set_state",
        ],
    }
    fidelity_by_backend = {
        "fake": {
            "engine": "analytic:LeIsaac-SO101-PickOrange-Direct-v0 fake backend",
            "fidelity_level": "F0",
            "determinism": {
                "kind": "seeded",
                "seed_control": "parameter",
                "notes": "reset(seed) selects Python's random.Random for the fake's initial joint offsets; the "
                         "upstream uses the Isaac Lab torch RNG and its object/camera domain randomization, so one "
                         "seed does not reproduce the upstream trajectory",
            },
            "timestep_ms": 16.666666666666668,
            "realtime_factor": 0,
            "clock": "lockstep",
            "reset": "full",
            "snapshot_restore": False,
            "gaps": [
                "analytic F0 model: the joints follow the commanded target directly; no rigid-body dynamics, "
                "contacts, friction, actuators, sensors, noise or domain randomization are modelled",
                "the fake returns 4 x 4 x 3 RGB arrays for the front and wrist cameras; the upstream cameras "
                "are 640 x 480 x 3 (source/leisaac/leisaac/tasks/template/single_arm_env_cfg.py:50-83) and no "
                "rendering is modelled",
                "the fake uses one environment and Python's random.Random; the upstream is vectorized with a "
                "leading num_envs dimension and uses the Isaac Lab torch RNG",
                "the fake never reports task success: terminated stays False; upstream terminates when all three "
                "oranges are in the plate ranges and the arm is at rest "
                "(source/leisaac/leisaac/tasks/pick_orange/mdp/terminations.py:47-56), which needs contacts the fake "
                "does not model",
                "the upstream observation_space is the cfg-derived dict (joint_pos, actions, joint_pos_target and the "
                "two cameras) while _get_observations returns a 'policy' dict plus 'subtask_terms'; the fake declares "
                "the structure it actually returns",
                "the observation is a small fixed-size stand-in: the real front and wrist image dimensions are "
                "640 x 480 x 3, and ee_frame_state, joint velocities and the per-orange subtask flags are "
                "placeholders",
                "no snapshot or restore: the fake exposes no get_state/set_state",
                "the upstream environment and the sim backend were not run; this package is checked on the fake "
                "backend only",
                "only fake is declared: the inherited generic gymnasium.make fallback is not a supported live "
                "adapter. It lacks task registration, cfg/application bootstrap and numpy-to-torch/batch "
                "adaptation (the native step calls action.to(self.device), enhance/envs/direct_rl_env.py:32-36); "
                "the upstream observation_space also differs from the observations it returns",
                "the native constructor owns a global SimulationContext and prints to stdout "
                "(dependencies/IsaacLab/source/isaaclab/isaaclab/envs/direct_rl_env.py:100-116); close clears "
                "callbacks and that global instance (:483-503), and reset can wait for textures without a timeout "
                "(enhance/envs/direct_rl_env.py:146-148). These lifecycle requirements are absent from the fake",
                "the fake resets the scene stand-in before returning timeout observations, as native step does "
                "(enhance/envs/direct_rl_env.py:82-107), while retaining the cached last action; its initial "
                "action buffer and reset joint jitter remain placeholders",
                "the upstream integer action specification creates an unbounded Box; the isolated R0 fake "
                "preserves that space. fixtures/operator-limits.example.json is an optional operator envelope "
                "for the fake, not a device limit or a required deployment default",
                "the repository also includes SO101Leader, which opens a serial motor bus from its constructor "
                "(devices/lerobot/so101_leader.py:20-51); it is never instantiated by this simulation contract",
            ],
        },
    }
