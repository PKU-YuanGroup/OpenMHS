"""OpenMHS driver for gh.nonejou072/robopal: the DianaMed arm model of the framework (a MuJoCo family driver).

A MujocoDriver is configuration only: ``model_path`` names the MJCF model and the MuJoCo bridge loads it with
``mujoco.MjModel.from_xml_path``, writes ``cap.world.step.v1``'s ``action.ctrl`` to ``data.ctrl`` (bounded per
actuator by the model's ``actuator_ctrlrange``), steps ``mj_step``, and serves ``cap.world.reset.v1`` with
``mj_resetData`` + ``mj_forward``.  The model is the DianaMed manipulator template of the clone
(robopal/assets/models/manipulators/DianaMed/DianaMed.xml): seven limited joints, seven motors and a timestep of
0.0005 s.  The environment class of the task card that builds its robot from this manipulator is
``robopal.envs.manipulation_tasks.demo_cube_drawer:DrawerCubeEnv`` (default robot ``DianaDrawerCube``, a
``DianaMed`` subclass, robopal/robots/diana_med.py), which is why it is ``native``.

``model_path`` points into the pinned clone (relative to this directory) instead of copying the model: the package
carries no duplicate of an upstream asset and its meshes, and with mujoco installed the bridge loads the upstream
file unchanged.  What this package does NOT serve is the environment on top of the model: the spliced gripper and
task objects of ``DrawerCubeEnv``, its observations, rewards, the goal and its episode limit.

The gate environment has no mujoco, so ``backends["fake"]`` is the package's stand-in module in fake.py (a callable,
which the gate treats as the upstream simulator: native calls are not recorded for it).  The stand-in reads the same
model file and offers the MuJoCo API the bridge calls, but it integrates a placeholder model: it is not MuJoCo and
its trajectories are not the model's (fidelity ``gaps``).  This package is model-authored and unreviewed; nothing
here ran in MuJoCo.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import fake_mujoco

MODEL = "robopal/assets/models/manipulators/DianaMed/DianaMed.xml"
#: The model file of the pinned clone; the driver directory is four levels below the repository root.
MODEL_PATH = "../../../../robots/nonejou072/robopal/" + MODEL


class DianaMedWorld(MujocoDriver):
    device_id = "diana-med"
    model_path = MODEL_PATH
    native = "robopal.envs.manipulation_tasks.demo_cube_drawer:DrawerCubeEnv"
    backends = {"fake": fake_mujoco}
    vendor, model = "NoneJou072", "robopal DianaMed manipulator (MJCF)"
    display_name = "robopal DianaMed arm world"
    tags = ["mujoco", "simulation", "robot arm", "robopal", "reinforcement learning", "world"]
    facts = [
        Fact("robopal is a robot simulation framework on the MuJoCo physics engine", source="vendor_doc",
             ref="README.md:15"),
        Fact("The framework offers Gymnasium style single-arm and PettingZoo style bimanual environments",
             source="vendor_doc", ref="README.md:22"),
        Fact("The model integrates with a timestep of 0.0005 s, the implicitfast integrator and gravity "
             "-9.81 m/s^2", source="upstream_code", ref=f"{MODEL}:6"),
        Fact("The arm has seven limited joints: j1 -2.56..2.56 rad, j2 -1.57..1.57, j3 -2.56..2.56, j4 0.0..3.05, "
             "j5 -3.05..3.05, j6 -3.14..3.14 and j7 -3.14..3.14 (one line per joint)", source="upstream_code",
             ref=f"{MODEL}:24-53"),
        Fact("The seven motors a1..a7 command those joints and their ctrlrange is -80.0 to 80.0",
             source="upstream_code", ref=f"{MODEL}:70-76"),
        Fact("The arm geoms are visual only (contype 0, conaffinity 0) except the collision geom of the last link, "
             "so the template model has almost no contacts", source="upstream_code", ref=f"{MODEL}:22"),
        Fact("The DrawerCubeEnv manipulation environment builds its robot from the DianaDrawerCube class by "
             "default", source="upstream_code",
             ref="robopal/envs/manipulation_tasks/demo_cube_drawer.py:9-18"),
        Fact("DianaDrawerCube derives from DianaMed, the robot class whose manipulator is the DianaMed template",
             source="upstream_code", ref="robopal/robots/diana_med.py:129"),
        Fact("A robot class splices its manipulator, gripper and scene into one MJCF model with RobotGenerator and "
             "saves that model for the environment", source="upstream_code", ref="robopal/robots/base.py:53-70"),
        Fact("In a spliced scene the arm joints and actuators are prefixed (0_j1..0_j7, 0_a1..0_a7)", 
             source="upstream_code", ref="robopal/robots/diana_med.py:25-26"),
        Fact("The DrawerCubeEnv environment runs at a control frequency of 20 Hz with the CARTIK controller and "
             "limits an episode to 50 steps", source="upstream_code",
             ref="robopal/envs/manipulation_tasks/demo_cube_drawer.py:16-35"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the model state is kept and stays readable")
    #: The full fidelity contract of the world as deployed (spec 05-fidelity FID-002): the bridge derives the
    #: engine, the determinism kind and the lockstep clock, the members below say what the model and the fake are.
    fidelity = {
        "engine": "mujoco",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "exact",
            "seed_control": "none",
            "notes": "MuJoCo integrates the model deterministically from the reset state; the model has no random "
                     "element, so the same ctrl sequence and tick count repeat the trajectory.  The package's fake "
                     "backend is deterministic too, but its placeholder dynamics are not the model's.",
        },
        "timestep_ms": 0.5,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the model is the DianaMed manipulator template only: the gripper, task objects (drawer, cube), the "
            "spliced scene, the reward, the goal and the 50-step episode limit of the environment are not served",
            "rigid-body dynamics of the seven-joint arm with the model's inertias, damping, joint ranges and motor "
            "ctrlranges; the arm geoms are visual only, so contacts are negligible in the template",
            "no rendering, no sensors, no cameras and no wall-clock pacing: realtime_factor 0, ticks advance "
            "simulated time by the model's 0.0005 s step only",
            "the fake backend is not MuJoCo: it reads the model's timestep, joint count and actuator ctrlranges from "
            "the model file, then integrates a placeholder model (ctrl drives qvel, qvel drives qpos) with no "
            "inertias, contacts, constraints or actuators of the real solver; its trajectories are not valid "
            "simulation results",
            "the joint ranges of the model file bound qpos in MuJoCo; the fake does not enforce them (the runtime's "
            "only limit is the actuator ctrlrange the bridge derives)",
        ],
    }
