# Facts and tags for gh.cxy1997/robotiq-ur5

Every fact cites its source at commit `6c6d53f6a7d525f83e103ce594f166520d9390ee`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (a Python file or an MJCF file of the clone).  The same facts are written
into `facts = [...]` in `driver.py`; the reference file is generated from the driver, not from this page.

The package serves the card's model, the MJCF scene `xmls/lab_env.xml` (`models[0]`), as a `MujocoDriver`.  It reads
the model file from the read-only clone; the package copies neither the model nor its meshes.  The card lists no
`entry_symbols`, so there was no symbol to confirm; the card's model file and the `environment.py` usage text exist.

| fact | source | ref |
|---|---|---|
| The README describes the repository as 'Simulator of UR5 robotic arm with Roboriq gripper, built with MuJoJo' | vendor_doc | README.md:2 |
| The README requires MuJoCo 1.5.0 and mujoco-py | vendor_doc | README.md:5-6 |
| The README's Python usage is 'from environment import lab_env' | vendor_doc | README.md:9 |
| The lab_env constructor loads xmls/lab_env.xml as the real-world simulator and xmls/light_env.xml to locate the gripper | upstream_code | environment.py:75-79 |
| The upstream reset writes 42 qpos values from initial_pos and then overwrites the first three with the selected task's joint_pos values | upstream_code | environment.py:89-92 |
| The upstream step maps action[0], action[1] and action[2] to qpos[0], qpos[1] and qpos[2] over -30 to 45 degrees, -105 to -50 degrees and 0 to 180 degrees, and uses action[3] for the number of gripper closing steps | upstream_code | environment.py:103-111 |
| The upstream get_state renders 960 by 720 images from workbench_camera and upper_camera, crops 214 by 214 windows, adds Gaussian noise, and returns the two images plus the six-element vector [x1, y1, x2, y2, grasped, danger] | upstream_code | environment.py:170-188 |
| The upstream safety_check steps the simulation, sums the absolute movement of the first six joints and compares it with safety_threshold | upstream_code | environment.py:190-198 |
| The safety_threshold is 0.01 | upstream_code | environment.py:33 |
| The model root element is '<mujoco model="ur5">' and its compiler element declares angle radian and meshdir meshes | upstream_code | xmls/lab_env.xml:1-2 |
| The option element sets gravity 0 0 0, an elliptic cone and timestep 0.02 s | upstream_code | xmls/lab_env.xml:4 |
| The global default class gives joints frictionloss 1 and damping 1 and motors gear 0.8 | upstream_code | xmls/lab_env.xml:12-19 |
| The arm is a chain of six hinge joints named joint1 to joint6 | upstream_code | xmls/lab_env.xml:74-106 |
| The right gripper finger has hinge joints joint7_1 with range 0 to 0.872664626 rad, joint8_1 and joint9_1 with range 0 to 2.967059728 rad, and joint10_1 with range 0 to 1 rad | upstream_code | xmls/lab_env.xml:119-137 |
| The left gripper finger has hinge joints joint7_2 with range 0 to 0.872664626 rad, joint8_2 and joint9_2 with range 0 to 2.967059728 rad, and joint10_2 with range 0 to 1 rad | upstream_code | xmls/lab_env.xml:143-161 |
| Four target bodies each declare three slide joints free_x, free_y and free_z and one ball joint free_ball | upstream_code | xmls/lab_env.xml:173-207 |
| The actuator section declares twelve motor actuators: gravity_1 to gravity_4 on free_z_1 to free_z_4 with gear '1 0 0 0 0 0', close_1 and close_2 on joint7_1 and joint7_2 with gear '0.2 0 0 0 0 0', joint1_motor with gear 1.2, and joint2_motor to joint6_motor | upstream_code | xmls/lab_env.xml:232-243 |
| No active actuator element of the model declares a ctrlrange attribute | upstream_code | xmls/lab_env.xml:232-243 |
| The model declares the cameras workbench_camera and upper_camera | upstream_code | xmls/lab_env.xml:42-49 |
| The model declares four touch sensors on target_site_1 to target_site_4 | upstream_code | xmls/lab_env.xml:247-251 |

Limits: the bridge derives `cap.world.step.v1` `action.ctrl` from `model.actuator_ctrlrange`.  The active motors of
`xmls/lab_env.xml:232-243` declare no `ctrlrange`, and MuJoCo's `ctrllimited` default is false, so the bridge derives
no interval for any of the twelve controls, and no source in the clone states a control bound that could be
cited; so the bridge publishes `action.ctrl` as `operator_required`: the endpoint refuses a step that sets it
(`MHS.SAFETY.LIMITS_UNSET`, before any native call) until the site's `site-limits.json` bounds it, and a
step without `action` keeps the controls as they are. `site-limits.example.json` is operator example data
(-10 to 10 for every control), not a bound of the model; the package invents none.

Fidelity: the fake backend is a stand-in for the MuJoCo library (fake.py), not MuJoCo.  It reads the model file for the
joint dimensions, the actuator count, the control targets and the absent ctrlrange, but its integration is a
placeholder first-order motion, and it resolves no mesh, contact, equality, tendon, sensor or camera.  The upstream
`environment.py` task interface is not served: its reset writes `initial_pos` and `joint_pos`, its step maps a
four-element action to joint angles and a gripper sequence, and its state is two cropped noisy camera images plus a
grasp/danger vector.  Those outputs are NOT COVERED.  MuJoCo was not importable where the gate ran, so no trajectory
was compared with the real engine and the sim backend that imports `mujoco` was not run.  The gaps are listed in the
`fidelity` attribute of `driver.py`.

Tags: gripper, manipulation, mujoco, robot, robotiq, simulation, ur5
