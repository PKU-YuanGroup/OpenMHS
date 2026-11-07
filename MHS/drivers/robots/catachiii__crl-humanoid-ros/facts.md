# Facts and tags for gh.catachiii/crl-humanoid-ros

Every fact cites its source at commit `31202ed7c73ab6b6735d0416274ee9d256ecdf02`: `vendor_doc` (a text file of the
clone) or `upstream_code` (a text file of the clone, `path/in/clone:LINE`). The same facts are in `driver.py`; the
reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The repository is a ROS 2 framework for humanoid robot simulation and control that supports the Unitree G1 and LimX Tron1A platforms | vendor_doc | README.md:5 |
| The repository lists MuJoCo-based software-in-the-loop testing as its simulation role | vendor_doc | README.md:11 |
| The card's first model is the MJCF scene 'g1 scene crl', which includes g1_29dof_crl.xml | upstream_code | crl_humanoid_commons/data/robots/g1_description/scene_crl.xml:1-2 |
| The robot model compiles angles in radians and resolves its meshes from meshes/ | upstream_code | crl_humanoid_commons/data/robots/g1_description/g1_29dof_crl.xml:2 |
| The pelvis body is placed at 0 0 0.793 and carries the free joint floating_base_joint | upstream_code | crl_humanoid_commons/data/robots/g1_description/g1_29dof_crl.xml:44-46 |
| The left hip pitch joint declares range -2.5307 2.8798 and actuatorfrcrange -88 88 | upstream_code | crl_humanoid_commons/data/robots/g1_description/g1_29dof_crl.xml:53 |
| The actuator block has 29 motor actuators, one for each leg, waist and arm joint, and none sets ctrlrange or ctrllimited | upstream_code | crl_humanoid_commons/data/robots/g1_description/g1_29dof_crl.xml:245-275 |
| The model declares gyro and accelerometer sensors for the torso and pelvis IMUs | upstream_code | crl_humanoid_commons/data/robots/g1_description/g1_29dof_crl.xml:277-282 |
| The scene's worldbody adds a directional light and a plane geom named floor | upstream_code | crl_humanoid_commons/data/robots/g1_description/scene_crl.xml:18-21 |
| The G1 simulator declares robot_xml_file with the default g1_description/scene_crl.xml | upstream_code | crl_humanoid_simulator/include/crl_humanoid_simulator/G1SimNode.h:40 |
| initializeMuJoCo loads the robot_xml_file model with mj_loadXML and sets the model option timestep to timeStepSize_ | upstream_code | crl_humanoid_simulator/include/crl_humanoid_simulator/G1SimNode.h:393-414 |
| BaseNode declares the time_step_size parameter with default 0.01 and stores it in timeStepSize_ | upstream_code | crl_humanoid_commons/include/crl_humanoid_commons/nodes/BaseNode.h:36-37 |
| The G1 simulator configuration sets the robot node's time_step_size to 0.001667 | upstream_code | crl_humanoid_simulator/config/g1_sim.yaml:22-24 |
| The repository's crl_humanoid_hardware G1Node names the Unitree SDK2 low-level command and state topics rt/lowcmd and rt/lowstate for the 29 G1 motors | upstream_code | crl_humanoid_hardware/include/crl_humanoid_hardware/G1Node.h:17-30 |
| The README lists MuJoCo 3.3.5 as the simulation dependency | vendor_doc | README.md:78 |

## Shape and deviation from the card

The card says `family: ros` and `helper: RosDriver`, and the registry card's device plan lists
`cap.world.reset.v1`, `cap.world.step.v1` and `cap.world.seed.v1` on a `world.sim` resource. A `RosDriver` over the
ROS 2 graph cannot express a world step or a reset with a state hash: the upstream simulator's ROS surface is a set
of controller and monitor topics plus services, and its physics loop advances at wall-clock timers. The card's
`models[0]` is the MJCF scene the simulator loads, so this package uses the SDK's `MujocoDriver` for that scene. It
serves `cap.world.step.v1` and `cap.world.reset.v1` from the model. `cap.world.seed.v1` is not served: the MuJoCo
bridge exposes no seed input, and a reset restores the model defaults rather than sampling a new state. This is a
recorded DEVIATION FROM THE CARD, not a claim that the ROS 2 node interface is covered.

Only the card's first scene is served. The Tron1A scene and the G1 robot include are other card models and are not
separate resources. The upstream ROS command topics, `remote`/`monitor` messages, `elastic_band`, `restart`, FSM
state switching and the hardware packages are out of scope. `crl_humanoid_hardware` drives the real Unitree G1
through Unitree SDK2 (`rt/lowcmd`, `crl_humanoid_hardware/include/crl_humanoid_hardware/G1Node.h:17-30`) and the
LimX Tron1A through the LimX SDK; that legged-hardware path is not served, reviewed or run here.

## Limits

The G1 actuator block declares 29 `motor` elements with no `ctrlrange`/`ctrllimited`
(`crl_humanoid_commons/data/robots/g1_description/g1_29dof_crl.xml:245-275`). The joint `actuatorfrcrange` values
(e.g. `-88 88` on `left_hip_pitch_joint`, line 53) are joint force ranges, not actuator ctrl ranges, and are not
used as a control envelope. The model therefore states no control bound, so the bridge publishes `action.ctrl` as `operator_required`: the endpoint refuses a step that sets it
(`MHS.SAFETY.LIMITS_UNSET`, before any native call) until the site's `site-limits.json` bounds it, and a
step without `action` keeps the controls as they are. `site-limits.example.json` is operator example data
(-10 to 10 for every control), not a bound of the model; the package invents none. No number is copied from a
catalogue default or from the upstream constructor; a deployment's torque envelope must not claim it came from
the model.

## Mock path

The card prefers the upstream simulator, but MuJoCo is not installed where the gate runs and may not be installed
(no network, no pip). `fake.py` is therefore a package-local stand-in for the `mujoco` module the MuJoCo bridge
imports. It reads the same scene and its include for the free base, the 29 hinge joints, the 29 motors and the
option timestep, but integrates a placeholder torque response; the driver's fidelity `gaps` state every
difference. The fake therefore publishes an F0 fidelity contract (`fidelity_by_backend`, engine
`analytic:stand-in mujoco module (no physics)`), while the class-level F1 MuJoCo contract describes the real
`sim` path (the official `mujoco` module loading the same scene), which was not run.

## Safety

The device is simulated at R0. The MuJoCo family's stop is a software latch in the stock bridge: after an e-stop,
step and reset are refused until `mhs.safety.reset` clears the latch, while the integration state stays readable. There is no
native emergency-stop service, no physical stop and no hardware backend; no physical humanoid is modelled and no
hardware run is claimed. The upstream ROS simulator's own stop path (FSM ESTOP state, soft e-stop flag) is not
bound by this direct model driver.

## Tags

`ros2`, `humanoid`, `unitree`, `g1`, `mujoco`, `simulation`, `world`
