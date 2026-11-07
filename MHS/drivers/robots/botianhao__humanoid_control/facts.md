# Facts and tags for gh.botianhao/humanoid_control

Every fact cites its source at commit `cfb27eb205d6ee21a801abe273ffc0a53d3be0f2`: `upstream_code`
(`path/in/clone.py:LINE`) or `vendor_doc` (a text file of the clone). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The MJCF root element declares the model humanoid-legged-description and uses radians | upstream_code | humanoid_legged_description/mjcf/humanoid_legged_control_.xml:1-2 |
| The model option sets timestep 0.001 s, 50 iterations, the PGS solver, gravity 0 0 -9.81 and noslip_iterations 20 | upstream_code | humanoid_legged_description/mjcf/humanoid_legged_control_.xml:4 |
| The base_link body carries a freejoint | upstream_code | humanoid_legged_description/mjcf/humanoid_legged_control_.xml:70-71 |
| The left leg is a chain of six hinge joints from leg_l1_joint to leg_l6_joint, the right leg is a chain of six hinge joints from leg_r1_joint to leg_r6_joint, and each joint declares its own range and actuatorfrcrange | upstream_code | humanoid_legged_description/mjcf/humanoid_legged_control_.xml:103-164 |
| The actuator section declares twelve motor actuators, one per leg hinge, each with ctrllimited true and a ctrlrange of -150 to 150, -200 to 200 or -90 to 90 depending on the joint | upstream_code | humanoid_legged_description/mjcf/humanoid_legged_control_.xml:179-192 |
| The model provides a keyframe named home whose qpos is 0 0 1.5, the identity quaternion and twelve zero joint angles | upstream_code | humanoid_legged_description/mjcf/humanoid_legged_control_.xml:233-239 |
| mujoco_base.MuJoCoBase.__init__ loads the XML path with mujoco.MjModel.from_xml_path and creates an MjData | upstream_code | humanoid_mujoco_sim/humanoid_mujoco_sim/mujoco_base.py:6-19 |
| The module function main of humanoid_sim initialises rclpy, resolves the installed humanoid_legged_description share path to mjcf/humanoid_legged_control_.xml and constructs HumanoidSim with it | upstream_code | humanoid_mujoco_sim/humanoid_mujoco_sim/humanoid_sim.py:279-286 |
| init_base_pos is 0 0 0.82 and init_joint_pos is twelve joint values, both defined at module scope | upstream_code | humanoid_mujoco_sim/humanoid_mujoco_sim/humanoid_sim.py:17-18 |
| After super().__init__ loads the model, HumanoidSim.__init__ sets qpos[:3] to init_base_pos, qpos[3:7] to a scipy quaternion of init_base_eular_zyx and the last twelve qpos values to init_joint_pos | upstream_code | humanoid_mujoco_sim/humanoid_mujoco_sim/humanoid_sim.py:22-60 |
| HumanoidSim computes data.ctrl as targetTorque plus Kp and Kd errors against targetPos, targetVel and the last twelve qpos/qvel values, then calls mj.mj_step | upstream_code | humanoid_mujoco_sim/humanoid_mujoco_sim/humanoid_sim.py:127-131 |
| HumanoidSim's node publishes /jointsPosVel, /ground_truth/state, /imu, /realTorque and /pauseFlag and subscribes to /targetTorque, /targetPos, /targetVel, /targetKp and /targetKd | upstream_code | humanoid_mujoco_sim/humanoid_mujoco_sim/humanoid_sim.py:45-55 |
| HumanoidSim sets simend to 1000.0 s and sim_rate to 1000.0 Hz | upstream_code | humanoid_mujoco_sim/humanoid_mujoco_sim/humanoid_sim.py:28-29 |
| The simulation loop runs until the GLFW window close flag; each outer pass runs inner iterations while no more than 1/60 s of simulated time has passed since the pass began and the pause flag is clear, and calls mj_step only when the wall clock has advanced by 1 / sim_rate | upstream_code | humanoid_mujoco_sim/humanoid_mujoco_sim/humanoid_sim.py:118-132 |

Limits: the driver declares none of its own. `cap.world.step.v1` takes `{ticks, action: {ctrl: [12 numbers]}}`; the
bridge checks every `ctrl` element against the model's `actuator_ctrlrange`
(`humanoid_legged_description/mjcf/humanoid_legged_control_.xml:179-192`) before writing `data.ctrl`, and refuses an
out-of-range value with `MHS.SAFETY.ENVELOPE_VIOLATION` without calling `mj_step`. `ticks` is bounded by the bridge
(1 to `max_ticks`, 10000 by default). The device is simulated (R0), so no bound is `operator_required` and no
`site-limits.example.json` is needed.

Contract: `MujocoDriver` serves `cap.world.step.v1` and `cap.world.reset.v1` on the `world` resource. A step applies
the control vector and integrates `ticks` times; the state is `{time_ms, qpos, qvel, ctrl, tick, timestep_ms, seed}`,
with 19 qpos values (a free base of 7 plus 12 hinges) and 18 qvel values (a free base of 6 plus 12 hinges). A reset
calls `mj_resetData` and `mj_forward`, restoring the model defaults; a seed is accepted for the class contract but
MuJoCo does not use it.

DEVIATION FROM THE CARD: the card named `RosDriver` (`family: ros`, `helper: RosDriver`). Recon found no ROS
service or action for stepping, resetting or stopping the simulated world, and the only ROS 2 surface is the topic
list in the last two Facts. The environment is the card's MuJoCo model, so this package serves it through
`MujocoDriver`; RESULT.json records the deviation.

Fidelity contract (`driver.py`): `fidelity` describes the real engine (engine `mujoco:humanoid_legged_control_`,
level F1) for the backend that imports `mujoco`, and `fidelity_by_backend["fake"]` describes the stand-in that the
gate runs (engine `analytic:stand-in mujoco module (no physics)`, level F0); before the model review of 2026-11-04
the fake was published with the F1 contract. Both use determinism `none` with `seed_control` `none`, timestep 1 ms
(the MJCF's `timestep="0.001"`, line 4), `realtime_factor` 0, clock `lockstep`, reset `full`, snapshot and restore
available through the bridge's basic MuJoCo checkpoint profile (the stand-in does not implement
`mj_getState`/`mj_setState`). The gaps state that the fake is not MuJoCo, that it loads no meshes or contacts, that the upstream node overrides the start state to 0.82 and
twelve init angles and computes `data.ctrl` from target topics, that `mj_resetData` restores the model defaults and
does not apply the home keyframe, that the upstream loop is wall-clock paced, that the ROS topics and controller
nodes are not used, and that no trajectory was compared with the real engine or a physical humanoid.

Safety: simulated R0 device. The e-stop is the runtime's software latch; there is no native stop and no physical
e-stop claim. After an e-stop no step or reset is accepted until `mhs.safety.reset` clears the latch, and the state
stays readable.

Tags: botianhao, humanoid, legged, mujoco, simulation, robot
