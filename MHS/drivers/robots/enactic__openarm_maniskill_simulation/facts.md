# Facts and tags for gh.enactic/openarm_maniskill_simulation

Every fact cites its source at commit `3d3615aadabff11ce61ddc2e1608c1447cb3a59d`, as `upstream_code` with a
`path/in/clone:LINE` reference.  The same facts are written into `driver.py` (`facts = [...]`); the reference file is
generated from the driver, not from this page.  The clone has no vendor documentation beyond `README.md`.

| fact | source | ref |
|---|---|---|
| The repository is an overlay: its installation copies the openarm URDF, the agent package and the four tabletop task files into a ManiSkill checkout rather than installing a package | upstream_code | README.md:41-56 |
| The required ManiSkill version is v3.0.0b21 | upstream_code | README.md:10 |
| The clone lists PushCube-v1, PullCube-v1 and PickCube-v1 as its runnable tasks | upstream_code | README.md:64-68 |
| PickCube-v1 is registered with max_episode_steps=50 | upstream_code | mani_skill/envs/tasks/tabletop/pick_cube.py:34 |
| PickCubeEnv defaults the robot to the openarm agent | upstream_code | mani_skill/envs/tasks/tabletop/pick_cube.py:52 |
| The openarm PickCube config uses cube_half_size 0.02, goal_thresh 0.025, cube_spawn_half_size 0.05, cube_spawn_center (0, 0) and max_goal_height 0.3 | upstream_code | mani_skill/envs/tasks/tabletop/pick_cube_cfgs.py:70-80 |
| The cube xy position is drawn uniformly from the spawn half-size around the spawn centre and its z is the cube half-size | upstream_code | mani_skill/envs/tasks/tabletop/pick_cube.py:120-128 |
| The goal xy position uses the same draw and its z is a uniform draw up to max_goal_height above the cube z | upstream_code | mani_skill/envs/tasks/tabletop/pick_cube.py:132-140 |
| The observation extras are is_grasped, tcp_pose and goal_pos, plus obj_pose, tcp_to_obj_pos and obj_to_goal_pos when the state observation is used | upstream_code | mani_skill/envs/tasks/tabletop/pick_cube.py:148-161 |
| Success is the goal-site to cube distance at or below goal_thresh and a static robot | upstream_code | mani_skill/envs/tasks/tabletop/pick_cube.py:163-175 |
| The dense reward adds a reaching term 1 - tanh(5 * distance), the grasp flag, a placement term and a static term, and sets 5 where success is true | upstream_code | mani_skill/envs/tasks/tabletop/pick_cube.py:177-202 |
| OpenArm is registered with uid openarm and the URDF at robots/openarm/openarm.urdf | upstream_code | mani_skill/agents/robots/openarm/openarm.py:16-19 |
| The openarm reset keyframe is a nine-element joint position array | upstream_code | mani_skill/agents/robots/openarm/openarm.py:33-48 |
| The arm has seven openarm_joint joints and the gripper one openarm_finger_joint1 | upstream_code | mani_skill/agents/robots/openarm/openarm.py:50-61 |
| The arm's pd_ee_delta_pos controller bounds the end-effector position delta to -0.1 and 0.1 | upstream_code | mani_skill/agents/robots/openarm/openarm.py:100-109 |
| The gripper joint position controllers bound the opening to 0 and 0.0451 | upstream_code | mani_skill/agents/robots/openarm/openarm.py:174-190 |
| OpenArm.is_grasping checks pairwise contact forces with a minimum force of 0.5 N and a maximum contact angle of 85 degrees | upstream_code | mani_skill/agents/robots/openarm/openarm.py:255-286 |
| OpenArm.is_static compares the largest absolute joint velocity with a threshold of 0.2 | upstream_code | mani_skill/agents/robots/openarm/openarm.py:288-290 |

Limits: the driver declares two, both on the step action and both from the OpenArm controller configurations.

| limit | source | ref |
|---|---|---|
| `cap.world.step.v1 action.tcp_delta` each element from -0.1 to 0.1 m | upstream_code | mani_skill/agents/robots/openarm/openarm.py:100-109 |
| `cap.world.step.v1 action.gripper` from 0 to 0.0451 m | upstream_code | mani_skill/agents/robots/openarm/openarm.py:183-190 |

The clone does not state a tick bound or a control timestep, so the driver declares neither: `ticks` uses the
catalogue class's 1 to 10000 schema and `fidelity.timestep_ms` is 0 with a gap that says no physical time is modelled.

Shape: the card names the Gymnasium helper, but `PickCubeEnv` inherits ManiSkill's `BaseEnv`, which is not in the clone,
so the Gymnasium family fake (which needs `action_space` and `observation_space`) would fail G7.NOT_UPSTREAM.  This
package is a direct `Driver` over the environment object; the deviation is stated in `driver.py` and in RESULT.json.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `sapien:mani_skill:PickCube-v1`, level F0 (analytic
placeholder kinematics, no dynamics), determinism `seeded` with `seed_control` `parameter`, timestep 0 because the
clone states none, `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore.  The gaps say what is
not modelled, including the full state and camera observations, the arm and its controller, contacts, the other two
tasks and the fact that the fake was never compared with the upstream simulator.

Safety: simulated R0 device.  There is no hardware backend and no physical actuator.  The e-stop is the runtime's
software latch (no native stop exists); after it no step or reset is accepted until `mhs.safety.reset` clears the
latch, and the state stays readable.

Tags: openarm, mani-skill, sapien, pick-cube, tabletop, simulation, reinforcement-learning, robot-arm
