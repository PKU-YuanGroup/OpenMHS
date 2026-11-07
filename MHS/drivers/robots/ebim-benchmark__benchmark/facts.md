# Facts and tags for gh.ebim-benchmark/benchmark

Every fact cites its source at commit `161db49e9eafd34be31e5bdada72d8e2f796c16a`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md) or `upstream_code` (code or XML of the clone). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

The package serves one device: the card's `models[0]`, the Task 1 MuJoCo scene
`task1_mujoco/robotiq_duo_full_scene_minimal_core/duo_full_scene_grasp.xml`. The model file is read from the read-only
clone at the pinned commit and is never copied into this package or imported as code.

| fact | source | ref |
|---|---|---|
| Task 1 teleoperates a mobile dual-arm Franka FR3 platform with Robotiq 2F-85 grippers on a planar-drive base with a vertical spine to route a deformable cable across a fixture board | vendor_doc | task1_mujoco/README.md:38-42 |
| Everything runs in a single MuJoCo process (main.py): robot, cable, board and physics live in one simulation | vendor_doc | task1_mujoco/README.md:53-54 |
| The task environment pins mujoco==3.9.0 | vendor_doc | task1_mujoco/robotiq_duo_full_scene_minimal_core/environment.yml:20 |
| The scene is the MuJoCo model full_robot_board_cable_routing | upstream_code | task1_mujoco/robotiq_duo_full_scene_minimal_core/duo_full_scene_grasp.xml:2 |
| The model uses the implicitfast integrator with timestep 0.0005 s | upstream_code | task1_mujoco/robotiq_duo_full_scene_minimal_core/duo_full_scene_grasp.xml:7 |
| The scene activates the mujoco.elasticity.cable plugin | upstream_code | task1_mujoco/robotiq_duo_full_scene_minimal_core/duo_full_scene_grasp.xml:4 |
| The scene contains a cable composite with count 71 1 1 and initial none, described by its comment as 71 segments | upstream_code | task1_mujoco/robotiq_duo_full_scene_minimal_core/duo_full_scene_grasp.xml:947-949 |
| The cable initialization writes four qpos values at each cable segment's ball joint | upstream_code | task1_mujoco/robotiq_duo_full_scene_minimal_core/teleop/scene.py:113-121 |
| The actuator block declares a spine position actuator with ctrlrange 0 to 0.85, three base velocity actuators with ctrlrange -2.0 to 2.0 and -4.0 to 4.0, seven velocity actuators per FR3 arm with ctrlrange -8 to 8, -10 to 10 and -12 to 12, a position actuator per Robotiq gripper with ctrlrange 0 to 0.8, caster and TMRV steer actuators with ctrlrange -3.14159 to 3.14159, and roll and drive actuators with ctrlrange -80 to 80 | upstream_code | task1_mujoco/robotiq_duo_full_scene_minimal_core/duo_full_scene_grasp.xml:1030-1060 |
| The model has a home keyframe named home | upstream_code | task1_mujoco/robotiq_duo_full_scene_minimal_core/duo_full_scene_grasp.xml:1063 |
| TeleopSession is described as everything the input methods share and it owns the model and data | upstream_code | task1_mujoco/robotiq_duo_full_scene_minimal_core/teleop/session.py:1-7 |
| TeleopSession loads the scene with scene.load_model and constructs mujoco.MjData from the model | upstream_code | task1_mujoco/robotiq_duo_full_scene_minimal_core/teleop/session.py:47-52 |
| TeleopSession resets to the home keyframe when that key exists with mj_resetDataKeyframe and then calls mj_forward | upstream_code | task1_mujoco/robotiq_duo_full_scene_minimal_core/teleop/session.py:53-56 |
| TeleopSession.step_once advances the physics with mujoco.mj_step | upstream_code | task1_mujoco/robotiq_duo_full_scene_minimal_core/teleop/session.py:153 |
| scene.load_model loads the scene XML with mujoco.MjModel.from_xml_path | upstream_code | task1_mujoco/robotiq_duo_full_scene_minimal_core/teleop/scene.py:29 |

## Limits

The driver declares no `Limit` of its own. The only actuation bound is the model's per-actuator `ctrlrange`, which the
MuJoCo bridge derives from the MJCF at load time (`duo_full_scene_grasp.xml:1030-1060`: the spine position actuator
0 to 0.85, the base velocity actuators -2.0 to 2.0 and -4.0 to 4.0, the FR3 arm velocity actuators -8 to 8, -10 to 10
and -12 to 12, the two gripper position actuators 0 to 0.8, the caster and TMRV steer actuators -3.14159 to
3.14159, and the roll and drive actuators -80 to 80). The derived bound's source is the model file itself, so it is
not copied into a driver limit and no operator-required bound is needed. `ticks` is bounded by the family's
`max_ticks` (10000 by default), and the reset input `seed` is accepted as metadata of the bridge and does not seed a
random draw.

## Fidelity contract

`driver.py` publishes the contract the bridge derives: engine `mujoco:full_robot_board_cable_routing`, level F1,
timestep 0.5 ms (`duo_full_scene_grasp.xml:7`), `realtime_factor` 0, clock `lockstep`, reset `full`, snapshot/restore
offered by the bridge, and determinism `seeded` with `seed_control` `none`. The gaps state that the fake is a stand-in
for the MuJoCo library, not the engine; that the 71-count composite cable with initial none is not expanded, so the
real model's 315 qpos and 246 qvel (39 explicit joints plus 69 cable ball joints at 4/3 each) are reduced to the 39
explicit joints in the fake; that reset uses `mj_resetData` rather than the upstream home keyframe; and that the
upstream grasp, cable-plugin, rendering and teleoperation layers are not exposed.

## Tags

benchmark, cable-routing, dual-arm, fr3, manipulation, mobile-base, mujoco, robot, simulation
