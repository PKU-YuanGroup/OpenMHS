# Facts and tags for gh.princeton-robot-planning-and-learning/kindergarden

Every fact cites its source at commit `5b2dbac482142b879b48449b3fa2af63f641aed3`. The model is the card's models[2],
`src/kinder/envs/dynamic3d/models/rby1a/rby1a_model_v1.2.xml`, read from the read-only clone in place. The same facts
are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| KinDER is a physical reasoning benchmark for robot learning and planning | vendor_doc | README.md:7 |
| The package declares mujoco~=3.3.0 as a dependency | upstream_code | pyproject.toml:29 |
| The RBY1A model is the MJCF model rby1, compiled in radians with autolimits and eulerseq xyz | upstream_code | src/kinder/envs/dynamic3d/models/rby1a/rby1a_model_v1.2.xml:1-25 |
| The model sets no option timestep: its two `<option>` elements name only the implicitfast integrator and the elliptic cone; the only timestep text is a commented-out line | upstream_code | src/kinder/envs/dynamic3d/models/rby1a/rby1a_model_v1.2.xml:2-5 |
| The root default class gives every motor the control range -3000000 to 3000000 and ctrllimited true | upstream_code | src/kinder/envs/dynamic3d/models/rby1a/rby1a_model_v1.2.xml:10-11 |
| The model declares 24 motors: two wheel, six torso, seven left arm, seven right arm and two head motors, all without a local ctrlrange so the root default applies | upstream_code | src/kinder/envs/dynamic3d/models/rby1a/rby1a_model_v1.2.xml:267-296 |
| The model has one free root joint (world_j) and 28 hinge or slide joints: the two wheels, six torso joints, seven joints per arm, two fingers per gripper and two head joints | upstream_code | src/kinder/envs/dynamic3d/models/rby1a/rby1a_model_v1.2.xml:83-249 |
| The joint limits are stated per joint; examples are torso_0 -0.349066 to 0.349066 rad, torso_1 -1.0472 to 1.52173 rad and right_arm_4 -6.28319 to 6.28319 rad | upstream_code | src/kinder/envs/dynamic3d/models/rby1a/rby1a_model_v1.2.xml:100-153 |
| The two fingers of a gripper are coupled by an equality constraint | upstream_code | src/kinder/envs/dynamic3d/models/rby1a/rby1a_model_v1.2.xml:262-264 |
| The dynamic3d RBY1A robot environment inserts rby1a_model_v1.2.xml into the task scene XML | upstream_code | src/kinder/envs/dynamic3d/robots/rby1a_robot_env.py:104-108 |
| The dynamic3d env selects RBY1ARobotEnv when the task's robot type is rby1a | upstream_code | src/kinder/envs/dynamic3d/envs.py:149-153 |
| The base MuJoCo environment defines SIMULATION_TIMESTEP as 0.0005 s | upstream_code | src/kinder/envs/dynamic3d/mujoco_utils.py:27 |
| The base MuJoCo environment writes its SIMULATION_TIMESTEP into the XML option element before loading the model | upstream_code | src/kinder/envs/dynamic3d/mujoco_utils.py:774-781 |

Limits: the driver declares none of its own. The only physical bound is the model's per-actuator `actuator_ctrlrange`,
which the MuJoCo bridge derives from the model file (root default `-3000000..3000000`, `rby1a_model_v1.2.xml:10-11`) and
which the runtime enforces before any native call. `ticks` is bounded by the bridge's `max_ticks` (10000 by default).
The device is simulated (R0), so no bound is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `mujoco`, level F1, determinism `exact` (one model, one
state, no random element; the bridge records a seed that does not select the initial state), timestep 2.0 ms, realtime
factor 0, clock `lockstep`, reset `full`, snapshot and restore offered by the bridge's integration state. The model file
states no `<option timestep>`, so the 2.0 ms value is the fake backend's placeholder for MuJoCo's library default; the
upstream environment sets 0.0005 s when it composes a scene (`mujoco_utils.py:27,774-781`), and the gap list says this is
not verified. The gaps also say that the fake is not the engine, that the task environments and their objects, rewards
and episode limits are not served, that meshes and rendering are not resolved, and that nothing ran in MuJoCo or on
hardware.

Safety: simulated R0 device. The e-stop is the runtime's software latch (the family exposes no native stop); after it no
step or reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the
state stays readable.

Tags: kinder, mujoco, mobile-manipulator, rby1a, simulation, world
