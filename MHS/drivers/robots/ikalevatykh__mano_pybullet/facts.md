# Facts and tags for gh.ikalevatykh/mano_pybullet

Every fact cites its source at commit `960c257cf465f8966e770562b66150beaa359230`. `upstream_code` is a line of the
clone; `vendor_doc` is README.md. The same facts are written into `driver.py` (`facts = [...]`); the reference file is
generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| HandLiftEnv-v1 is registered as a gym environment with entry point mano_pybullet.envs:HandLiftEnv | upstream_code | mano_pybullet/envs/__init__.py:9-12 |
| HandLiftEnv is the object-lifting subclass of HandObjectEnv | upstream_code | mano_pybullet/envs/hand_lift_env.py:8 |
| The default target lift height is 0.25 | upstream_code | mano_pybullet/envs/hand_lift_env.py:11 |
| The target height is stored in _target_height at construction | upstream_code | mano_pybullet/envs/hand_lift_env.py:18 |
| The reward is the z coordinate of the object's base position | upstream_code | mano_pybullet/envs/hand_lift_env.py:47-48 |
| The episode is done when the object's z coordinate is greater than the target height | upstream_code | mano_pybullet/envs/hand_lift_env.py:56-57 |
| HandLiftEnv passes itself as the model_path argument of HandObjectEnv | upstream_code | mano_pybullet/envs/hand_lift_env.py:17 |
| The default hand side is the right hand (HAND_RIGHT = 1) and the default control mode is joint space (MODE_JOINT = 1) | upstream_code | mano_pybullet/envs/hand_env.py:19-26 |
| The default constructor selects hand_side=HAND_RIGHT and control_mode=MODE_JOINT | upstream_code | mano_pybullet/envs/hand_env.py:38-41 |
| In joint mode the action per hand is a 3-vector base position bounded by -5.0 to 5.0, a 4-vector base quaternion bounded by -1.0 to 1.0, and the hand model's joint angles | upstream_code | mano_pybullet/envs/hand_env.py:73-80 |
| The observation per hand is a 3-vector base position, a 4-vector base quaternion, a 6-vector constraint force bounded by -10.0 to 10.0, the joint angles, joint velocities bounded by -3.0 to 3.0 and joint torques bounded by -1.0 to 1.0 | upstream_code | mano_pybullet/envs/hand_env.py:81-89 |
| HandObjectEnv extends the observation space with the object's 3-vector base position and 4-vector base quaternion | upstream_code | mano_pybullet/envs/hand_object_env.py:32-37 |
| The hand state is the base position, base orientation, constraint forces, joint positions, joint velocities and joint torques | upstream_code | mano_pybullet/hand_body.py:81-94 |
| HandModel20 is a heuristic rigid model with 20 degrees of freedom | upstream_code | mano_pybullet/hand_model.py:122-123 |
| The dofs_limits property returns the lower and upper limit of every model degree of freedom | upstream_code | mano_pybullet/hand_model.py:58-65 |
| The metadata declares step_time 1.0 / 60.0 seconds | upstream_code | mano_pybullet/envs/hand_env.py:32-36 |
| step() runs int(step_time * 240.0) simulation steps and returns observation, reward, done, info | upstream_code | mano_pybullet/envs/hand_env.py:169-177 |
| reset() sets gravity (0, 0, -10) and deterministicOverlappingPairs=1 | upstream_code | mano_pybullet/envs/hand_env.py:125-128 |
| The gym extra installs gym>=0.17.3 and imageio, and the package requires numpy, chumpy, transforms3d and pybullet>=3.0.6 | upstream_code | setup.py:36-43 |
| The MANO models must be downloaded separately from the MANO website and pointed to by MANO_MODELS_DIR | vendor_doc | README.md:25-29 |
| The README describes HandLiftEnv as the environment whose target is to lift an object | vendor_doc | README.md:46 |

Limits: the driver declares none. The action and observation spaces are gymnasium `Tuple`s, so the bridge derives
structure but no per-element limits from them; the action bounds are the ones in the facts above (base position
-5.0 to 5.0, quaternion -1.0 to 1.0, and the HandModel20 joint limits from `mano_pybullet/hand_model.py:166-182`).
The device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `pybullet:mano_pybullet HandLiftEnv-v1`, level F1
(rigid-body PyBullet dynamics with contacts), determinism `seeded` with `seed_control` `parameter`, timestep 16.67 ms
(one environment step is `int(step_time * 240.0)` PyBullet steps of 1/240 s, with `step_time = 1.0 / 60.0` from
`mano_pybullet/envs/hand_env.py:36` and `:169`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and
restore. The gaps say the fake is kinematic, that the upstream constructor's `super().__init__(self, **kwargs)` passes
the environment object as `model_path` (`mano_pybullet/envs/hand_lift_env.py:17`), that only the default right hand and
HandModel20 are modelled, and that the MANO model files are not included.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step,
reset or seed is accepted until `mhs.safety.reset` clears the latch, and the world state stays readable.

Tags: mano, pybullet, hand, manipulation, reinforcement-learning, simulation, gym
