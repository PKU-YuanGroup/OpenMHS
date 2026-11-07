"""OpenMHS driver for gh.zhefan-xu/isaac-go2-ros2: the Unitree Go2 environment of Isaac Sim / Isaac Lab.

The card's entry symbol is ``go2.go2_env:Go2RSLEnvCfg`` (go2/go2_env.py:139), the configuration the launcher builds
and passes to ``gym.make("Isaac-Velocity-Rough-Unitree-Go2-v0", cfg=cfg)`` (isaac_go2_ros2.py:39,45;
go2/go2_ctrl.py:81).  The driver is a Gymnasium family driver: ``env_id`` names that environment and the bridge
derives ``cap.world.step.v1``, ``cap.world.reset.v1`` and ``cap.world.seed.v1`` from its spaces.  ``step`` takes
``{ticks, action}`` with ``action.values`` bounded per element by the environment's action space, so the driver
declares no bound of its own.  The device is simulated (R0): there is no hardware backend and no operator-required
limit.

The gate cannot import Isaac Sim, Isaac Lab, ROS 2 or the trained RSL-RL checkpoint (README.md:26-30), so the
``fake`` backend is the package's own kinematic stand-in (fake.py).  A backend name that ``backends`` does not list
(``sim``) would be served by ``gymnasium.make(env_id)`` (GymnasiumDriver.open_native); that path was not run here and
would still need the upstream installation and the ``cfg`` the launcher builds.

The ``fidelity`` attribute states the model as deployed on the fake: an analytic stand-in with no dynamics.  The
upstream environment itself is an Isaac Lab rigid-body simulation with contacts and sensors; the package does not
run it, so it makes no F1/F2 claim.  Every constant and rule in ``facts`` cites a line of the clone at the pinned
commit f201692a5519e6e6ed058637ce93a2f603f016f2.  This package is model-authored and unreviewed: it is checked on
the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "go2/go2_env.py"
CTRL = "go2/go2_ctrl.py"
BRIDGE = "ros2/go2_ros2_bridge.py"
LAUNCHER = "isaac_go2_ros2.py"
SIM_CFG = "cfg/sim.yaml"


class Go2IsaacLab(GymnasiumDriver):
    device_id = "isaac-go2-ros2"
    env_id = "Isaac-Velocity-Rough-Unitree-Go2-v0"
    native = "go2.go2_env:Go2RSLEnvCfg"
    backends = {"fake": ".fake:FakeGo2Env"}
    display_name = "Unitree Go2 in Isaac Sim / Isaac Lab (rough terrain)"
    vendor, model = "Zhefan Xu", "Unitree Go2"
    tags = ["unitree-go2", "quadruped", "isaac-sim", "isaac-lab", "reinforcement-learning", "ros2", "simulation",
            "gymnasium"]
    facts = [
        Fact("The repository provides a Unitree Go2 quadruped robot simulation on Isaac Sim / Isaac Lab with a "
             "ROS 2 interface", source="vendor_doc", ref="README.md:14"),
        Fact("Isaac Sim 4.5, Isaac Lab 2.1.0 and ROS 2 Humble must be installed before the simulation runs",
             source="vendor_doc", ref="README.md:26-30"),
        Fact("The ROS 2 interface subscribes to /unitree_go2/cmd_vel and publishes front-camera, LIDAR, odometry "
             "and pose topics", source="vendor_doc", ref="README.md:64-80"),
        Fact("The Go2 is an Isaac Lab articulation spawned at {ENV_REGEX_NS}/Go2", source="upstream_code",
             ref=f"{ENV}:47"),
        Fact("The height scanner is a grid at 0.1 resolution over a size of 1.6 x 1.0 attached to the Go2 base",
             source="upstream_code", ref=f"{ENV}:52-58"),
        Fact("The Go2RSLEnvCfg default scene uses 2 environments with an env_spacing of 2.0", source="upstream_code",
             ref=f"{ENV}:142"),
        Fact("The action term is a JointPositionActionCfg over all joints matched by the regular expression .*",
             source="upstream_code", ref=f"{ENV}:64"),
        Fact("The observation group contains base linear velocity, base angular velocity, projected gravity, the "
             "base velocity command, joint positions, joint velocities, the last action and a height scan clipped "
             "to -1..1", source="upstream_code", ref=f"{ENV}:75-94"),
        Fact("The velocity command ranges are all zero: lin_vel_x, lin_vel_y, ang_vel_z and heading",
             source="upstream_code", ref=f"{ENV}:110-111"),
        Fact("The environment config sets decimation to 8, sim.dt to 0.005 s and the render interval to the "
             "decimation", source="upstream_code", ref=f"{ENV}:161-165"),
        Fact("The episode length is 20.0 s and the finite-horizon flag is False, so the environment does not "
             "truncate on time", source="upstream_code", ref=f"{ENV}:171-172"),
        Fact("Joint position actions are scaled by 0.25", source="upstream_code", ref=f"{ENV}:173"),
        Fact("The height scanner update period is decimation * sim.dt", source="upstream_code",
             ref=f"{ENV}:175-176"),
        Fact("The environment is created with gym.make('Isaac-Velocity-Rough-Unitree-Go2-v0', cfg=cfg) and wrapped "
             "in RslRlVecEnvWrapper", source="upstream_code", ref=f"{CTRL}:81-82"),
        Fact("The command input is a float32 tensor of shape (num_envs, 3)", source="upstream_code",
             ref=f"{CTRL}:14-16"),
        Fact("The ROS 2 cmd_vel callback writes Twist.linear.x, linear.y and angular.z into the three command "
             "columns", source="upstream_code", ref=f"{BRIDGE}:320-323"),
        Fact("The launcher overrides decimation with ceil(1/sim.dt/cfg.freq)", source="upstream_code",
             ref=f"{LAUNCHER}:41"),
        Fact("The sim.yaml default is 1 environment and a control frequency of 40", source="upstream_code",
             ref=f"{SIM_CFG}:4-5"),
    ]
    safe_state = ("the simulated world stops advancing: no step, reset or seed is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the last state stays readable")
    #: The fidelity contract of the model as deployed on the fake backend (spec 05-fidelity section 2).
    fidelity_level = "F0"
    fidelity = {
        "engine": "isaaclab:Isaac-Velocity-Rough-Unitree-Go2-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake draws its initial joint offsets from Python's random.Random(seed) and its step is "
                     "analytic, so one seed and action sequence repeat; the upstream environment would draw from "
                     "Isaac Lab's generators, so a seed does not give the same trajectory on the two",
        },
        "timestep_ms": 40.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is an analytic stand-in, not the Isaac Sim / Isaac Lab environment: it models no rigid-body "
            "dynamics, contacts, actuator, sensor or noise dynamics, and the base never moves",
            "one step is one environment transition of 40 ms (decimation 8 x sim.dt 0.005 s, go2/go2_env.py:161,164); "
            "the launcher recomputes decimation from cfg.freq (isaac_go2_ros2.py:41) and a changed frequency is not "
            "modelled here",
            "the fake observation uses placeholder dimensions: 3 values for the base terms, 12 for the joint terms "
            "and 8 for the height scan; the upstream joint dimension comes from UNITREE_GO2_CFG outside the clone "
            "and the upstream height scan is the grid configured at go2/go2_env.py:52-58 (0.1 resolution over a "
            "1.6 x 1.0 size), so the fake arrays are smaller stand-ins",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms only",
            "the fake was not compared with the upstream environment; Isaac Sim 4.5, Isaac Lab 2.1.0, ROS 2 Humble "
            "and the RSL-RL checkpoint (README.md:26-30, go2/go2_ctrl.py:80-91) are absent where the gate runs, and "
            "package code never imports the clone",
            "the ROS 2 topics of the upstream bridge (/unitree_go2/cmd_vel, camera, LIDAR, odometry, pose) are not "
            "exposed by this Gymnasium contract; it serves cap.world.step, cap.world.reset and cap.world.seed only",
            "snapshot and restore are not offered: the deployed environment exposes no get_state/set_state to the "
            "bridge",
        ],
    }
