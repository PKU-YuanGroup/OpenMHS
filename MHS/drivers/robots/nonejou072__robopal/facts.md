# Facts and tags for gh.nonejou072/robopal

Every fact cites its source at commit `df5a503657cb4772f5ec7e09d694c584b0d8e172`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page. This package
serves the DianaMed manipulator model of the framework as a MuJoCo world; the environment on top of it is not served.

| fact | source | ref |
|---|---|---|
| robopal is a robot simulation framework on the MuJoCo physics engine | vendor_doc | README.md:15 |
| The framework offers Gymnasium style single-arm and PettingZoo style bimanual environments | vendor_doc | README.md:22 |
| The model integrates with a timestep of 0.0005 s, the implicitfast integrator and gravity -9.81 m/s^2 | upstream_code | robopal/assets/models/manipulators/DianaMed/DianaMed.xml:6 |
| The arm has seven limited joints: j1 -2.56..2.56 rad, j2 -1.57..1.57, j3 -2.56..2.56, j4 0.0..3.05, j5 -3.05..3.05, j6 -3.14..3.14 and j7 -3.14..3.14 (one line per joint) | upstream_code | robopal/assets/models/manipulators/DianaMed/DianaMed.xml:24-53 |
| The seven motors a1..a7 command those joints and their ctrlrange is -80.0 to 80.0 | upstream_code | robopal/assets/models/manipulators/DianaMed/DianaMed.xml:70-76 |
| The arm geoms are visual only (contype 0, conaffinity 0) except the collision geom of the last link, so the template model has almost no contacts | upstream_code | robopal/assets/models/manipulators/DianaMed/DianaMed.xml:22 |
| The DrawerCubeEnv manipulation environment builds its robot from the DianaDrawerCube class by default | upstream_code | robopal/envs/manipulation_tasks/demo_cube_drawer.py:9-18 |
| DianaDrawerCube derives from DianaMed, the robot class whose manipulator is the DianaMed template | upstream_code | robopal/robots/diana_med.py:129 |
| A robot class splices its manipulator, gripper and scene into one MJCF model with RobotGenerator and saves that model for the environment | upstream_code | robopal/robots/base.py:53-70 |
| In a spliced scene the arm joints and actuators are prefixed (0_j1..0_j7, 0_a1..0_a7) | upstream_code | robopal/robots/diana_med.py:25-26 |
| The DrawerCubeEnv environment runs at a control frequency of 20 Hz with the CARTIK controller and limits an episode to 50 steps | upstream_code | robopal/envs/manipulation_tasks/demo_cube_drawer.py:16-35 |

Limits: the only bounds are the model's own, derived by the bridge from the file: per actuator `action.ctrl` inside the
`ctrlrange` of that motor (-80.0..80.0 for all seven here), which needs no separate Limit object in `driver.py`
(the gate treats a bound derived from the simulator object as such, not as a hand-written limit).

Model path: `driver.py` reads the model from the pinned clone (`../../../../robots/nonejou072/robopal/` +
the model path) instead of copying the file into the package, so the package carries no duplicate of an upstream
asset or of its meshes and a machine with mujoco installed loads the upstream model unchanged.

Tags: mujoco, simulation, robot arm, robopal, reinforcement learning, world
