# Facts and tags for gh.limxdynamics/humanoid-mujoco-sim

Every fact cites its source at commit `4a1f297725660172e590a239020cc08fb3798aa3`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

The package serves the card's primary model, the MJCF file
`humanoid-description/HU_D03_description/xml/HU_D03_03.xml` (`models[0]`), as a `MujocoDriver`. It reads the model file
from the read-only clone; neither the model nor its assets are copied into the package. The card's model files live in
the `humanoid-description` submodule, which the pinned superproject commit records as a gitlink (`160000 commit` in
`git ls-tree`), so no formal Fact cites a line inside it: gate G4 reads the superproject tree and would report
`REF_MISSING`. The bridge still loads the model from the checkout and derives `action.ctrl` from its
`actuator_ctrlrange` at run time; that derived limit is not a package Fact.

| fact | source | ref |
|---|---|---|
| The repository is a MuJoCo simulation environment for LimX humanoid robots (HU_D03, HU_D04) used to visualize models, test motion controllers and validate RL policies before deploying to hardware | vendor_doc | README.md:5 |
| The prerequisites are Linux x86_64; the bundled prebuild/kinematic_projection helper is x86_64-only and simulation functionality is limited on aarch64 | vendor_doc | README.md:12-14 |
| The README installs the LimX motion control SDK wheel from limxsdk-lowlevel/python3/amd64 | vendor_doc | README.md:27 |
| The available models are HU_D03_03 and HU_D04_01 | vendor_doc | README.md:32 |
| The upstream loads the model with mujoco.MjModel.from_xml_path(asset_path) and creates MjData from it | upstream_code | simulator.py:25-26 |
| The upstream takes the actuator count from model.nu and the joint count from model.njnt | upstream_code | simulator.py:29-32 |
| The upstream takes the integration step from model.opt.timestep | upstream_code | simulator.py:45 |
| The upstream subscribes its simulation-side callback with robot.subscribeRobotCmdForSim | upstream_code | simulator.py:69 |
| The simulation loop calls mujoco.mj_step(model, data) on every iteration | upstream_code | simulator.py:84 |
| For the non-floating-base branch the upstream computes data.ctrl from the received RobotCmd as Kp * (q_cmd - q) + Kd * (dq_cmd - dq) + tau | upstream_code | simulator.py:105-115 |
| The upstream publishes the robot state to the LimX SDK with publishRobotStateForSim | upstream_code | simulator.py:132 |
| The upstream initializes the LimX SDK robot with robot.init(robot_ip) before starting the simulation | upstream_code | simulator.py:218 |
| The upstream selects the model from the ROBOT_TYPE environment variable and passes it to SimulatorMujoco | upstream_code | simulator.py:229-236 |

Limits: the bridge derives the `cap.world.step.v1` input `action.ctrl` from the model itself, one interval per
actuator (`actuator_ctrlrange`; the class source is `upstream_code` and the reference is the model file). The package
declares no limit of its own and no `operator_required` bound, because the model file is the system of record for the
control envelope. The runtime refuses an out-of-range element before writing `data.ctrl`.

Fidelity: the fake backend is a stand-in for the MuJoCo library (`fake.py`), not MuJoCo. It reads the model file for
the actuator count, the control ranges and the joint dimensions, but its integration is a placeholder velocity
proportional to each control value and it resolves no mesh, contact, equality, tendon or actuator constraint. MuJoCo
was not importable where the gate ran (no network, no pip), so no trajectory was compared with the real engine. The
gaps are listed in the `fidelity` attribute of `driver.py`.

Tags: limx, hu-d03, humanoid, mujoco, simulation, robot
