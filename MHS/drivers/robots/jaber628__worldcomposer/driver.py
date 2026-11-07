"""OpenMHS driver for gh.jaber628/worldcomposer: the WorldComposer-Tableware-v0 Isaac Lab task.

WorldComposer is a Gymnasium family of Isaac Lab ``DirectRLEnv`` manipulation tasks.  The registered Tableware
environment is served through the ``cap.world.*`` classes: ``cap.world.step.v1`` takes ``{ticks, action}`` with the
six-value action derived from the environment's action space, ``cap.world.reset.v1`` takes ``{seed, options}`` and
``cap.world.seed.v1`` takes ``{seed}``.  The device is simulated (R0): there is no hardware backend, no stop path to
a machine and no operator-required limit.

``TablewareEnv`` subclasses ``isaaclab.envs.DirectRLEnv`` (Tableware.py:9 and :17), so the Gymnasium base, the space
objects and the episode time limit live in the external Isaac Lab package, which this clone does not contain.  The
task needs Isaac Sim, Isaac Lab, a CUDA GPU and the external ``Assets/`` dataset (README.md:45-54 and :74-86);
package code never imports or runs the clone, so the ``fake`` backend is this package's pure Python interface
stand-in and the upstream simulator path was not run.  The fake reproduces the spaces, the observation keys, the
zero reward and the time-out contract, not the Isaac Sim physics.

Every Fact cites a line or a line range of the clone at the pinned commit
c2de3a2c9b3cc0f91e2bf739e5e6a24742988da2.  This package is model-authored and unreviewed: it is checked on the fake
backend only, and no hardware or simulator run is claimed.
"""

from mhs.driver import Fact, GymnasiumDriver

TASK = "source/WorldComposer/WorldComposer/tasks/Task01_Tableware"
ENV = f"{TASK}/Tableware.py"
CFG = f"{TASK}/Tableware_cfg.py"
REGISTRATION = f"{TASK}/__init__.py"
ROBOT = "source/WorldComposer/WorldComposer/assets/robots/lerobot.py"
SUCCESS = "source/WorldComposer/WorldComposer/utils/success_checker.py"
SETUP = "source/WorldComposer/setup.py"


