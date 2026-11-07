# Facts and tags for gh.brave-eai/dexjoco

Every fact cites its source at commit `8d23b0fab23b17a58c4b55f3942e17013aaf8267`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

The package serves the card's main model, the MJCF scene
`dexjoco/dexjoco/sim/envs/xmls/arena_arm_hand_bimanual_assembly.xml` (`models[0]`), as a `MujocoDriver`. It reads the
model file and its includes from the read-only clone; the package copies neither the model nor its assets. The
upstream task environment (`PandaBimanualAssemblyGymEnv`) is the wrapper that loads this scene; the driver serves the
scene itself, not the task layer.

The card lists five bimanual environment entry symbols, and all five exist in the clone: `PandaBimanualAssemblyGymEnv`
(`panda_bimanual_assembly_env.py:29`), `PandaBimanualHanoiGymEnv` (`panda_bimanual_hanoi_env.py:51`),
`PandaBimanualMicrowaveCookGymEnv` (`panda_bimanual_microwave_cook_env.py:26`), `PandaBimanualPhotographGymEnv`
(`panda_bimanual_photograph_env.py:92`) and `PandaBimanualUnlockIpadGymEnv` (`panda_bimanual_unlock_ipad_env.py:26`).
This package serves the first one's scene; the other four task wrappers and their scenes are not served.


| fact | source | ref |
|---|---|---|
| DexJoCo is a MuJoCo-based simulation benchmark and toolkit for task-oriented dexterous manipulation with 11 functionally grounded tasks | vendor_doc | README.md:16-17 |
| The card's main model is the MJCF scene arena_arm_hand_bimanual_assembly.xml, whose root element is '<mujoco model="Arena_Allegro_Bimanual_Assembly">' | upstream_code | dexjoco/dexjoco/sim/envs/xmls/arena_arm_hand_bimanual_assembly.xml:2 |
| The assembly scene includes panda_allegro_bimanual.xml, industri_round_peg_8mm.xml and industri_tray_insert_round_peg_8mm.xml | upstream_code | dexjoco/dexjoco/sim/envs/xmls/arena_arm_hand_bimanual_assembly.xml:3-5 |
| panda_allegro_bimanual.xml includes panda_allegro_right.xml and panda_allegro_left.xml | upstream_code | dexjoco/dexjoco/sim/envs/xmls/panda_allegro_bimanual.xml:3-4 |
| The assembly scene sets the physics timestep to 0.002 s | upstream_code | dexjoco/dexjoco/sim/envs/xmls/arena_arm_hand_bimanual_assembly.xml:7 |
| The assembly environment defines _XML_PATH as xmls/arena_arm_hand_bimanual_assembly.xml | upstream_code | dexjoco/dexjoco/sim/envs/panda_bimanual_assembly_env.py:17 |
| The assembly environment passes _XML_PATH as xml_path to MujocoGymEnv | upstream_code | dexjoco/dexjoco/sim/envs/panda_bimanual_assembly_env.py:52-53 |
| MujocoGymEnv loads the MJCF with mujoco.MjModel.from_xml_path and creates the data with mujoco.MjData | upstream_code | dexjoco/dexjoco/sim/mujoco_gym_env.py:30-33 |
| MujocoGymEnv sets the model time step from its physics_dt argument | upstream_code | dexjoco/dexjoco/sim/mujoco_gym_env.py:34 |
| The right arm has seven motor actuators: joints 1 to 4 have ctrlrange -87 to 87 and joints 5 to 7 have ctrlrange -12 to 12 | upstream_code | dexjoco/dexjoco/sim/envs/xmls/panda_allegro_right.xml:480-486 |
| The right hand has sixteen position actuators, four per finger, whose control ranges come from their default classes | upstream_code | dexjoco/dexjoco/sim/envs/xmls/panda_allegro_right.xml:488-503 |
| The right hand control ranges are base -0.47 to 0.47, proximal -0.196 to 1.61, medial -0.174 to 1.709, distal -0.227 to 1.618, thumb base 0.263 to 1.396, thumb proximal -0.105 to 1.163, thumb medial -0.189 to 1.644 and thumb distal -0.162 to 1.719 | upstream_code | dexjoco/dexjoco/sim/envs/xmls/panda_allegro_right.xml:117-148 |
| The left model declares the same seven motor actuators and sixteen position actuators | upstream_code | dexjoco/dexjoco/sim/envs/xmls/panda_allegro_left.xml:530-557 |
| The left hand control ranges are base -0.47 to 0.47, proximal -0.196 to 1.61, medial -0.174 to 1.709, distal -0.227 to 1.618, thumb base 0.263 to 1.396, thumb proximal -0.105 to 1.163, thumb medial -0.189 to 1.644 and thumb distal -0.162 to 1.719 | upstream_code | dexjoco/dexjoco/sim/envs/xmls/panda_allegro_left.xml:120-151 |
| The peg is a free body: its body element contains a freejoint | upstream_code | dexjoco/dexjoco/sim/envs/xmls/industreal_round_peg_8mm.xml:13-16 |
| The tray insert is a free body: its body element contains a freejoint | upstream_code | dexjoco/dexjoco/sim/envs/xmls/industreal_tray_insert_round_peg_8mm.xml:13-14 |
| The scene has two mocap target bodies, target_right and target_left | upstream_code | dexjoco/dexjoco/sim/envs/xmls/arena_arm_hand_bimanual_assembly.xml:126-131 |
| The assembly environment's reset samples the peg and socket positions, rotates their yaw and sets the Panda and Allegro home poses instead of the model defaults | upstream_code | dexjoco/dexjoco/sim/envs/panda_bimanual_assembly_env.py:359-391 |
| The assembly environment's step takes a right and a left 23-value vector, a 7-value pose plus 16 hand commands per arm | upstream_code | dexjoco/dexjoco/sim/envs/panda_bimanual_assembly_env.py:432-455 |

Limits: the bridge derives the `cap.world.step.v1` input `action.ctrl` from the scene itself (one interval per
actuator, `actuator_ctrlrange`). The class source is `upstream_code` and the reference is the model file, so no
`operator_required` bound is needed. The ranges above are the model's actuator control ranges, not a claim about a
physical robot.

Fidelity: the fake backend is a stand-in for the MuJoCo library (fake.py), not MuJoCo. It parses the scene and its
includes for the actuator count and control ranges, the free-joint layout and the qpos/qvel dimensions, but its
integration is a placeholder first-order motion, and it resolves no mesh, contact, equality, tendon or actuator
constraint. MuJoCo was not importable where the gate ran (no network, no pip), so no trajectory was compared with the
real engine. The gaps are listed in the `fidelity` attribute of `driver.py`.

Tags: dexjoco, bimanual, dexterous-manipulation, panda, allegro, mujoco, simulation
