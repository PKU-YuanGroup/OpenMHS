"""OpenMHS driver for gh.cai23sbp/isaaclab_parkour: the Isaac Lab Extreme Parkour teacher task for a Unitree Go2.

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives the
contract from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with ``action.values``
shaped by the fake's single-environment ``Box`` space, ``cap.world.reset.v1`` takes ``{seed, options}`` and
``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0): there is no hardware backend, no e-stop path to a
machine and no operator-required limit.

The upstream environment is vectorized (``is_vector_env = True``, ``num_envs = 6144`` in the teacher task) and
requires Isaac Sim, Isaac Lab, ``isaaclab_assets`` and a GPU.  The acceptance gate cannot import or install those,
so the ``fake`` backend is the package's own pure Python stand-in for one environment of the task (fake.py).  A
backend name that ``backends`` does not list (``sim``) is served by ``gymnasium.make(env_id)``
(GymnasiumDriver.open_native); that path was not run here.

Every cited line is from the clone at the pinned commit d6766d8883cffe427f2d4c087717d4eca1f23d8c.  This package is
model-authored and unreviewed: it is checked on the fake backend only, and no fidelity claim is made about the
upstream simulator or a physical Unitree Go2.
"""

from mhs.driver import Fact, GymnasiumDriver

RL_ENV = "parkour_isaaclab/envs/parkour_manager_based_rl_env.py"
BASE_ENV = "parkour_isaaclab/envs/parkour_manager_based_env.py"
GO2_INIT = "parkour_tasks/parkour_tasks/extreme_parkour_task/config/go2/__init__.py"
TEACHER_CFG = "parkour_tasks/parkour_tasks/extreme_parkour_task/config/go2/parkour_teacher_cfg.py"
MDP_CFG = "parkour_tasks/parkour_tasks/extreme_parkour_task/config/go2/parkour_mdp_cfg.py"
RL_CFG = "parkour_tasks/parkour_tasks/extreme_parkour_task/config/go2/agents/parkour_rl_cfg.py"
OBSERVATIONS = "parkour_isaaclab/envs/mdp/observations.py"
TERMINATIONS = "parkour_isaaclab/envs/mdp/terminations.py"
JOINT_ACTIONS = "parkour_isaaclab/envs/mdp/parkour_actions/joint_actions.py"


