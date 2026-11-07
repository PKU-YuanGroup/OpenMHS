# Facts and tags for gh.nvlabs/humanoidmimicgen

Every fact cites its source at commit `d82844dcec242c82d6b82628ccc45933c3ad5cbd`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (a Python or MJCF file of the clone). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

The package serves the card's primary model, the Unitree G1 MJCF robot
`humanoidmimicgen/locomanipulation/models/assets/robots/unitree_g1/g1_29dof_rev_1_0.xml` (`models[0]`), as a
`MujocoDriver`. It reads the model file from the read-only clone in place; the package copies neither the model nor
its meshes.

| fact | source | ref |
|---|---|---|
| The release packages nine G1 simulation environments and MuJoCo assets | vendor_doc | README.md:21-22 |
| The project requires Linux and Python 3.10; an NVIDIA GPU and CUDA are needed only for WBC execution or EGL rendering, and recorded playback can run CPU-only | vendor_doc | README.md:40-42 |
| MuJoCo is pinned to 3.2.6 and RoboSuite to 1.5.1 | vendor_doc | README.md:46 |
| The package requires Python 3.10 or newer and declares mujoco==3.2.6, numpy==1.26.4, robosuite==1.5.1 and robosuite-models==1.0.0 as dependencies | upstream_code | pyproject.toml:10-25 |
| The card's primary model is the MJCF robot named g1_29dof_with_hand_rev_1_0 with angle unit radian | upstream_code | humanoidmimicgen/locomanipulation/models/assets/robots/unitree_g1/g1_29dof_rev_1_0.xml:1-2 |
| The robot is attached to the world by a free joint named base on the root body | upstream_code | humanoidmimicgen/locomanipulation/models/assets/robots/unitree_g1/g1_29dof_rev_1_0.xml:59-61 |
| The actuator block declares 29 motor actuators | upstream_code | humanoidmimicgen/locomanipulation/models/assets/robots/unitree_g1/g1_29dof_rev_1_0.xml:390-419 |
| The twelve leg motors have control ranges -88 to 88 for hip pitch and hip yaw, -139 to 139 for hip roll and knee, and -50 to 50 for ankle pitch and ankle roll | upstream_code | humanoidmimicgen/locomanipulation/models/assets/robots/unitree_g1/g1_29dof_rev_1_0.xml:391-402 |
| The three waist motors have control ranges -88 to 88 (yaw), -50 to 50 (roll) and -50 to 50 (pitch) | upstream_code | humanoidmimicgen/locomanipulation/models/assets/robots/unitree_g1/g1_29dof_rev_1_0.xml:403-405 |
| The fourteen arm motors have control ranges -25 to 25 for shoulder pitch, shoulder roll, shoulder yaw and elbow, -30 to 30 for wrist roll, and -10 to 10 for wrist pitch and wrist yaw | upstream_code | humanoidmimicgen/locomanipulation/models/assets/robots/unitree_g1/g1_29dof_rev_1_0.xml:406-419 |
| The model declares four IMU sensors: a gyroscope and an accelerometer on the torso site and another pair on the pelvis site | upstream_code | humanoidmimicgen/locomanipulation/models/assets/robots/unitree_g1/g1_29dof_rev_1_0.xml:422-427 |
| The asset section references 33 mesh STL files under meshes/ | upstream_code | humanoidmimicgen/locomanipulation/models/assets/robots/unitree_g1/g1_29dof_rev_1_0.xml:23-57 |
| The G1 robot class is a RoboSuite LeggedManipulatorModel | upstream_code | humanoidmimicgen/locomanipulation/models/robots/manipulators/g1_robot.py:14-15 |
| The G1 constructor loads robots/unitree_g1/g1_29dof_rev_1_0.xml | upstream_code | humanoidmimicgen/locomanipulation/models/robots/manipulators/g1_robot.py:25-32 |
| The left three-finger hand is a separate MJCF model named g1_threefinger_left_hand | upstream_code | humanoidmimicgen/locomanipulation/models/assets/robots/unitree_g1/g1_threefinger_left_hand.xml:1 |
| The left hand MJCF declares seven position actuators | upstream_code | humanoidmimicgen/locomanipulation/models/assets/robots/unitree_g1/g1_threefinger_left_hand.xml:122-140 |
| The right three-finger hand is a separate MJCF model named g1_threefinger_right_hand | upstream_code | humanoidmimicgen/locomanipulation/models/assets/robots/unitree_g1/g1_threefinger_right_hand.xml:1 |
| The right hand MJCF declares seven position actuators | upstream_code | humanoidmimicgen/locomanipulation/models/assets/robots/unitree_g1/g1_threefinger_right_hand.xml:122-142 |
| The left hand gripper loads g1_threefinger_left_hand.xml | upstream_code | humanoidmimicgen/locomanipulation/models/grippers/g1_threefinger_hands.py:26-33 |
| The right hand gripper loads g1_threefinger_right_hand.xml | upstream_code | humanoidmimicgen/locomanipulation/models/grippers/g1_threefinger_hands.py:106-113 |
| LocoManipulationEnv is a RoboSuite ManipulationEnv | upstream_code | humanoidmimicgen/locomanipulation/envs/base.py:122-123 |
| GroundOnly is a pass-through subclass of LocoManipulationEnv | upstream_code | humanoidmimicgen/locomanipulation/envs/base.py:420-421 |
| LMSimpleEnv selects GroundArena as its arena | upstream_code | humanoidmimicgen/locomanipulation/envs/locomanip.py:92-93 |
| GroundArena loads arenas/ground_arena.xml | upstream_code | humanoidmimicgen/locomanipulation/models/scenes/ground_arena.py:33-36 |
| The ground arena MJCF holds the floor plane and four fixed cameras (frontview, birdview, agentview, sideview) | upstream_code | humanoidmimicgen/locomanipulation/models/assets/arenas/ground_arena.xml:14-27 |

