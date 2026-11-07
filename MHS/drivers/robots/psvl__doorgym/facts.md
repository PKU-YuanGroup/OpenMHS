# Facts and tags for gh.psvl/doorgym

Every fact cites its source at commit `903493a6bd518bed5452c683c3857f1bfc5a209d`; `upstream_code` means a code line of
the clone and the path is relative to the clone root. The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| blue-doorenv-v1 is registered with entry point doorenv2.envs:DoorEnvBlueV1 and max_episode_steps=512 | upstream_code | doorenv2/doorenv2/__init__.py:3-7 |
| DoorEnvBlueV1 is defined in doorenv_blue.py as a DoorEnv subclass | upstream_code | doorenv2/doorenv2/envs/doorenv_blue.py:12 |
| DoorEnvBlueV1 passes world_path to DoorEnv; the constructor default is /home/demo/DoorGym/world_generator/world/pull_floatinghook | upstream_code | doorenv2/doorenv2/envs/doorenv_blue.py:13-26 |
| DoorEnv sets self.xml_path = self.random_world(world_path) | upstream_code | doorenv2/doorenv2/envs/doorenv.py:36 |
| random_world chooses one entry of world_path with random.choice(os.listdir(world_path)) | upstream_code | doorenv2/doorenv2/envs/doorenv.py:314-318 |
| For a world file whose name contains gripper and not float or mobile, DoorEnv sets nn to 8 | upstream_code | doorenv2/doorenv2/envs/doorenv.py:58-62 |
| frame_skip is 20 | upstream_code | doorenv2/doorenv2/envs/doorenv.py:73 |
| DoorEnv.step advances the simulation with do_simulation(a, self.frame_skip) | upstream_code | doorenv2/doorenv2/envs/doorenv.py:128 |
| The pull_blue_right_v2_gripper_motor world includes the gripper-motor robot and sets the MuJoCo timestep to 0.001 s | upstream_code | world_generator/world/pull_blue_right_v2_gripper_motor/1555111990_pull_blue_right_v2_gripper_motor.xml:4-5 |
| The gripper-motor robot has seven joint motors with ctrlrange -1.0 to 1.0 | upstream_code | world_generator/robot/blue_right_v2_gripper_motor.xml:4-10 |
| The right_gripper_joint position actuator of that robot has ctrlrange 0 to 1.05 | upstream_code | world_generator/robot/blue_right_v2_gripper_motor.xml:18 |
| The gripper-motor robot defines twelve actuators: seven joint motors and five position actuators | upstream_code | world_generator/robot/blue_right_v2_gripper_motor.xml:3-22 |
| DoorEnv initialises gripper_action with four zeros | upstream_code | doorenv2/doorenv2/envs/doorenv.py:35 |
| For a gripper world DoorEnv builds the action Box from model.actuator_ctrlrange with the last gripper_space bounds removed | upstream_code | doorenv2/doorenv2/envs/doorenv.py:76-83 |
| DoorEnvBlueV1.gripper_action_gen builds four finger commands from the last action value | upstream_code | doorenv2/doorenv2/envs/doorenv_blue.py:29-31 |
| DoorEnv._get_obs concatenates get_robot_joints and get_dist_vec when vision is off | upstream_code | doorenv2/doorenv2/envs/doorenv.py:268-273 |
| DoorEnvBlueV1.get_robot_joints returns the first nn qpos and qvel values | upstream_code | doorenv2/doorenv2/envs/doorenv_blue.py:133-136 |
| get_dist_vec is get_finger_target minus get_knob_target | upstream_code | doorenv2/doorenv2/envs/doorenv.py:404-405 |
| get_finger_target averages the positions of the fingerleft2 and fingerright2 geoms for a gripper world | upstream_code | doorenv2/doorenv2/envs/doorenv_blue.py:138-143 |
| get_knob_target averages the positions of door_knob_2 and door_knob_3 for a pull world | upstream_code | doorenv2/doorenv2/envs/doorenv.py:391-394 |
| DoorEnv.step returns (observation, reward, done, info) with done False | upstream_code | doorenv2/doorenv2/envs/doorenv.py:130-135 |
| For gripper worlds the control penalty is -mean(square(a[:-2])) | upstream_code | doorenv2/doorenv2/envs/doorenv.py:110-111 |
| reset_model draws the hooked and untucked chances with np.random.randint(100) | upstream_code | doorenv2/doorenv2/envs/doorenv.py:165-172 |
| The non-float, non-mobile reset sets the first seven joint qpos from uniform(-0.1, 0.1) and draws the two-value pull goal from np_random.uniform(-0.15, 0.15) | upstream_code | doorenv2/doorenv2/envs/doorenv_blue.py:57-74 |
| The training utility installs an observation Box of nn*2+3 values | upstream_code | util.py:61 |

Limits: the driver declares none. The only bound is the ``action.values`` Box that the Gymnasium bridge derives from
the environment's ``action_space``; for the ``pull_blue_right_v2_gripper_motor`` world it is seven values in
[-1, 1] plus the gripper value in [0, 1.05], from the robot's actuator ``ctrlrange`` (robot XML:4-10,18) with the last
``gripper_space`` bounds removed (``doorenv2/doorenv2/envs/doorenv.py:76-83``). The device is simulated (R0), so no
limit is ``operator_required`` and no ``site-limits.example.json`` is needed.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `mujoco:blue-doorenv-v1`, level F1 (MuJoCo rigid-body
dynamics with contacts in the deployed model), determinism `seeded` with `seed_control` `parameter`, timestep 20 ms
(the world's 0.001 s times ``frame_skip`` 20), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and
restore. The gaps say that the fake is a pure-Python analytic stand-in with placeholder values, that it models one
generated world, that the environment publishes no observation space, that the 512-step limit is applied by gym's
TimeLimit wrapper, that the default ``world_path`` is a placeholder, and that nothing was compared with upstream or
validated against hardware.

Safety: simulated R0 device. There is no hardware transport and no native stop in the upstream class; the e-stop is the
runtime's software latch and after it no step or reset is accepted until `mhs.safety.reset` clears the latch. The state
stays readable.

Tags: doorgym, door-opening, mujoco, gym, reinforcement-learning, simulation, robot-arm, blue
