"""OpenMHS driver for gh.sallu-786/go2_isaac_ros2: the Unitree Go2 Isaac Lab task (Gymnasium family driver).

The upstream repository is a simulation, not a hardware driver: ``Go2RSLEnvCfg`` configures an Isaac Lab
``ManagerBasedRLEnv`` (quadruped/go2/go2_env.py:139) and the application builds it with
``gym.make("Isaac-Velocity-Flat-Unitree-Go2-v0", cfg=cfg)`` (quadruped/go2/go2_ctrl.py:72, main.py:51).  This
GymnasiumDriver therefore declares the registered task id and serves ``cap.world.step.v1``, ``cap.world.reset.v1`` and
``cap.world.seed.v1`` through the gymnasium bridge.

Isaac Sim 4.5.0, Isaac Lab 2.1.0 or 2.1.1, ROS2 Humble and a GPU are external prerequisites (README.md:4-8 and
:41-43), so the gate cannot build the real environment: the only exercised backend is the package's kinematic fake
(fake.py), and the upstream simulator was not run here.  The device is simulated (mode ``simulated``, risk R0): it has
no physical effect and no hardware backend, and the only stop is the runtime's software latch.
"""

from mhs.driver import Fact, GymnasiumDriver

GO2_ENV = "quadruped/go2/go2_env.py"
GO2_CTRL = "quadruped/go2/go2_ctrl.py"


