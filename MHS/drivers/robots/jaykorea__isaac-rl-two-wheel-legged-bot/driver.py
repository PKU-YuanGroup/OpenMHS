"""OpenMHS driver for gh.jaykorea/isaac-rl-two-wheel-legged-bot: the Flamingo velocity-flat Isaac Lab task.

A GymnasiumDriver is configuration only: ``env_id`` names the registered task and the bridge derives the whole
contract from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` where the action is the flat
``{values}`` array of the environment's ``Box`` action space, ``cap.world.reset.v1`` takes ``{seed, options}`` and
``cap.world.seed.v1`` takes ``{seed}``.  The device is simulated (R0): there is no hardware backend and no e-stop path
to a machine.

The upstream task is ``Isaac-Velocity-Flat-Flamingo-v1-ppo-constraint``, registered at
``lab/flamingo/tasks/constraint_based/locomotion/velocity/flamingo_env/__init__.py:22-30`` with the entry point named
by ``native``.  It needs Isaac Sim 4.5 and Isaac Lab 2.0.0 (README.md:3-5) and the task configuration is built by the
training script (``scripts/co_rl/train.py:117``).  The gate cannot install or import that stack, so the ``fake``
backend is the package's own pure Python interface stand-in (see fake.py): it reproduces the action, observation,
step and reset contract, not the Isaac Sim physics.  The fidelity ``gaps`` say exactly what is not modelled.

Every fact cites a line of the clone at the pinned commit d922cce9e07a8877c37e12b2cb39dfdcf34b9d40.  The package is
model-authored and unreviewed: it is checked on the fake backend only, and no hardware or simulator run is claimed.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV_REGISTRATION = "lab/flamingo/tasks/constraint_based/locomotion/velocity/flamingo_env/__init__.py"
ENV_CLASS = "lab/flamingo/isaaclab/isaaclab/envs/manager_based_constraint_rl_env.py"
TASK_CFG = ("lab/flamingo/tasks/constraint_based/locomotion/velocity/flamingo_env/flat_env/stand_drive/"
            "flat_env_stand_drive_cfg.py")
BASE_CFG = "lab/flamingo/tasks/constraint_based/locomotion/velocity/velocity_env_cfg.py"
CONSTRAINTS = "lab/flamingo/tasks/constraint_based/locomotion/velocity/mdp/constraints.py"


class FlamingoVelocityFlat(GymnasiumDriver):
    """The Flamingo velocity-tracking flat task with the constraint-manager workflow."""

    device_id = "flamingo-velocity-flat"
    env_id = "Isaac-Velocity-Flat-Flamingo-v1-ppo-constraint"
    native = "lab.flamingo.isaaclab.isaaclab.envs:ManagerBasedConstraintRLEnv"
    backends = {"fake": ".fake:FakeFlamingoVelocityFlatEnv"}
    display_name = "Isaac Lab Flamingo velocity flat constraint task"
    vendor, model = "jaykorea", "Isaac-Velocity-Flat-Flamingo-v1-ppo-constraint"
    tags = ["flamingo", "isaac-lab", "isaac-sim", "reinforcement-learning", "simulation", "gymnasium",
            "two-wheel-legged-bot"]
    facts = [
        Fact("Isaac-Velocity-Flat-Flamingo-v1-ppo-constraint is registered with entry point "
             "lab.flamingo.isaaclab.isaaclab.envs:ManagerBasedConstraintRLEnv and the FlamingoFlatEnvCfg "
             "configuration", source="upstream_code", ref=f"{ENV_REGISTRATION}:22-30"),
        Fact("The environment class is a Gymnasium Env for a vectorized manager-based workflow: "
             "ManagerBasedConstraintRLEnv(ManagerBasedEnv, gym.Env)", source="upstream_code",
             ref=f"{ENV_CLASS}:29-35"),
        Fact("The default action terms are six joint-position targets for the left/right hip, shoulder and leg "
             "joints with scale 2.0 and two wheel-velocity targets for the left/right wheel joints with scale 20.0, "
             "so the action has eight values", source="upstream_code", ref=f"{TASK_CFG}:36-52"),
        Fact("The action space is Box(low=-inf, high=inf) with shape (action_dim,) and the observation space is a "
             "Dict of Box(low=-inf, high=inf) groups, both batched over num_envs", source="upstream_code",
             ref=f"{ENV_CLASS}:327-348"),
        Fact("The flat velocity config defaults to 4096 parallel environments", source="upstream_code",
             ref=f"{BASE_CFG}:419"),
        Fact("The flat velocity config sets decimation 4 and sim.dt 0.005 s, so one environment step advances 20 ms "
             "of simulated time", source="upstream_code", ref=f"{BASE_CFG}:433-436"),
        Fact("The Flamingo velocity flat task sets episode_length_s to 20.0 s", source="upstream_code",
             ref=f"{TASK_CFG}:247-251"),
        Fact("max_episode_length is ceil(episode_length_s / step_dt), 1000 steps for 20 s at 20 ms per step",
             source="upstream_code", ref=f"{ENV_CLASS}:97-105"),
        Fact("The time_out constraint truncates the episode when episode_length_buf reaches max_episode_length",
             source="upstream_code", ref=f"{CONSTRAINTS}:59-61"),
        Fact("The base_contact constraint terminates on a contact force above 1.0 on base_link, hip, shoulder or "
             "leg bodies", source="upstream_code", ref=f"{TASK_CFG}:67-72"),
        Fact("The stack_policy observation group concatenates joint_pos, joint_vel, base_ang_vel, base_euler and "
             "actions terms in that order", source="upstream_code", ref=f"{BASE_CFG}:240-250"),
        Fact("step processes the action, runs the simulation for cfg.decimation steps, computes the constraint and "
             "reward buffers, resets terminated environments, computes observations and returns observations, "
             "rewards, reset_delta, reset_time_outs and extras", source="upstream_code", ref=f"{ENV_CLASS}:165-245"),
        Fact("The README targets Isaac Sim 4.5, Isaac Lab 2.0.0, Python 3.10 and Linux", source="vendor_doc",
             ref="README.md:3-6"),
        Fact("The package is installed with pip install -e . from the repository root", source="vendor_doc",
             ref="README.md:68-73"),
        Fact("The USD assets are not uploaded by git and must be unzipped manually under the assets folder",
             source="vendor_doc", ref="README.md:74-78"),
        Fact("The training script creates the task with gym.make(task, cfg=env_cfg, render_mode=...)",
             source="upstream_code", ref="scripts/co_rl/train.py:117"),
        Fact("The training script seeds the environment with env.seed(agent_cfg.seed)", source="upstream_code",
             ref="scripts/co_rl/train.py:162"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop no step or reset is accepted until "
                  "mhs.safety.reset clears the latch, and the world state stays readable")
    #: The contract of the model this package serves on the fake backend (spec 05-fidelity).  The upstream task is an
    #: Isaac Sim rigid-body simulation, but this package ships no sim backend and the fake models no dynamics, so the
    #: level is F0 and the gaps carry every omission.  The timestep is the task's control step (decimation x sim.dt).
    fidelity = {
        "engine": "isaaclab:Isaac-Velocity-Flat-Flamingo-v1-ppo-constraint",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed=...) and cap.world.seed.v1 set the seed of the next reset (scripts/co_rl/train.py:162 "
                     "seeds the upstream environment the same way). The fake's reduced state is deterministic; its "
                     "seed does not change the fixed initial observation. The upstream Isaac Sim environment was not "
                     "run here, so its own determinism is not claimed.",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is an interface stand-in: it models no rigid-body dynamics, contacts, actuator, sensor or "
            "noise model; the upstream task runs Isaac Sim 4.5 and Isaac Lab 2.0.0 (README.md:3-5), which this "
            "package does not install or run, and no simulator run is claimed",
            "the fake serves one environment with the 8-value action of the default FlamingoFlatEnvCfg and a "
            "28-value stack_policy observation, while the upstream spaces are batched over 4096 environments and "
            "its observation_space is a Dict of four groups (stack_policy, none_stack_policy, stack_critic, "
            "none_stack_critic); the other groups are not represented",
            "the fake's 28-value observation follows the stack_policy term order (joint position 6, joint velocity "
            "8, base angular velocity 3, base Euler 3, last action 8); every value except the last action is a fixed "
            "placeholder, and no robot pose, command, contact, height scan or reward is simulated",
            "the fake truncates at 1000 steps (20.0 s at 20 ms per step) and never terminates on contact: the "
            "base_contact constraint (threshold 1.0) and the terrain constraint are not modelled",
            "no snapshot or restore: the environment exposes no get_state/set_state and the fake offers none",
            "only the fake backend is declared; opening the registered task through gymnasium.make needs Isaac Sim, "
            "Isaac Lab and a task cfg, and was not run",
        ],
    }