class WorldComposerTableware(GymnasiumDriver):
    """The WorldComposer-Tableware-v0 manipulation task of the jaber628 WorldComposer suite."""

    device_id = "worldcomposer-tableware"
    device_kind = "world.sim"
    mode, risk = "simulated", "R0"
    env_id = "WorldComposer-Tableware-v0"
    native = "WorldComposer.tasks.Task01_Tableware.Tableware:TablewareEnv"
    backends = {"fake": ".fake:FakeTablewareEnv"}
    display_name = "WorldComposer Tableware (Isaac Lab DirectRLEnv)"
    vendor, model = "jaber628", "WorldComposer-Tableware-v0"
    tags = ["worldcomposer", "tableware", "robot-manipulation", "isaac-lab", "isaac-sim",
            "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("The task is registered as WorldComposer-Tableware-v0 with entry point Tableware:TablewareEnv and "
             "TablewareEnvCfg as its environment configuration", source="upstream_code",
             ref=f"{REGISTRATION}:3-9"),
        Fact("TablewareEnv subclasses DirectRLEnv imported from isaaclab.envs, so the Gymnasium base, the action "
             "and observation space objects and the episode time limit live in the external Isaac Lab package",
             source="upstream_code", ref=f"{ENV}:9-17"),
        Fact("TablewareEnv takes the environment configuration cfg and an optional render_mode", source="upstream_code",
             ref=f"{ENV}:20"),
        Fact("The task config sets decimation 1, episode_length_s 60, action_scale 1.0, action_space 6, "
             "observation_space 6 and state_space 0", source="upstream_code", ref=f"{CFG}:17-22"),
        Fact("The simulation step is dt = 1/120 s, with render_interval equal to decimation 1", source="upstream_code",
             ref=f"{CFG}:25"),
        Fact("The robot is an SO101 follower whose default joint positions are shoulder_pan -0.0363, "
             "shoulder_lift -1.7135, elbow_flex 1.4979, wrist_flex -1.5, wrist_roll -0.085 and gripper -0.01176",
             source="upstream_code", ref=f"{CFG}:27-39"),
        Fact("The SO101 action joint order is shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll, "
             "gripper", source="upstream_code", ref=f"{ROBOT}:17-24"),
        Fact("_pre_physics_step multiplies the action by action_scale and _apply_action sets it as the robot joint "
             "position target", source="upstream_code", ref=f"{ENV}:97-101"),
        Fact("_get_observations returns a dict with the applied action and the six joint positions under the keys "
             "action and observation.state", source="upstream_code", ref=f"{ENV}:103-113"),
        Fact("_get_rewards returns 0 for the Tableware task", source="upstream_code", ref=f"{ENV}:133-135"),
        Fact("The episode ends when episode_length_buf reaches max_episode_length - 1, and the same time-out flag is "
             "returned as both terminated and truncated", source="upstream_code", ref=f"{ENV}:137-139"),
        Fact("Camera observations are added only when task_config.teleop.enable_cameras is true: top and wrist RGB "
             "and, unless disable_depth is true, depth images", source="upstream_code", ref=f"{ENV}:115-129"),
        Fact("The wrist and top cameras are configured at 960 x 720 pixels with rgb and depth data types",
             source="upstream_code", ref=f"{CFG}:42-79"),
        Fact("The success check compares the XY distance between objects A and B and requires both distances to be "
             "at most 0.035 m", source="upstream_code", ref=f"{SUCCESS}:97-113"),
        Fact("Installation creates a Python 3.11 environment, installs torch 2.7.0, lerobot 0.4.1 and "
             "isaacsim[all,extscache], then installs source/WorldComposer in editable mode", source="vendor_doc",
             ref="README.md:74-86"),
        Fact("The simulation assets are downloaded from the Hugging Face WorldComposer_Assets dataset into Assets/",
             source="vendor_doc", ref="README.md:45-54"),
        Fact("The package setup requires Python 3.10 or newer and declares the Apache-2.0 license",
             source="upstream_code", ref=f"{SETUP}:32-34"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The upstream task is an Isaac
    #: Sim rigid-body simulation, but this package ships no sim backend and the fake models no dynamics, so the level
    #: is F0 and the gaps carry every omission.  timestep_ms is the physics step of Tableware_cfg.py:25 (1/120 s);
    #: decimation 1 makes it the control step as well (Tableware_cfg.py:17).
    fidelity = {
        "engine": "mhs-fake:WorldComposer-Tableware-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed=...) and cap.world.seed.v1 set the seed of the next reset, and the fake's state "
                     "update is deterministic. The upstream reset randomizes object instances, scale, position, "
                     "texture and lighting (Tableware.py:157 onwards) and the upstream Isaac Sim environment was "
                     "not run, so its own determinism is not claimed and the two were not compared.",
        },
        "timestep_ms": 1000.0 / 120.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic F0 stand-in: no Isaac Sim physics, rigid bodies, contacts, actuator, sensor, noise or "
            "rendering model; the fake applies the action directly as the joint positions and claims no dynamics",
            "the real action and observation space objects are created by the external DirectRLEnv and were not "
            "inspected; the fake exposes unbounded six-value Boxes and neither rejects nor clamps a finite action, "
            "so no action limit is published",
            "the observation is the two-key dict of Tableware.py:110-113 with six values each; the camera keys that "
            "task_config.teleop.enable_cameras adds (Tableware.py:115-129) are not represented and the fake returns "
            "no image arrays, while the real wrist and top cameras are 960 x 720 rgb and depth (Tableware_cfg.py:"
            "42-79)",
            "the fake serves one environment with the default joint positions of Tableware_cfg.py:31-38; the reset "
            "randomization of Tableware.py:157 onwards (object instance, scale, position, texture and lighting) is "
            "not modelled",
            "the fake does not model task success: the 0.035 m XY distance check of utils/success_checker.py:97-113 "
            "is not evaluated",
            "the episode time limit is a placeholder of 7200 fake steps derived from episode_length_s 60 and "
            "dt 1/120 s; the termination and truncation rule itself is in the external DirectRLEnv, and the fake "
            "marks both flags on time-out as Tableware.py:137-139 does",
            "the upstream task needs Isaac Sim, Isaac Lab, the external Assets/ dataset and a CUDA GPU "
            "(README.md:45-54 and :74-86); it was never started here, so the upstream simulator path and any "
            "agreement with it are not claimed",
            "no wall-clock pacing: realtime_factor 0 and clock lockstep",
            "snapshot and restore are not offered: the fake exposes no get_state or set_state",
        ],
    }
