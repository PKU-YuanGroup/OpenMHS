"""OpenMHS driver for gh.leggedrobotics/sru-navigation-sim: the SRU Isaac Lab navigation environment (simulated R0).

The card's family is ``gymnasium`` and its entry symbol is the clone's ``NavigationEnv``
(``isaaclab_nav_task.navigation.navigation_env:NavigationEnv``, line 19), a concrete subclass of the external Isaac Lab
``ManagerBasedRLEnv`` that adds an observation delay manager.  ``Isaac-Nav-MDPO-AoW-D-v0`` is the registered training
task (``isaaclab_nav_task/navigation/config/aow_d/__init__.py:17-25``) used here.  The bridge serves the environment
through ``cap.world.step.v1``, ``cap.world.reset.v1`` and ``cap.world.seed.v1``; the action object is
``{"values": [vx, vy, omega]}``, because the clone's action term has ``action_dim = 3`` for ``[vx, vy, omega]``.

The real environment cannot run where the gate runs: it needs Isaac Lab v2.1.1, Isaac Sim 4.5 and a GPU
(``docs/README.md:64-69``, card ``install.gpu``), and this package never imports the clone.  The ``fake`` backend is
therefore an analytic F0 stand-in (``fake.py``) that models the task contract defined in the clone but not the
rigid-body dynamics, locomotion policy, depth sensor, delay buffer or reward of the Isaac Sim task.  Its action bounds
and observation sizes are placeholders and are disclosed in the fidelity ``gaps``; no ``sim`` backend is declared,
because a live backend would have to import and run the upstream task and Isaac Sim, which is outside this package.

Every Fact cites a line of the clone at commit 80f6c01c2d9f171374c9f9dba289abd38bcf0c6c.  This package is
model-authored and unreviewed (``driver.lock.json``): it is checked on the fake backend only, and fake evidence does
not establish an Isaac Sim, ROS or hardware run.
"""

from mhs.driver import Fact, GymnasiumDriver

NAV = "isaaclab_nav_task/navigation/navigation_env.py"
CFG = "isaaclab_nav_task/navigation/navigation_env_cfg.py"
AOW = "isaaclab_nav_task/navigation/config/aow_d/__init__.py"
ACTIONS = "isaaclab_nav_task/navigation/mdp/navigation/actions/navigation_se2_actions.py"
GOALS = "isaaclab_nav_task/navigation/mdp/navigation/goal_commands.py"
TERMS = "isaaclab_nav_task/navigation/mdp/terminations.py"
DOCS = "docs/README.md"


