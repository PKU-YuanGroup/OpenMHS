"""OpenMHS driver for gh.google-research/robodesk: the RoboDesk manipulation environment (a Gymnasium family driver).

RoboDesk is a Gymnasium environment (``robodesk.robodesk:RoboDesk`` subclasses ``gym.Env``, robodesk/robodesk.py:16)
with a five-value end-effector action space and a dictionary observation that carries an image.  The card says
``family: mujoco`` and ``helper: MujocoDriver``, but the upstream class is not a bare MuJoCo model/data pair: it
wraps the MuJoCo physics, inverse kinematics, nine task reward functions and the rendering inside ``reset()`` and
``step()``.  A ``MujocoDriver`` would expose ``actuator_ctrlrange`` and the raw ``qpos``/``qvel`` instead of the
environment action space, so this package uses the Gymnasium family, which serves exactly ``reset``/``step`` and
derives the action schema from ``RoboDesk.action_space`` (DEVIATION FROM THE CARD: helper GymnasiumDriver).

``cap.world.step.v1`` takes ``{ticks, action: {values: [five numbers in -1..1]}}``, ``cap.world.reset.v1`` takes
``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  RoboDesk.reset() takes no seed argument and draws its
randomized initial state from numpy's global generator (robodesk/robodesk.py:207-229), so the fidelity contract
declares statistical determinism with no seed control.

The package is checked on the fake backend only: the upstream package needs ``dm_control``, ``gym``, ``numpy`` and
``PIL`` (setup.py:31-34) and package code never imports the clone.  The fake in fake.py is a small kinematic
stand-in for the environment interface; it does not integrate the MuJoCo model.  This package is model-authored
and unreviewed.
"""

from mhs.driver import Fact, GymnasiumDriver

ROBODESK = "robodesk/robodesk.py"
DESK = "robodesk/assets/desk.xml"
README = "README.md"


class RoboDesk(GymnasiumDriver):
    device_id = "robodesk"
    native = "robodesk.robodesk:RoboDesk"
    backends = {"fake": ".fake:FakeRoboDesk"}
    display_name = "RoboDesk multi-task manipulation benchmark"
    vendor, model = "Google Research", "RoboDesk"
    tags = ["robodesk", "mujoco", "manipulation", "robot-arm", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("RoboDesk is a Gymnasium environment: the class subclasses gym.Env", source="upstream_code",
             ref=f"{ROBODESK}:16"),
        Fact("The environment loads the MuJoCo scene model robodesk/assets/desk.xml", source="upstream_code",
             ref=f"{ROBODESK}:23-24"),
        Fact("The MuJoCo model integrates with a 2 ms timestep (0.002 s)", source="upstream_code",
             ref=f"{DESK}:5"),
        Fact("Each environment step applies the action action_repeat times and runs the physics 10 times per "
             "application", source="upstream_code", ref=f"{ROBODESK}:170-176"),
        Fact("The action space is Box(-1, 1, (5,)): five end-effector control values, each between -1 and 1",
             source="vendor_doc", ref=f"{README}:109-115"),
        Fact("The action is five-dimensional (action_dim = 5)", source="upstream_code", ref=f"{ROBODESK}:34"),
        Fact("The robot has nine actuated joints (num_joints = 9)", source="upstream_code", ref=f"{ROBODESK}:29"),
        Fact("The observation is a dictionary with image, qpos_robot, qvel_robot, end_effector, qpos_objects and "
             "qvel_objects", source="vendor_doc", ref=f"{README}:96-107"),
        Fact("The image observation space is Box(0, 255, (image_size, image_size, 3), uint8)",
             source="upstream_code", ref=f"{ROBODESK}:104-105"),
        Fact("The constructor defaults image_size to 64 pixels", source="upstream_code", ref=f"{ROBODESK}:19-20"),
        Fact("The observation spaces are 9 floats for qpos_robot and qvel_robot, 3 floats for end_effector and 26 "
             "floats for qpos_objects and qvel_objects", source="upstream_code", ref=f"{ROBODESK}:106-111"),
        Fact("The observation key qpos_objects is populated from physics.data.qvel, not qpos",
             source="upstream_code", ref=f"{ROBODESK}:385"),
        Fact("An episode ends when episode_length is set and num_steps reaches it; there is no other termination "
             "condition in step()", source="upstream_code", ref=f"{ROBODESK}:192-197"),
        Fact("The constructor defaults episode_length to 500 time steps",
             source="upstream_code", ref=f"{ROBODESK}:19-20"),
        Fact("The reward is the task reward clamped to the interval [0, 1]", source="upstream_code",
             ref=f"{ROBODESK}:375-378"),
        Fact("reset() takes no seed or options argument: it resets the physics, then randomizes the drawer, slide, "
             "blocks and ball and the robot start pose with numpy's global random generator",
             source="upstream_code", ref=f"{ROBODESK}:207-229"),
        Fact("The reward type is one of dense, sparse or success; task defaults to open_slide and reward to dense",
             source="upstream_code", ref=f"{ROBODESK}:19-21"),
        Fact("step returns (observation, reward, done, info) with info {'discount': 1.0}",
             source="upstream_code", ref=f"{ROBODESK}:197"),
        Fact("Episodes end after 500 time steps by default and there are no early terminations",
             source="vendor_doc", ref=f"{README}:92-94"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop no step or reset is accepted until "
                  "mhs.safety.reset clears the latch; the simulated state is kept and stays readable")
    #: The fidelity contract of the model this package actually serves: a kinematic fake of the environment
    #: interface.  The upstream MuJoCo model is contact dynamics (F1), but the fake does not integrate it, so the
    #: deployed model is declared F0 and the omissions are listed in the gaps.
    fidelity = {
        "engine": "custom:RoboDesk kinematic fake (upstream mujoco robodesk/assets/desk.xml not integrated)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "statistical",
            "seed_control": "none",
            "notes": "upstream reset() draws the object positions and the robot start pose from numpy's global "
                     "generator and takes no seed argument (robodesk/robodesk.py:207-229); the fake uses its own "
                     "Python RNG, so no seed reproduces a trajectory and no exact replay is claimed",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic fake only: no MuJoCo integration, contacts, friction, gravity, inverse kinematics or "
            "Franka Panda actuators are modelled; the upstream rigid-body dynamics are not reproduced",
            "the fake observation image is a 4 x 4 x 3 stand-in; upstream renders 120 x 120 and resizes to "
            "image_size x image_size x 3, 64 x 64 x 3 by default (robodesk/robodesk.py:104-105, 114-131)",
            "the six observation keys are present but carry placeholder values; the upstream qpos_objects-from-qvel "
            "defect is mirrored (robodesk/robodesk.py:385), and no task reward function is modelled (the fake "
            "returns a constant placeholder reward)",
            "one fake step is one control step and does not model action_repeat, task, reward-type or image_size "
            "constructor options",
            "no rendering, no camera, no get_state/set_state: snapshot and exact replay are not offered",
            "no wall-clock pacing: simulated time advances only when a step command arrives (realtime_factor 0)",
            "the fake was never compared with the upstream environment, which is not importable where the gate "
            "runs; trajectories and arrays are not validated against MuJoCo",
        ],
    }