class IsaacLabParkourTeacher(GymnasiumDriver):
    device_id = "unitree-go2-parkour-teacher"
    env_id = "Isaac-Extreme-Parkour-Teacher-Unitree-Go2-v0"
    native = "parkour_isaaclab.envs:ParkourManagerBasedRLEnv"
    backends = {"fake": ".fake:FakeParkourEnv"}
    # The fake's dimensions are placeholders; it does not copy the 6144-environment action space.
    display_name = "Isaac Lab Extreme Parkour teacher task (Unitree Go2)"
    vendor, model = "cai23sbp", "Isaac-Extreme-Parkour-Teacher-Unitree-Go2-v0"
    tags = ["unitree-go2", "quadruped", "parkour", "locomotion", "isaac-lab", "physx", "simulation", "gymnasium"]
    facts = [
        Fact("The teacher task is registered as gym id Isaac-Extreme-Parkour-Teacher-Unitree-Go2-v0 with entry_point "
             "parkour_isaaclab.envs:ParkourManagerBasedRLEnv and the UnitreeGo2TeacherParkourEnvCfg configuration",
             source="upstream_code", ref=f"{GO2_INIT}:18-24"),
        Fact("ParkourManagerBasedRLEnv is a vectorized Gymnasium environment: it sets is_vector_env = True",
             source="upstream_code", ref=f"{RL_ENV}:22-23"),
        Fact("The teacher scene configures 6144 environments with an environment spacing of 1.0",
             source="upstream_code", ref=f"{TEACHER_CFG}:34"),
        Fact("The teacher config sets decimation 4, an episode length of 20.0 s, a simulation timestep of 0.005 s and "
             "a render interval equal to the decimation", source="upstream_code", ref=f"{TEACHER_CFG}:48-52"),
        Fact("The shared ActionsCfg drives every robot joint (joint_names ['.*']) with scale 0.25 and the default joint "
             "offset, action_delay_steps [1, 1], an action history of 8 and a per-joint clip of (-4.8, 4.8)",
             source="upstream_code", ref=f"{MDP_CFG}:339-350"),
        Fact("The teacher configuration overrides joint_pos.use_delay to False and joint_pos.history_length to 1",
             source="upstream_code", ref=f"{TEACHER_CFG}:59-60"),
        Fact("The action term applies processed_actions as joint position targets", source="upstream_code",
             ref=f"{JOINT_ACTIONS}:33-35"),
        Fact("The action term clips raw actions then computes processed_actions as raw_actions * scale + offset",
             source="upstream_code", ref=f"{JOINT_ACTIONS}:50-54"),
        Fact("The policy configuration counts 53 proprioceptive values, 132 height scans, 9 privileged explicit "
             "values, 29 privileged latent values (4 + 1 + 12 + 12) and a history of 10",
             source="upstream_code", ref=f"{RL_CFG}:24-28"),
        Fact("ExtremeParkourObservations concatenates the 53-value proprioceptive vector, the 132 measured heights, "
             "the 9 privileged explicit values, the 29 privileged latent values and the flattened history buffer",
             source="upstream_code", ref=f"{OBSERVATIONS}:85-90"),
        Fact("The single action space is a Box(low=-inf, high=inf, shape=(action_dim,)) where action_dim is the sum "
             "of the action term dimensions; the environment then batches the observation and action spaces over "
             "num_envs", source="upstream_code", ref=f"{RL_ENV}:239-244"),
        Fact("The single observation space is a Dict of Box(low=-inf, high=inf) spaces shaped by the observation "
             "manager groups, batched over num_envs", source="upstream_code", ref=f"{RL_ENV}:224-243"),
        Fact("step processes the action, applies it over the configured decimation physics steps, computes "
             "terminations, rewards and resets, and returns (obs_buf, reward_buf, reset_terminated, reset_time_outs, "
             "extras)", source="upstream_code", ref=f"{RL_ENV}:95-165"),
        Fact("The terminate_episode function ORs roll/pitch cutoffs above 1.5 rad, a base-height cutoff below "
             "-0.25 m, episode-length exhaustion and goal-count exhaustion into reset_buf", source="upstream_code",
             ref=f"{TERMINATIONS}:32-42"),
        Fact("TerminationsCfg declares terminate_episode as a time_out=True term", source="upstream_code",
             ref=f"{MDP_CFG}:247-253"),
        Fact("The reset signature takes seed, env_ids and options and returns (observations, extras)",
             source="upstream_code", ref=f"{BASE_ENV}:152-184"),
        Fact("The demo launches the Omniverse application with AppLauncher and later constructs "
             "ParkourManagerBasedRLEnv(cfg=env_cfg)", source="upstream_code",
             ref="scripts/rsl_rl/demo.py:38-89"),
        Fact("The README installs the package inside an external IsaacLab checkout with pip3 install -e .",
             source="upstream_code", ref="README.md:13-25"),
        Fact("The repository LICENSE names GNU General Public License version 3", source="vendor_doc",
             ref="LICENSE:1-2"),
        Fact("The environment module carries an Isaac Lab Project Developers copyright and a BSD-3-Clause SPDX header",
             source="upstream_code", ref=f"{RL_ENV}:1-4"),
    ]
    safe_state = ("On the declared fake backend, the latch refuses step and reset until mhs.safety.reset clears it, "
                  "and the cached state stays readable. No native Isaac Sim pause or stop is provided; this latch "
                  "does not establish that an independently running Isaac timeline has stopped.")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the seeded determinism and the lockstep clock; the values below state the deployed teacher task and the
    #: placeholders of the package's fake.
    fidelity = {
        "engine": "analytic:single-environment parkour contract fake (no Isaac Sim/PhysX)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the seed of the next reset. The fake's only randomness "
                     "is Python's random.Random for the placeholder initial state, so the fake is reproducible for "
                     "a seed; the upstream simulator's determinism (PhysX, the event manager and 6144 environments) "
                     "was not run or established here.",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a hand-written stand-in, not a recording and not the Isaac Sim environment: its dynamics, "
            "observation values, reward, contacts, terrain and sensors are placeholders; the Box/Dict structure, "
            "nominal 20 ms control period and episode-length cutoff are derived from the clone; dimensions are "
            "single-environment placeholders and none of the "
            "roll, pitch, height or goal predicates is modelled",
            "the upstream environment is vectorized (is_vector_env = True, 6144 environments in the teacher config); "
            "the SDK Gymnasium bridge drives one environment, so the fake presents a single-environment view and "
            "keeps batched space shapes for num_envs = 1 but returns scalar rewards and flags. It omits the "
            "upstream tensor/vector returns and automatic per-environment reset; this is a fake-only contract",
            "the action dimension 12 is a placeholder: the action term drives every joint of the Unitree Go2 and the "
            "clone does not state the joint count; 12 is inferred from the 12 joint stiffness and 12 joint damping "
            "terms counted in parkour_rl_cfg.py:25 and is not a sourced dimension of the action space",
            "the upstream Gym action space is unbounded, but this package rejects raw actions outside the "
            "(-4.8, 4.8) clip interval before stepping: its fake Box is deliberately narrower and its derived "
            "bounds identify the fake backend, not the upstream Gym space. The clip values are separately cited "
            "at parkour_mdp_cfg.py:349. The fake uses absolute scale-0.25 position "
            "targets with placeholder zero default offsets and instantaneous tracking, not incremental motion; "
            "the teacher disables delay and uses a history of one",
            "the observation is a placeholder vector of 753 values: 53 + 132 + 9 + 29 + 10 * 53, from the policy "
            "configuration (parkour_rl_cfg.py:24-28) and the concatenation in observations.py:85-90; the values are "
            "not the simulator's observations",
            "no rendering, cameras, ray-cast height scanner, contact sensor, terrain generation, physics integration "
            "or manager computation is modelled",
            "only the fake backend is declared. The implicit gymnasium.make route is not a working live adapter: "
            "the native constructor requires cfg (parkour_manager_based_rl_env.py:30-32), its step expects a "
            "torch tensor (95-97) and returns vector rewards/flags (165), while this package supplies no cfg, "
            "device tensor conversion or scalar/vector adapter. Isaac Sim, a GPU, external assets and task "
            "registration are also required; the route was not run",
            "native construction creates a global SimulationContext, scene and managers, starts or reuses the "
            "timeline and prints to stdout (parkour_manager_based_env.py:40-141); reset may wait for asset "
            "loading without a timeout (180-182). No timeline pause/read-back or process isolation is provided",
            "the repository LICENSE is GPL-3.0, while the cited environment modules retain BSD-3-Clause Isaac Lab "
            "headers; no upstream code or assets are copied into this package",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
        ],
    }