class SruNavigation(GymnasiumDriver):
    device_id = "sru-navigation-sim"
    env_id = "Isaac-Nav-MDPO-AoW-D-v0"
    native = "isaaclab_nav_task.navigation.navigation_env:NavigationEnv"
    backends = {"fake": ".fake:FakeNavigationEnv"}
    display_name = "SRU visual navigation (Isaac Lab, AoW-D)"
    vendor, model = "Robotic Systems Lab, ETH Zurich", "SRU navigation simulation"
    tags = ["navigation", "isaac-lab", "isaac-sim", "reinforcement-learning", "simulation", "gymnasium", "aow-d"]
    fidelity_level = "F0"
    facts = [
        Fact("NavigationEnv subclasses Isaac Lab's ManagerBasedRLEnv and creates an ObservationDelayManager before "
             "the other managers are loaded", source="upstream_code", ref=f"{NAV}:19-44"),
        Fact("Isaac-Nav-MDPO-AoW-D-v0 is registered with entry point isaaclab_nav_task.navigation:NavigationEnv and "
             "the AowDNavigationEnvCfg configuration", source="upstream_code", ref=f"{AOW}:17-25"),
        Fact("The task is hierarchical: a high-level policy emits SE2 velocity commands (vx, vy, omega) at 5 Hz and "
             "a pre-trained low-level locomotion policy converts them to joint actions at 50 Hz", source="vendor_doc",
             ref=f"{DOCS}:18-20"),
        Fact("The action term has action_dim 3 for [vx, vy, omega]", source="upstream_code", ref=f"{ACTIONS}:41-42"),
        Fact("The configured action path uses use_raw_actions=True, policy_scaling [1.5, 1.0, 1.0] and "
             "policy_distr_type 'gaussian'", source="upstream_code", ref=f"{CFG}:150-166"),
        Fact("With use_raw_actions=True the raw action is kept; gaussian processing applies tanh, adds "
             "the observed speed norm times policy_bias, then multiplies by policy_scaling",
             source="upstream_code", ref=f"{ACTIONS}:157-182"),
        Fact("PLANNING_FREQ is 5.0 Hz", source="upstream_code", ref=f"{CFG}:48"),
        Fact("The environment sets sim.dt = 0.005 s, decimation = int((1 / sim.dt) / PLANNING_FREQ), "
             "episode_length_s = 60.0 s and is_finite_horizon = True", source="upstream_code", ref=f"{CFG}:421-428"),
        Fact("The robot goal command is resampled only on episode reset: resampling_time_range is (1e9, 1e9)",
             source="upstream_code", ref=f"{CFG}:137-142"),
        Fact("The reset event samples the base yaw uniformly from (-pi, pi) and randomizes joint positions by scale "
             "0.5 to 1.5", source="upstream_code", ref=f"{CFG}:271-283"),
        Fact("The termination terms are time_out, base_contact (threshold 1.0), large_pitch_angle (threshold 40), "
             "early_termination at_goal (distance_threshold 0.5) and terrain_fall (fall_height_threshold -2.0)",
             source="upstream_code", ref=f"{CFG}:370-386"),
        Fact("time_out_navigation increments time_at_goal whenever the XY goal distance is below distance_threshold",
             source="upstream_code", ref=f"{TERMS}:61-64"),
        Fact("at_goal_navigation counts the current goal entry or any earlier entry with time_at_goal > 0, and "
             "terminates when the counter exceeds required_time_at_goal_in_steps", source="upstream_code",
             ref=f"{TERMS}:152-166"),
        Fact("required_steps_at_goal is 4.0 / env.step_dt", source="upstream_code", ref=f"{GOALS}:378"),
        Fact("The observation groups are metrics, policy, critic and low_level_policy", source="upstream_code",
             ref=f"{CFG}:247-251"),
        Fact("The raycast camera is downsampled from 192x120 to 64x40 and has max_distance 11.0",
             source="upstream_code", ref=f"{CFG}:85-105"),
        Fact("The simulator prerequisites are Isaac Lab v2.1.1, Isaac Sim 4.5.0, Python 3.10 and PyTorch >= 2.5.1",
             source="vendor_doc", ref=f"{DOCS}:64-69"),
        Fact("The repository excludes the rsl_rl learning module and the PPO/MDPO training algorithms",
             source="vendor_doc", ref=f"{DOCS}:6-16"),
        Fact("The two robot platforms are B2W (bipedal wheeled) and AoW-D (Anymal on Wheels)",
             source="vendor_doc", ref=f"{DOCS}:54-56"),
    ]
    safe_state = ("the declared analytic fake stops advancing and keeps its state readable; no step or world reset "
                  "is accepted while latched. mhs.safety.reset releases only the latch and advances no ticks. "
                  "No pause or stop of an external Isaac Sim application is provided")
    #: The fidelity contract of the model as deployed: an analytic F0 fake of the task contract, not a claim about
    #: the Isaac Sim environment.  The upstream engine, physics timestep and dynamics are outside this package.
    fidelity = {
        "engine": "analytic",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the analytic fake draws its reset yaw and goal from Python's random.Random(seed) and its "
                     "kinematics are deterministic, so a seed and an action sequence repeat a trajectory of this "
                     "fake; the upstream Isaac Sim environment's random number stream and physics are not reproduced",
        },
        "timestep_ms": 200.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "absence of dynamics: this is an F0 analytic stand-in with no rigid-body physics, contacts, friction, "
            "actuators, locomotion policy, depth raycasting, observation delay or domain randomization; none of the "
            "Isaac Sim behaviour of the upstream task is modelled, including the base_contact, large_pitch_angle "
            "and terrain_fall terminations",
            "the action bounds [-1, 1] and every observation size are the fake's placeholders: the real action and "
            "observation spaces are built by the external Isaac Lab ManagerBasedRLEnv and are not defined in the "
            "clone; only the 3-dimensional [vx, vy, omega] action layout and the four observation group names are "
            "sourced (navigation_se2_actions.py:42 and navigation_env_cfg.py:247-251)",
            "the observation groups are reduced stand-ins: the upstream policy and critic groups include a delayed "
            "depth image from the 64x40 raycast camera (navigation_env_cfg.py:85-105) and a height scan, and the "
            "low-level group includes joint positions and velocities; this fake returns 10, 12, 10 and 1 values per "
            "group and omits those terms, as recorded in RESULT.json notes",
            "the goal, reset pose and reward are stand-ins: upstream samples goals from terrain masks on reset "
            "(navigation_env_cfg.py:137-142), randomizes yaw and joints (navigation_env_cfg.py:271-283) and computes "
            "the reward from Isaac Lab physics terms (navigation_env_cfg.py:338-367); no trajectory or reward of "
            "this fake was compared with an upstream run",
            "no captured traffic or transcript is shipped in the clone, so this analytic fake is used instead of a "
            "recording; it was never compared with the upstream environment: Isaac Lab v2.1.1 and Isaac Sim 4.5 are "
            "not installed where the gate runs, and no sim backend was declared because a live backend would import "
            "and run the upstream task",
            "only the fake backend is declared: the inherited generic gymnasium.make fallback is not a supported "
            "live adapter. The shipped train.py parses argv, launches AppLauncher, registers tasks and supplies cfg "
            "before gym.make (scripts/train.py:35-60, :67-103); those application lifecycle and vectorized torch "
            "action/observation requirements are not implemented by this single-environment analytic contract",
            "the upstream goal counter keeps advancing after the first radius entry even after leaving the goal "
            "(terminations.py:62-65, :158-166); it is not a requirement to remain inside the radius for four seconds",
            "the fake uses the zero default policy_bias; it omits the upstream speed-dependent bias, low-pass "
            "filter and low-level policy path (navigation_se2_actions.py:176-182, :240)",
            "snapshot and restore are not offered: this fake exposes no get_state or set_state methods",
        ],
    }
