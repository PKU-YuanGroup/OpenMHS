# Facts and tags for gh.zichunxx/panda_mujoco_gym

Every fact cites its source at commit `e9881d993234875ee1d55d717176bf7999bdb583`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`; the model files are cited by their path in the
clone, `panda_mujoco_gym/assets/pick_and_place.xml`, and the copy the package carries is `model.xml`). The same facts
are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository provides three manipulation tasks - push, slide and pick-and-place - for the Franka Emika Panda arm, implemented on the MuJoCo physics engine | vendor_doc | README.md:3 |
| The pick-and-place environment loads its scene from assets/pick_and_place.xml | upstream_code | panda_mujoco_gym/envs/pick_and_place.py:4 |
| The scene includes the robot model panda_mocap.xml | upstream_code | model.xml:8 |
| The scene sets the integrator to Euler, noslip_iterations to 3, the timestep to 0.002 s and the cone to pyramidal | upstream_code | model.xml:4 |
| The scene compiles with the radian angle unit, the ./meshes/ mesh directory and automatic limits | upstream_code | model.xml:2 |
| The scene adds a free object body at (0.4, 0, 0.2) whose box geom has mass 0.1 and size 0.02 m, and a target site at the same position | upstream_code | model.xml:30-38 |
| The robot model declares the seven arm joints joint1 to joint7 | upstream_code | panda_mocap.xml:142-204 |
| The default class panda gives every arm joint armature 0.1, damping 1, axis 0 0 1 and the range -2.8973 to 2.8973 rad, and its actuators the ctrlrange -2.8973 to 2.8973 and forcerange -87 to 87 | upstream_code | panda_mocap.xml:5-8 |
| The default class finger gives the gripper finger joints a slide joint on axis 0 1 0 with the range 0 to 0.04 m | upstream_code | panda_mocap.xml:7-9 |
| The two actuator sections declare seven general actuators for the arm joints and two for the gripper fingers, and the finger actuators have the ctrlrange 0 to 0.04 | upstream_code | panda_mocap.xml:269-283 |
| The robot model welds the mocap body panda_mocap to the end-effector body ee_center_body, so the end effector is driven by a mocap pose and not by joint position commands | upstream_code | panda_mocap.xml:266 |
| The environment states that the model has 9 actuators (7 arm and 2 gripper joints), 16 generalized coordinates (9 arm and gripper plus the 7 of the object's free joint) and 15 degrees of freedom | upstream_code | panda_mujoco_gym/envs/panda_env.py:75-81 |
| The environment takes its control range from the model's actuator_ctrlrange | upstream_code | panda_mujoco_gym/envs/panda_env.py:83-84 |
| The environment action is three Cartesian displacements plus a gripper command unless the gripper is blocked | upstream_code | panda_mujoco_gym/envs/panda_env.py:35-37 |
| The pick-and-place environment runs 25 physics substeps per step, uses the distance threshold 0.05 and samples the object and the goal in a 0.3 m range with a 0.2 m height range | upstream_code | panda_mujoco_gym/envs/pick_and_place.py:13-23 |
| The package registers the three tasks, each with a sparse and a dense reward, with 50 steps per episode | upstream_code | panda_mujoco_gym/__init__.py:6-16 |
| A step clips the action to the action-space bounds and runs ten physics steps of n_substeps each | upstream_code | panda_mujoco_gym/envs/panda_env.py:121-133 |

Limits: none are declared in `driver.py`. The per-actuator bounds of the step action are derived from the carried
model's `actuator_ctrlrange` by the bridge (the same field the environment reads,
`panda_mujoco_gym/envs/panda_env.py:83-84`); their source is the model file (`model.xml:actuator_ctrlrange`), and the
stand-in `mujoco` module of `fake.py` reads that range from `model.xml` and `panda_mocap.xml` with the default classes
the model states.

Safety: this is a simulated device (mode simulated, risk R0): there is no hardware backend, no actuator can hurt
anybody and no operator bound applies. An e-stop stops the simulation from advancing until `mhs.safety.reset` clears the
latch; the world state stays readable. `safe_state` says the same.

Not exposed: the upstream reinforcement-learning environments (`FrankaPickAndPlaceEnv`, `FrankaPushEnv`,
`FrankaSlideEnv`, `FrankaEnv`) and their observations, rewards, goal sampling and mocap end-effector control; this
package serves the raw pick-and-place model. The other two scenes (`push.xml`, `slide.xml`) and the meshes are not
served or carried. The MuJoCo engine was never run here: the package is checked on the stand-in module of `fake.py`.

Tags: mujoco, franka, panda, manipulation, pick-and-place, simulation
