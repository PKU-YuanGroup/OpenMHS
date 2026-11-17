# Facts and tags for gh.nvidia-isaac/video_to_data

Every fact cites the pinned clone at commit `193382a184308f6800331f3db829f76dc4294cfe`.
`vendor_doc` refs name documentation text; `upstream_code` refs name code or a
comment. The reference files are generated from `driver.py`, not from this page.

## Shape and scope

The repository is an end-to-end pipeline that converts human demonstration
videos into simulation-ready assets and physics-grounded robot training data
(`README.md:3`). Its robotic-grounding stage retargets motion and drives Isaac
Lab environments with RSL-RL PPO (`README.md:33`).

DEVIATION FROM THE CARD/RECON: the card names
`flash_chord.envs.rl:RLEnv` as its entry symbol. Its constructor requires a
Scene and Reference (`flash_chord/envs/rl.py:198-213`), and its step takes a Warp
array and returns four Warp buffers (`:472-485`). The scene uses Newton's
SolverMuJoCo; its runtime explicitly supports CPU or CUDA according to where
the Warp arrays live (`flash_chord/runtime/sim.py:3-9`). That API and its
reference/scene construction are not integrated by this model-only package.
The card's `models` list names MuJoCo XML files; `scene_29dof.xml` is
the only `scene`, and the G1 whole-body planner loads it for forward
kinematics (`planner/g1_planner.py:104-110, 406-411`). This package therefore
serves that MuJoCo world through `MujocoDriver`. `RLEnv`, the Isaac Lab
Sharpa-V2D tasks and the FlashCHORD/Newton/Warp/JAX stack are NOT COVERED.

The model is read in place from the read-only clone; it is neither copied nor
modified. The real backend would be the official `mujoco` engine loading the
same file. MuJoCo, a GPU, Isaac Lab, FlashCHORD and a physical G1 were not
installed or run here.

## Facts

| fact | source | ref |
|---|---|---|
| The repository describes itself as an end-to-end pipeline that converts human demonstration videos into simulation-ready assets and physics-grounded robot training data. | vendor_doc | README.md:3 |
| The robotic-grounding stage retargets human motion onto a robot embodiment and drives Isaac Lab environments trained with RSL-RL PPO. | vendor_doc | README.md:33 |
| The G1 whole-body planner loads its MuJoCo scene from planner/assets/mujoco/scene_29dof.xml. | upstream_code | robotic_grounding/source/robotic_grounding/robotic_grounding/planner/g1_planner.py:406-411 |
| The planner constructs a MuJoCo model from that XML path with mujoco.MjModel.from_xml_path, then a mujoco.MjData and mujoco.mj_forward. | upstream_code | robotic_grounding/source/robotic_grounding/robotic_grounding/planner/g1_planner.py:104-110 |
| The scene is a MuJoCo model named 'g1_29dof scene' that includes g1_29dof.xml. | upstream_code | robotic_grounding/source/robotic_grounding/robotic_grounding/planner/assets/mujoco/scene_29dof.xml:1-2 |
| The scene's worldbody adds a directional light and a floor plane to the included robot model. | upstream_code | robotic_grounding/source/robotic_grounding/robotic_grounding/planner/assets/mujoco/scene_29dof.xml:19-21 |
| The G1 model compiles angles in radians and resolves its meshes from ../../../assets/meshes/g1. | upstream_code | robotic_grounding/source/robotic_grounding/robotic_grounding/planner/assets/mujoco/g1_29dof.xml:2 |
| The pelvis body starts at pos 0 0 0.793 and carries the free joint floating_base_joint. | upstream_code | robotic_grounding/source/robotic_grounding/robotic_grounding/planner/assets/mujoco/g1_29dof.xml:63-67 |
| The actuator block declares 29 <motor> actuators, one per actuated G1 joint, each with an explicit ctrlrange. | upstream_code | robotic_grounding/source/robotic_grounding/robotic_grounding/planner/assets/mujoco/g1_29dof.xml:386-419 |
| The hip motors state ctrlrange -88 88, the knee motors -139 139 and the ankle motors -50 50. | upstream_code | robotic_grounding/source/robotic_grounding/robotic_grounding/planner/assets/mujoco/g1_29dof.xml:387-399 |
| The waist yaw motor states ctrlrange -88 88 and the waist roll and pitch motors -50 50. | upstream_code | robotic_grounding/source/robotic_grounding/robotic_grounding/planner/assets/mujoco/g1_29dof.xml:401-403 |
| The shoulder, elbow and wrist-roll motors state ctrlrange -25 25; the wrist pitch and yaw motors state -5 5. | upstream_code | robotic_grounding/source/robotic_grounding/robotic_grounding/planner/assets/mujoco/g1_29dof.xml:405-419 |
| The model asset directory's NOTICE says the G1 and Dex3 robot descriptions are from or derived from Unitree G1 Description assets and are licensed under the BSD 3-Clause License. | vendor_doc | robotic_grounding/source/robotic_grounding/robotic_grounding/planner/assets/mujoco/NOTICE:3-6 |
| The model asset directory's LICENSE is the BSD 3-Clause License of Unitree Robotics. | vendor_doc | robotic_grounding/source/robotic_grounding/robotic_grounding/planner/assets/mujoco/LICENSE:1-3 |
| The robotic_grounding package setup declares license 'Apache 2.0'. | upstream_code | robotic_grounding/source/robotic_grounding/setup.py:36 |
| FlashCHORD's RLEnv constructor requires a Scene and Reference and accepts an optional RLEnvConfig. | upstream_code | robotic_grounding/flash_chord/src/flash_chord/envs/rl.py:198-213 |
| RLEnv.step accepts an optional Warp action array and returns observation, reward, done and truncation buffers. | upstream_code | robotic_grounding/flash_chord/src/flash_chord/envs/rl.py:472-485 |
| The FlashCHORD runtime describes MuJoCo-Warp through Newton's SolverMuJoCo, with CPU or CUDA selected by where the model's Warp arrays live. | upstream_code | robotic_grounding/flash_chord/src/flash_chord/runtime/sim.py:3-9 |

