# Facts and tags for gh.ambench/ambench

Every fact cites its source at commit `60bf5b73041df4eab571f7d9f0a297aeecbf2e0d`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| BaseEnv is a DirectRLEnv subclass and holds the shared simulation lifecycle around one robot profile and control pipeline | upstream_code | source/ambench/ambench/tasks/base/base_env.py:29-30 |
| PressButton extends BaseEnv | upstream_code | source/ambench/ambench/tasks/press_button/press_button_env.py:17 |
| PressButton-Am-EE-Abs-PID-Direct-v0 is registered with entry_point press_button_env:PressButton and env_cfg_entry_point press_button_env_cfg:PressButtonEnvEEAbsPIDCfg | upstream_code | source/ambench/ambench/tasks/press_button/__init__.py:11-16 |
| register_env calls gym.register(id=task_id, entry_point=entry_point, disable_env_checker=True, ...) | upstream_code | source/ambench/ambench/tasks/_registration.py:19-26 |
| For ABSOLUTE_EE_POSE the control pipeline's action_dim returns 8 | upstream_code | source/ambench/ambench/controllers/control_pipeline.py:49-53 |
| The pipeline reads the action position from action[:, :3] and the quaternion from action[:, 3:7], and adds the scene env origins to the position | upstream_code | source/ambench/ambench/controllers/control_pipeline.py:93-95 |
| The end-effector pipeline passes action[:, -1] to compute_gripper_targets | upstream_code | source/ambench/ambench/controllers/control_pipeline.py:150-153 |
| The gripper command is clamped to -1..1 and mapped as -1 closed and +1 open onto the ordered gripper joint targets | upstream_code | source/ambench/ambench/robots/robot_io.py:133-151 |
| The observation for one environment is ee_pos (3), ee_quat (4), ee_lin_vel (3), ee_ang_vel (3), base_pos (3), base_quat (4), base_lin_vel (3), base_ang_vel (3), gripper_width (1), button_pressed (1) and goal_pos (3) | upstream_code | source/ambench/ambench/tasks/press_button/press_button_env.py:81-97 |
| The observation is returned wrapped as {'policy': [one dict per environment]}; arm_joint_pos and arm_joint_vel are added only when the robot profile has arm joints | upstream_code | source/ambench/ambench/tasks/press_button/press_button_env.py:99-106 |
| The base observation space is a gymnasium Dict of float32 Boxes: positions and velocities are unbounded, quaternions are bounded to -1..1 and gripper_width is 0..inf | upstream_code | source/ambench/ambench/tasks/base/base_env_cfg.py:28-39 |
| The PressButton observation space adds button_pressed as a 0..1 Box of one element and goal_pos as an unbounded three-element Box | upstream_code | source/ambench/ambench/tasks/press_button/press_button_env_cfg.py:175-180 |
| The task succeeds when the button plunger joint position is at least button_pressed_threshold | upstream_code | source/ambench/ambench/tasks/press_button/press_button_env.py:36-39 |
| The plunger slide joint travel is 0.0 (unpressed) to 0.01 (fully pressed) and success uses the 0.004 threshold | upstream_code | source/ambench/ambench/tasks/press_button/press_button_env_cfg.py:167-170 |
| The PressButton reward is always zeros, whatever the state | upstream_code | source/ambench/ambench/tasks/press_button/press_button_env.py:108-110 |
| The episode is truncated when episode_length_buf reaches max_episode_length - 1 | upstream_code | source/ambench/ambench/tasks/base/base_env.py:122 |
| The task's episode_length_s is 20 | upstream_code | source/ambench/ambench/tasks/press_button/press_button_env_cfg.py:104 |
| The simulation timestep is 1/120 s and decimation is 1 | upstream_code | source/ambench/ambench/tasks/base/base_env_cfg.py:46-52 |
| BaseEnv sets self.dt = cfg.sim.dt * cfg.decimation | upstream_code | source/ambench/ambench/tasks/base/base_env.py:39 |
| The free end-effector robot starts at position (0.0, 0.0, 1.0) with the identity quaternion and its two finger joints at 0.001 each | upstream_code | source/ambench/ambench/robots/eef.py:29-35 |
| The free end-effector profile names ee_link as its control body, base body and end-effector body | upstream_code | source/ambench/ambench/robots/eef.py:63-65 |
| The wall is at (2.0, 0.0, 1.0) | upstream_code | source/ambench/ambench/tasks/press_button/press_button_env_cfg.py:109 |
| The wall default size is (0.1, 2.0, 2.0) | upstream_code | source/ambench/ambench/scenes/wall.py:18 |
| The button is placed on the wall surface, offset by half the wall thickness in front of the wall | upstream_code | source/ambench/ambench/tasks/press_button/press_button_env_cfg.py:120-127 |
| Each reset randomizes the wall x and y by -0.2..0.2 and its pitch by -0.2..0.2 rad, and the button position on the wall by -0.3..0.3 in y and z | upstream_code | source/ambench/ambench/tasks/press_button/press_button_env_cfg.py:43-68 |
| AM-Bench requires a native Linux host, a discrete NVIDIA GPU and Isaac Sim 5.1 with Python 3.11 | vendor_doc | README.md:42-43 |

Limits: the driver declares none. The clone declares the action dimension (`action_space: int` at
`base_env_cfg.py:47`) but not the Box bounds: Isaac Lab builds the Gym space outside the clone, so the fake publishes
an unbounded eight-value Box and the runtime has no per-element action bound. Nothing here is an
`operator_required` limit because the device is simulated (R0) and no bound is known to state.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `isaaclab:PressButton-Am-EE-Abs-PID-Direct-v0`, level F1
(the upstream Isaac Lab model has rigid-body dynamics and contacts), determinism `seeded` with `seed_control`
`parameter`, timestep 8.333 ms (`base_env_cfg.py:46-52` and `base_env.py:39`: 1/120 s times decimation 1), `realtime_factor` 0, clock `lockstep`, reset `full`, no
snapshot and restore. The gaps say that the fake backend is a kinematic F0 stand-in, that the action bounds and the
observation-space construction live outside the clone, that the fake returns the per-environment observation without
the `policy` wrapper, and that the model was never compared with the Isaac Lab environment or validated against
hardware.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: aerial-manipulation, isaac-lab, isaac-sim, press-button, reinforcement-learning, simulation, gymnasium
