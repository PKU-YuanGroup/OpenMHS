# Facts and scope for gh.rohanpsingh/learninghumanoidwalking

Facts cite the read-only source at commit `cd8c6557beadb9d25045624fb50eeb487b0e8fdd`. The table matches the Fact declarations in driver.py and the generated reference.json.

| Fact | Source | Ref |
|---|---|---|
| The project description is training a humanoid robot for locomotion using reinforcement learning | vendor_doc | `pyproject.toml:4` |
| The declared simulation dependencies are dm-control>=1.0.24 and mujoco==3.4.0 | upstream_code | `pyproject.toml:9-12` |
| The repository layout labels envs/common/mujoco_env.py as the MuJoCo simulation wrapper and models/ as the MuJoCo model files | vendor_doc | `README.md:25-32` |
| MujocoEnv is the superclass for all MuJoCo environments | upstream_code | `envs/common/mujoco_env.py:13-14` |
| MujocoEnv refuses a relative model path, opens the model with mujoco.MjSpec.from_file, compiles it and creates the mujoco.MjData it owns | upstream_code | `envs/common/mujoco_env.py:16-26` |
| MujocoEnv.reset restores the data with mujoco.mj_resetData and returns the subclass's reset_model observation | upstream_code | `envs/common/mujoco_env.py:113-116` |
| BaseHumanoidEnv is the shared humanoid environment base on top of MujocoEnv | upstream_code | `envs/common/base_humanoid_env.py:19` |
| BaseHumanoidEnv.step smooths the policy action, runs robot.step and returns the observation, the summed reward, done and the reward dictionary | upstream_code | `envs/common/base_humanoid_env.py:199-227` |
| JvrcWalkEnv is the concrete JVRC walking environment and builds its XML through the jvrc builder | upstream_code | `envs/jvrc/jvrc_walk.py:13-21` |
| The jvrc builder loads its MJCF from models/jvrc_mj_description/xml/scene.xml | upstream_code | `envs/jvrc/gen_xml.py:8` |
| The jvrc builder removes every motor whose joint is not listed in LEG_JOINTS | upstream_code | `envs/jvrc/gen_xml.py:79-82` |
| The served MJCF scene is named 'jvrc1 scene' and includes jvrc1.xml | upstream_code | `models/jvrc_mj_description/xml/scene.xml:1-3` |
| The model compiles angles in radians and resolves meshes from ../meshes | upstream_code | `models/jvrc_mj_description/xml/jvrc1.xml:4` |
| The model sets option timestep 0.001 s, 50 iterations, the Newton solver, a dense Jacobian and pyramidal friction cones | upstream_code | `models/jvrc_mj_description/xml/jvrc1.xml:8` |
| The default motor class sets ctrllimited="false" and forcelimited="false" | upstream_code | `models/jvrc_mj_description/xml/jvrc1.xml:10-13` |
| The root body PELVIS_S is placed at 0 0 1.4 and carries the free joint root | upstream_code | `models/jvrc_mj_description/xml/jvrc1.xml:162-163` |
| The R_HIP_P hinge has range -2.0944 to 0.785398 rad and armature 0.1925 | upstream_code | `models/jvrc_mj_description/xml/jvrc1.xml:172` |
| The L_KNEE hinge has range 0 to 2.61799 rad and armature 0.1305 | upstream_code | `models/jvrc_mj_description/xml/jvrc1.xml:221` |
| The actuator section has one motor for each leg, waist, neck, arm and thumb joint and no motor for the distal finger joints | upstream_code | `models/jvrc_mj_description/xml/jvrc1.xml:451-492` |
| Ten equality constraints couple the five distal finger joints of each hand to its thumb | upstream_code | `models/jvrc_mj_description/xml/jvrc1.xml:436-448` |
| The sensor section reads force and torque at both feet and both hands and a gyro and accelerometer at the imu site | upstream_code | `models/jvrc_mj_description/xml/jvrc1.xml:494-510` |
| H1Env is a Unitree H1 standing environment | upstream_code | `envs/h1/h1_env.py:11-12` |
| The JVRC model submodule's LICENSE states BSD 2-Clause | vendor_doc | `models/jvrc_mj_description/LICENSE:1` |

## Served contract and limits

The package serves the raw JVRC1 scene models/jvrc_mj_description/xml/scene.xml through MujocoDriver, not the
JvrcWalkEnv task layer. The model contains 34 torque motors, 51 qpos values and 50 qvel values; the free joint uses
seven position values and six velocity values. H1Env, the other environments, PD control, policy observations,
rewards, termination and generated reduced XML are outside this package.

The model's motors disable control and force limiting and declare no ctrlrange. action.ctrl is operator_required;
a step setting controls is refused until site-limits.json supplies an envelope. site-limits.example.json is
illustrative operator data, not an upstream bound. A step without an action retains the current controls.

## Fidelity and safety

fidelity_by_backend selects analytic:jvrc1-motor-fake at F0 for the fake. It resets to the model-default root pose
[0, 0, 1.4, 1, 0, 0, 0] and zero hinge positions. The fake applies placeholder acceleration from motor controls,
using each joint's distinct qpos and qvel addresses. A zero motor control is not a zero-position target.
Mass matrices, gravity, damping, coupled motion, meshes, contacts, constraints, tendons and sensors are omitted.
No real MuJoCo trajectory or hardware execution was performed. The lockstep software stop freezes stepping;
a safety reset releases the latch without stepping or resetting the world. State remains readable.

The parent and the selected JVRC model submodule each carry BSD-2-Clause licences. The submodule is read at the
parent's gitlink bfb2bf25966ddfe0d0248385ef7e2586963c86a0 and has its own attribution and redistribution terms.

Tags: humanoid, jvrc1, mujoco, simulation, reinforcement-learning, world
