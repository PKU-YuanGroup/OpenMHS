# Facts and limits for gh.dfki-ric/deformable_gym

Every fact cites its source at commit `5b67bc9eb28f3c4356c49d0192906fec1752d1a1`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The package registers FloatingMiaGraspInsole-v0 with entry point deformable_gym.envs.floating_mia_grasp_env:FloatingMiaGraspEnv, object_name 'insole_on_conveyor_belt/back' and observable_object_pos True | upstream_code | deformable_gym/__init__.py:6-14 |
| The documented example creates the environment with gymnasium.make('FloatingMiaGraspInsole-v0') | vendor_doc | README.md:78 |
| The floating Mia action space bounds the 3 end-effector position offsets by +-0.0005 and the 4 orientation offsets by +-0.000005 | upstream_code | deformable_gym/envs/floating_mia_grasp_env.py:65-66 |
| The action space has 10 values: 3 position offsets, 4 orientation offsets and 3 finger commands | upstream_code | deformable_gym/envs/floating_mia_grasp_env.py:117-134 |
| The finger bounds of the action space are selected from the motor array with actuated_finger_ids [0, 1, 5] | upstream_code | deformable_gym/envs/floating_mia_grasp_env.py:88-89 |
| The observation is the end-effector pose (7 values), 3 finger joint positions and 6 force readings; with observable_object_pos it appends 3 object position values | upstream_code | deformable_gym/envs/floating_mia_grasp_env.py:162-174 |
| The observation space bounds the position by -2..2 (z 0..2), the quaternion by -1..1, the three finger positions by the motor limits, the six forces by -10..10 and the object position by -2..2 | upstream_code | deformable_gym/envs/floating_mia_grasp_env.py:91-115 |
| The default horizon is 100 environment steps | upstream_code | deformable_gym/envs/base_env.py:45 |
| BaseBulletEnv.step terminates the episode when step_counter reaches the horizon | upstream_code | deformable_gym/envs/base_env.py:171 |
| The simulation registers a time_step subsystem at 100 Hz, with a default time_delta of 0.001 s | upstream_code | deformable_gym/envs/base_env.py:48-72 |
| BaseBulletEnv.reset accepts an options mapping with a hard_reset key that reloads the simulation | upstream_code | deformable_gym/envs/base_env.py:104-105 |
| BaseBulletEnv.reset passes seed and options to gymnasium's Env.reset through super().reset(seed=seed, options=options) | upstream_code | deformable_gym/envs/base_env.py:97-102 |
| The reward is 0.0 until the episode terminates; on termination it is +1.0 when the released object's height is at least 0.9 and -1.0 otherwise | upstream_code | deformable_gym/envs/grasp_env.py:60-79 |
| The initial hand pose is position (0.03, -0.025, 1.0) with Euler angles (-pi/8, pi, 0) converted by pybullet.getQuaternionFromEuler | upstream_code | deformable_gym/envs/floating_mia_grasp_env.py:37-39 |
| MiaHand._correct_index_limit sets the index finger's lower limit to 0.0 and keeps its upper limit | upstream_code | deformable_gym/robots/mia_hand.py:34-37 |
| The j_index_fle URDF limit is -1.399999976 to 1.399999976 | upstream_code | deformable_gym/assets/robots/urdf/mia_hand.urdf:312 |
| The j_little_fle URDF limit is 0 to 1.396260023 | upstream_code | deformable_gym/assets/robots/urdf/mia_hand.urdf:326 |
| The j_thumb_opp URDF limit is -0.628 to 0.0 | upstream_code | deformable_gym/assets/robots/urdf/mia_hand.urdf:371 |
| MiaHand.get_sensor_readings returns six force values | upstream_code | deformable_gym/robots/mia_hand.py:91-102 |

## Limits

The driver declares no limit of its own. The 10 action values are bounded by the environment's Box action space,
which the Gymnasium bridge derives from the live environment (`cap.world.step.v1`, limit paths `action.values[*]`)
at load time; those rules carry no source and the reference
`action_space of the fake backend .fake:FakeFloatingMiaGraspEnv`, and the family path is exempt from the clone-line
reference check (`_derived` in the gate). The fake publishes the bounds above so it can serve the same contract on
the gate. The device is simulated (R0), so no limit is `operator_required` and no operator overlay is needed.

## Fidelity contract

`driver.py` publishes engine `gymnasium:FloatingMiaGraspInsole-v0`, level F1, determinism `seeded` with
`seed_control` `parameter`, `timestep_ms` 10.0 (the 100 Hz `time_step` subsystem), `realtime_factor` 0, clock
`lockstep`, reset `full`, no snapshot and restore, and the gaps that say what the fake does not model (no soft-body
physics, no force simulation, no rendering, a placeholder terminal reward and no comparison with a real run).

## Safety

Simulated R0 device: there is no hardware backend and no machine to stop. The runtime's software latch stops the
simulation after an e-stop: no step or reset is accepted until `mhs.safety.reset` clears it, and the state stays
readable.

Tags: grasping, deformable-object, reinforcement-learning, simulation, pybullet, gymnasium