## Limits

The driver declares no explicit `Limit`. The bridge loads the served model and derives the one bound of
`cap.world.step.v1` from it: `action.ctrl` is a 29-element array, and each element is bounded by the matching
actuator's `ctrlrange` in `g1_29dof_rev_1_0.xml`. The model's 29 motor control ranges are at lines 391-419: the
twelve leg motors at 391-402, the three waist motors at 403-405 and the fourteen arm motors at 406-419. The bridge
publishes these per-actuator bounds with the model reference; no number is written into this package. `ticks` is
bounded by the MuJoCo family at 1 to 10000.

The device is simulated (R0), so no limit is `operator_required` and there is no site-limits overlay.

## Fidelity contract

`driver.py` `fidelity = {...}`: engine `mujoco:g1_29dof_with_hand_rev_1_0`, level F1 (a rigid-body MJCF, with no
rendering or sensor publication), determinism `seeded` with seed control `none`, `realtime_factor` 0, clock
`lockstep`, reset `full`, snapshot and restore offered through the bridge. The model file sets no
`<option timestep>`; the reference's `timestep_ms` (2.0) is MuJoCo's library default supplied by the fake's
placeholder fallback, not a value stated by the model.

The gaps say that the fake is not the engine, that the model is a bare robot asset with no floor or arena, that the
three-finger hands are separate fragments not included in `models[0]`, that the meshes and the four IMU sensors are
not loaded, that nothing paces wall-clock time, that the card's RoboSuite environment symbols are not run, and that
no physical G1 is modelled.

## Safety

Simulated R0 device. The e-stop is the runtime's software latch: after it, no step or reset is accepted until
`mhs.safety.reset` clears the latch, and the world state stays readable. There is no hardware e-stop, no physical
stop path and no claim of one.

Tags: mujoco, unitree, g1, humanoid, loco-manipulation, simulation, robot