## Contract

`cap.world.step.v1` takes `{ticks, action: {ctrl: [29 numbers]}}` and
`cap.world.reset.v1` takes the class's optional `seed`/`scenario` fields. The
MuJoCo bridge checks each `ctrl` element against the model's
`actuator_ctrlrange` before writing `data.ctrl`, then runs `mj_step` `ticks`
times. The model states every motor range, so the reference shows one derived
per-element bound and the driver declares no bound of its own.

The bridge publishes the world state
`{time_ms, qpos, qvel, ctrl, tick, timestep_ms, seed, native_checkpoint}`.
The free joint gives 7 qpos and 6 qvel entries, and the 29 hinge joints give
29 more of each: 36 `qpos`, 35 `qvel` and 29 `ctrl` entries. `cap.world.seed.v1`
is not served by `MujocoBridge`; a reset restores the model defaults with
`mj_resetData` + `mj_forward` and the class's seed field has no effect.

## Fidelity

The common fidelity is F1: the official `mujoco` engine loading the pinned
scene, with snapshot/restore through the bridge. The real engine path was not
installed or run, so the scene was never compiled and no trajectory was
compared with it. The model states no `<option timestep>`; `0.002 s` is
MuJoCo's library default and the fake's placeholder, not a value in the clone.
The pelvis starts at `0 0 0.793` with every hinge at ref 0, the model has no
keyframe or controller, and the 29 motors take raw torques, so under gravity
the legs are not held unless a caller supplies controls.

The deployed fake is F0: a package-local stand-in for the `mujoco` module. It
parses the same scene and its include for shape, qpos0 and ctrlranges and
advances a placeholder joint state; it loads no mesh, texture, inertia or
contact model, resolves no friction, tendon, equality, joint-limit or force
constraint, and its snapshot uses the bridge's basic profile (time, `qpos`,
`qvel`, `act`, `ctrl`) because it exposes no `mj_getState`/`mj_setState`.
Those differences are listed in `driver.py` and `RESULT.json`.

## Licence

The card pins `CC-BY-4.0 AND Apache-2.0`; the `robotic_grounding` setup
declares Apache 2.0 (`setup.py:36`), while the MuJoCo model assets carry a
Unitree BSD 3-Clause licence (`assets/mujoco/NOTICE:3-6`,
`assets/mujoco/LICENSE:1-3`). The owner decides before publication.

## Safety

The served device is simulated at R0: the only capabilities are
`cap.world.step.v1` and `cap.world.reset.v1`, whose effects are confined to
in-process simulated state (MHS-004 SAFE-006). No physical actuator, robot or
hardware command is exposed. The runtime's software e-stop latch blocks further
step and reset calls until `mhs.safety.reset`; it is not a hardware emergency
stop and makes no physical-safety claim. The model's ctrlranges are simulation
values, not a physical torque certification.
Safety reset advances no ticks and retains the stored control vector. A later
explicit step without a new action reuses it; no external Isaac or FlashCHORD
application is paused by this package.

## Tags

`mujoco`, `mjcf`, `simulation`, `g1`, `humanoid`, `whole-body`, `planner`
