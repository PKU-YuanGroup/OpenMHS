"""OpenMHS driver for gh.leggedrobotics/nav-suite: the depth-navigation Gymnasium task (a Gymnasium family driver).

A GymnasiumDriver is configuration only: ``env_id`` names the registered task and the bridge derives the contract
from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action ``{values}`` of three
numbers (the SE2 velocity command ``[vx, vy, omega]``), ``cap.world.reset.v1`` takes ``{seed, options}`` and
``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0): there is no hardware backend, no e-stop path to a
machine and no operator-required limit.

The card's entry symbol is the environment configuration class ``NavTasksDepthNavEnvCfg`` (env_cfg_base.py:394); the
registered environment itself is ``isaaclab.envs:ManagerBasedRLEnv`` (configs/__init__.py:10-32), which lies outside
the clone.  The card names the configuration class, so it is the ``native`` symbol the gate checks; the fake
implements the Gymnasium environment interface that the family's bridge calls.

The gate cannot run the Linux/Isaac Sim stack or the git-lfs assets the task needs (README.md:3-6 and :99-117), so
the ``fake`` backend is the package's own pure Python kinematic model (see fake.py).  A backend name that
``backends`` does not list (``sim``) is served by ``gymnasium.make(env_id)`` (GymnasiumDriver.open_native); that path
needs the Isaac Lab stack and was not run here.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002):
the deployed fake is a kinematic SE2 model, not the Isaac Lab physics simulation.  Every constant and rule cites a
line of the clone at the pinned commit (648ba3b28dac61aec48e150a507c2a8507646ea2).  This package is model-authored
and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

CFG = "exts/nav_tasks/nav_tasks/configs/env_cfg_base.py"
REG = "exts/nav_tasks/nav_tasks/configs/__init__.py"
ACTION_CFG = "exts/nav_tasks/nav_tasks/mdp/actions/navigation_actions_cfg.py"


class NavSuiteDepthNavigation(GymnasiumDriver):
    device_id = "nav-suite-depth-nav"
    env_id = "NavTasks-DepthImgNavigation-PPO-Anymal-D-DEV"
    native = "nav_tasks.configs.env_cfg_base:NavTasksDepthNavEnvCfg"
    backends = {"fake": ".fake:FakeNavTasksEnv"}
    display_name = "nav-suite depth navigation (Anymal D, Isaac Lab)"
    vendor, model = "leggedrobotics", "nav-suite"
    tags = ["navigation", "depth", "anymal", "isaac-lab", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("The suite registers three Gymnasium task ids whose entry point is isaaclab.envs:ManagerBasedRLEnv",
             source="upstream_code", ref=f"{REG}:10-32"),
        Fact("The DEV task id NavTasks-DepthImgNavigation-PPO-Anymal-D-DEV uses NavTasksDepthNavEnvCfg_DEV",
             source="upstream_code", ref=f"{REG}:10-17"),
        Fact("NavTasksDepthNavEnvCfg is a ManagerBasedRLEnvCfg subclass", source="upstream_code",
             ref=f"{CFG}:393-394"),
        Fact("The scene robot is ANYMAL_D_CFG at the prim path {ENV_REGEX_NS}/Robot", source="upstream_code",
             ref=f"{CFG}:72-73"),
        Fact("The high-level action term velocity_command is a NavigationSE2ActionCfg", source="upstream_code",
             ref=f"{CFG}:128-134"),
        Fact("NavigationSE2ActionCfg has action_dim 3 (vx, vy, omega) and clip_mode none, so the action is not "
             "clipped", source="upstream_code", ref=f"{ACTION_CFG}:44-52"),
        Fact("The simulation timestep is 0.005 s", source="upstream_code", ref=f"{CFG}:417"),
        Fact("The high-level planner runs at 10 Hz and decimation is int(200 / 10) = 20, so one environment step "
             "advances 0.1 s", source="upstream_code", ref=f"{CFG}:424-428"),
        Fact("The episode length is 20 s", source="upstream_code", ref=f"{CFG}:422"),
        Fact("The reset event randomizes the base yaw over (-3.0, 3.0)", source="upstream_code",
             ref=f"{CFG}:194-200"),
        Fact("The reset event sets the joint position and velocity ranges to (0.0, 0.0)", source="upstream_code",
             ref=f"{CFG}:202-209"),
        Fact("The timeout termination uses max_speed 1.0 and safety_factor 4.0", source="upstream_code",
             ref=f"{CFG}:286-293"),
        Fact("The goal_reached termination requires 2.0 s within distance 0.5, angle 0.3 and speed 0.6",
             source="upstream_code", ref=f"{CFG}:295-304"),
        Fact("Contact of the base or of a thigh, hip or shank with the environment terminates the episode",
             source="upstream_code", ref=f"{CFG}:306-322"),
        Fact("The policy observation group concatenates base linear and angular velocity, joint positions and "
             "velocities, goal commands and an embedded depth image, with corruption disabled",
             source="upstream_code", ref=f"{CFG}:170-183"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "isaaclab:NavTasks-DepthImgNavigation-PPO-Anymal-D-DEV (fake: analytic kinematics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the fake's initial yaw and the integration is "
                     "deterministic, so one implementation repeats a trajectory for the same seed and actions; the "
                     "upstream reset uses the Isaac Lab/torch random generators and this package's fake uses "
                     "Python's random.Random, so a seed gives different trajectories on the two",
        },
        "timestep_ms": 100.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "Isaac Sim 4.5, Isaac Lab 2.1, a GPU and the git-lfs policy and terrain assets are not available where "
            "the gate runs; the fake backend is a pure-Python kinematic SE2 model with no dynamics (no rigid-body "
            "motion, contacts, friction, actuator or sensor model), not the physics simulation, and it was never "
            "compared with an upstream run",
            "the observation is the planar pose [x, y, yaw] only; the upstream policy group concatenates base "
            "velocities, joint positions and velocities, goal commands and an embedded depth image, so the image "
            "and the joint state are not covered",
            "the registered task is vectorized (the DEV config sets num_envs 2); the fake serves one unbatched "
            "environment, and its reward is 0 every step because the upstream reward terms are not modelled",
            "the fake truncates at 200 steps (episode_length_s 20 s divided by the 0.1 s step) and does not model "
            "the proportional timeout, the goal_reached or the base/leg contact terminations",
            "the reset yaw draw uses Python's random.Random and the upstream event uses the Isaac Lab/torch random "
            "generators, so a seed does not give the same trajectory on the two",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms only",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
        ],
    }
