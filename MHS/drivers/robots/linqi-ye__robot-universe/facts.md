# Facts and tags for gh.linqi-ye/robot-universe

Every fact cites its source at commit `3f2de2ab27f18cd677cf159afe1992a42daa24d8`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (an MJCF file of the clone). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

The package serves the card's first model, the MJCF scene `go_bdx/scene.xml` (`models[0]`), as a `MujocoDriver`.
It reads the model file from the read-only clone; neither the model nor its meshes are copied into the package. The
upstream repository is a collection of robot description files (`README.md:1-2`); its ROS content is description
packages whose launch files display or spawn models and one ROS 1 visualisation node (`panda5_test/src/panda5.cpp`
receives UDP state and publishes joint states), none of which accepts a command, and the go_bdx directory has no ROS
file, so the card's static `family:ros` / `RosDriver` shape has no pinned command endpoint or type to bind. The package follows the MJCF instead. The card's other models
(`birdy_v1/mujoco/scene_birdy_v1.xml`, `birdy_v1/mujoco/scene_birdy_v1_L.xml`, `PF_P441A/xml/robot.xml` and
`PF_TRON1A/xml/robot.xml`) are not served; one package serves one model.

| fact | source | ref |
|---|---|---|
| The repository describes itself as a comprehensive collection of robot URDF models. | vendor_doc | README.md:1-2 |
| The package's model is the MJCF scene go_bdx/scene.xml, whose root element is '<mujoco model="bdx scene">' and which includes go_bdx.xml on line 2. | upstream_code | go_bdx/scene.xml:1-2 |
| The scene adds a gradient skybox, a checkered groundplane and a floor plane body to the included robot model. | upstream_code | go_bdx/scene.xml:13-22 |
| The included model's root element is '<mujoco model="bdx">' and its compiler sets angle='radian', meshdir='meshes' and autolimits='true'. | upstream_code | go_bdx/go_bdx.xml:1-2 |
| The model's option line selects the implicitfast integrator; the timestep option on line 4 is commented out. | upstream_code | go_bdx/go_bdx.xml:4-5 |
| The bdx default class sets joint limited='true', and its six joint-parameter classes set range='-0.785398 0.785398'. | upstream_code | go_bdx/go_bdx.xml:8-35 |
| The bdx body declares a freejoint, and its pelvis body sets childclass 'bdx'. | upstream_code | go_bdx/go_bdx.xml:62-65 |
| The actuator section declares 16 position actuators with gear 1 and explicit ctrlrange values: the hip, knee, ankle and neck actuators use -30 to 30, the head actuators -5.55 to 5.55, and the antenna actuators -13.62 to 13.62. | upstream_code | go_bdx/go_bdx.xml:163-179 |
| The same actuator lines set forcerange -23.7 to 23.7 for the hip, knee, ankle and neck actuators, -7.3 to 7.3 for the head actuators and -0.2943 to 0.2943 for the antenna actuators. | upstream_code | go_bdx/go_bdx.xml:163-179 |
| The model declares six sensors on the imu site: orientation, position, angular velocity, linear velocity, linear acceleration and a magnetometer. | upstream_code | go_bdx/go_bdx.xml:181-188 |
| The mesh assets declare scale='0.001 0.001 0.001' for every STL mesh. | upstream_code | go_bdx/go_bdx.xml:42-58 |
| panda5_test/src/panda5.cpp initialises the ROS 1 node panda_visual and advertises joint_states and CPU-sample, mode and leg-end topics. | upstream_code | panda5_test/src/panda5.cpp:233-253 |

Limits: the package declares no Limit of its own. The bridge derives `cap.world.step.v1` input `action.ctrl` from
the model itself, one interval per actuator from `actuator_ctrlrange`: the model declares 16 `<position>` actuators
and each has an explicit `ctrlrange` (`go_bdx/go_bdx.xml:163-179`). The derived reference is the model file, and the
bridge refuses an out-of-range element before writing `data.ctrl`. The model's joint ranges (`go_bdx/go_bdx.xml:8-35`)
are narrower than those control ranges; the bridge bounds the control input, not the joint, and this package does not
reinterpret a joint limit as a control limit or invent one. No bound was copied from a catalogue default or from a
constructor default.

Fidelity: the fake backend is a stand-in for the MuJoCo library (`fake.py`), not MuJoCo. It expands the scene's
`<include>` and reads the model file for the joint dimensions (one freejoint and 16 hinges, so 23 qpos and 22 qvel),
the 16 actuators and their ctrlranges, but its integration is a placeholder first-order motion; it resolves no mesh,
contact, equality, tendon or sensor, and it does not integrate the freejoint. The fake's 0.002 s timestep is a
placeholder for MuJoCo's library default because the clone states no timestep. The fake exposes no
`mj_getState`/`mj_setState`/`mj_stateSize`, so the bridge uses its basic checkpoint profile. MuJoCo was not importable
where the gate ran, so no trajectory was compared with the real engine. Since the model review of 2026-11-05 the
fake backend publishes its own F0 contract (`fidelity_by_backend` in `driver.py`, engine `analytic:stand-in mujoco
module (no physics)`); the class-level F1 `mujoco:bdx scene` contract describes the real engine path, which was not
run. The stand-in also ignores the joint ranges, which MuJoCo would enforce. The gaps of both contracts are in
`driver.py`.

Tags: bdx, go-bdx, mujoco, robot-universe, simulation, model