class Go2IsaacLab(GymnasiumDriver):
    """The Go2 flat-ground velocity task of quadruped/go2/go2_env.py behind the gymnasium bridge."""

    device_id = "go2-isaac"
    device_kind = "world.sim"
    env_id = "Isaac-Velocity-Flat-Unitree-Go2-v0"
    native = "quadruped.go2.go2_env:Go2RSLEnvCfg"
    backends = {"fake": ".fake:FakeGo2Env"}
    display_name = "Unitree Go2 Isaac Lab flat-ground task"
    vendor, model = "sallu-786", "Unitree Go2 / Isaac-Velocity-Flat-Unitree-Go2-v0"
    tags = ["isaac-sim", "isaac-lab", "unitree-go2", "quadruped", "reinforcement-learning", "simulation",
            "gymnasium"]
    facts = [
        Fact("The repository targets Isaac Sim 4.5.0 and Isaac Lab 2.1.0 or 2.1.1 on Ubuntu 22.04",
             source="vendor_doc", ref="README.md:4-8"),
        Fact("Isaac Sim 4.5.0, Isaac Lab 2.1.0 or 2.1.1 and ROS2 Humble are installed externally before the "
             "repository is used", source="vendor_doc", ref="README.md:41-43"),
        Fact("The documented run command is python main.py from the repository root", source="vendor_doc",
             ref="README.md:63-68"),
        Fact("The Go2 robot is the UNITREE_GO2_CFG articulation spawned at prim path {ENV_REGEX_NS}/Go2",
             source="upstream_code", ref=f"{GO2_ENV}:47"),
        Fact("Go2RSLEnvCfg subclasses ManagerBasedRLEnvCfg and is the environment configuration",
             source="upstream_code", ref=f"{GO2_ENV}:139"),
        Fact("The action term is a JointPositionActionCfg for asset unitree_go2 over joint_names ['.*']",
             source="upstream_code", ref=f"{GO2_ENV}:61-64"),
        Fact("The policy observation concatenates base_lin_vel, base_ang_vel, projected_gravity, base_vel_cmd, "
             "joint_pos, joint_vel, actions and height_scan", source="upstream_code", ref=f"{GO2_ENV}:74-94"),
        Fact("Projected gravity carries UniformNoiseCfg(n_min=-0.05, n_max=0.05)", source="upstream_code",
             ref=f"{GO2_ENV}:79-81"),
        Fact("The height_scan observation is clipped to (-1.0, 1.0)", source="upstream_code",
             ref=f"{GO2_ENV}:92-94"),
        Fact("The policy observation group sets enable_corruption=False and concatenate_terms=True",
             source="upstream_code", ref=f"{GO2_ENV}:96-98"),
        Fact("The height scanner uses a GridPatternCfg with resolution 0.1 and size [1.6, 1.0], offset 20 m above "
             "the base", source="upstream_code", ref=f"{GO2_ENV}:52-56"),
        Fact("The velocity command ranges are all zero: lin_vel_x, lin_vel_y, ang_vel_z and heading are (0, 0)",
             source="upstream_code", ref=f"{GO2_ENV}:106-113"),
        Fact("RewardsCfg and TerminationsCfg are empty pass classes, so the configuration declares no reward or "
             "termination terms", source="upstream_code", ref=f"{GO2_ENV}:120-129"),
        Fact("The environment uses decimation 8 and a simulation timestep of 0.005 s", source="upstream_code",
             ref=f"{GO2_ENV}:161-164"),
        Fact("The run loop derives its step period as sim.dt * decimation, 0.04 s for decimation 8 and sim.dt "
             "0.005 s", source="upstream_code", ref="main.py:93"),
        Fact("The configured episode length is 20.0 s and is_finite_horizon is False", source="upstream_code",
             ref=f"{GO2_ENV}:171-172"),
        Fact("The joint position action scale is 0.25", source="upstream_code", ref=f"{GO2_ENV}:173"),
        Fact("The application instantiates Go2RSLEnvCfg()", source="upstream_code", ref="main.py:51"),
        Fact("The run loop resets the environment with env.reset() and advances it with env.step(actions)",
             source="upstream_code", ref="main.py:94-104"),
        Fact("get_rsl_flat_policy builds the environment with gym.make('Isaac-Velocity-Flat-Unitree-Go2-v0', "
             "cfg=cfg)", source="upstream_code", ref=f"{GO2_CTRL}:70-73"),
    ]
    safe_state = ("the simulation is frozen: after an e-stop no step or reset is served until mhs.safety.reset "
                  "clears the latch, while the last observation stays readable")
    #: Fidelity of the model this package actually serves (fake.py, F0).  The upstream Isaac Lab environment runs
    #: PhysX rigid-body dynamics (F1 by spec 05-fidelity), but it cannot be built or validated here and this package
    #: never claims it ran.
    fidelity = {
        "engine": "isaaclab:Isaac-Velocity-Flat-Unitree-Go2-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake reseeds Python's random.Random on reset(seed) and is otherwise deterministic, so one "
                     "seed and one action sequence repeat a trajectory in this package; the upstream Isaac Lab "
                     "environment seeds its own numpy and torch generators and was not compared with the fake",
        },
        "timestep_ms": 40.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic stand-in only: no rigid-body dynamics, contacts, friction or PhysX; the upstream environment "
            "is an Isaac Sim 4.5.0 simulation (README.md:4-8) and none of that physics is modelled here",
            "the fake's action and observation widths and bounds are placeholders: the joint count comes from the "
            "external UNITREE_GO2_CFG articulation (go2_env.py:2,47) and the term widths from isaaclab mdp, neither "
            "stated in the clone; the real policy observation concatenates the eight terms of go2_env.py:74-94, "
            "while the fake returns a four-number summary",
            "the fake always returns reward 0, matching the empty RewardsCfg of go2_env.py:120-123, and never "
            "terminates or truncates (TerminationsCfg is empty and is_finite_horizon is False, go2_env.py:120-129 "
            "and :171-172); the 20 s episode length is declared but not enforced",
            "no rendering, camera, LIDAR, contact sensor, height scan, ROS2 topic or RSL-RL policy is modelled; the "
            "run loop's ROS2 bridge and checkpoint loading (main.py:77-88, go2_ctrl.py:70-83) are not part of the "
            "capabilities this driver serves",
            "the upstream environment was never run: Isaac Sim, Isaac Lab, ROS2 Humble and a GPU are external "
            "prerequisites (README.md:41-43); the sim backend (gymnasium.make of the registered task) was not "
            "exercised and would use the task's registered default config, because this family driver cannot pass a "
            "Go2RSLEnvCfg built from the clone without importing it",
            "snapshot and restore are not offered: the fake exposes no get_state or set_state",
        ],
    }
