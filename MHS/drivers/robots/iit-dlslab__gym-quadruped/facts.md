# Facts and tags for gh.iit-dlslab/gym-quadruped

Every fact cites a source at commit `097a8d649ae2232d3c0ed5eb83dc0e4f77483019`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page. The clone is
read-only and was not imported or installed.

| fact | source | ref |
|---|---|---|
| QuadrupedEnv is constructed from a robot name and defaults to the flat scene, the default observation names, sim_dt 0.002 s, the forward velocity command of 0.5 m/s and 0.0 rad/s, ground friction 1.0 and the leg order FL, FR, RL, RR | upstream_code | gym_quadruped/quadruped_env.py:85-99 |
| The default observations are qpos, qvel, tau_ctrl_setpoint, feet_pos:base and feet_vel:base | upstream_code | gym_quadruped/quadruped_env.py:80 |
| The observation space is a gymnasium Dict of Box bounds built from the model's joint ranges and actuator control ranges | upstream_code | gym_quadruped/utils/quadruped_utils.py:250-326 |
| The action space is a gymnasium Box of shape (mjModel.nu,): one torque per actuator, with low and high taken from actuator_forcerange | upstream_code | gym_quadruped/quadruped_env.py:224-235 |
| The scene model is loaded from robot_model/scene_<scene>.xml and its terrain is generated for the robot's hip height | upstream_code | gym_quadruped/quadruped_env.py:150-155 |
| The go2 robot configuration uses robot_model/go2/go2.xml and a hip height of 0.28 m | upstream_code | gym_quadruped/robot_cfgs.py:43-44 |
| The simulation timestep is the sim_dt constructor argument and is assigned to mjModel.opt.timestep | upstream_code | gym_quadruped/quadruped_env.py:182-183 |
| A step writes the action to mjData.ctrl, advances MuJoCo with one mj_step and then steps every configured sensor | upstream_code | gym_quadruped/quadruped_env.py:279-284 |
| A step returns the observation, reward, terminated, truncated and info; info carries time, step_num and invalid_contacts | upstream_code | gym_quadruped/quadruped_env.py:287-300 |
| The reward is the constant 0 | upstream_code | gym_quadruped/quadruped_env.py:1147-1150 |
| An episode terminates on an invalid contact or on leaving the terrain bounds; step never truncates | upstream_code | gym_quadruped/quadruped_env.py:292-296 |
| A random reset adds white noise of +-20 degrees to joint positions and +-0.5 to joint velocities around the model keyframe, with an options angle_sweep override for the position amplitude | upstream_code | gym_quadruped/quadruped_env.py:352-360 |
| reset(seed) seeds numpy's global random generator | upstream_code | gym_quadruped/quadruped_env.py:348-349 |
| reset returns the observation dictionary from _get_obs() | upstream_code | gym_quadruped/quadruped_env.py:416 |
| A reset randomizes the ground tangential friction coefficient from the configured ground_friction_coeff range | upstream_code | gym_quadruped/quadruped_env.py:412-414 |
| close() closes the viewer if one was opened and clears it | upstream_code | gym_quadruped/quadruped_env.py:880-885 |

Limits: the driver declares none of its own. The only bounds come from the catalogue classes and the bridge:
`cap.world.step.v1.ticks` is 1 to 10000 (the family's `max_ticks`), and the action is one torque per actuator, shaped
by the environment's action space. The upstream action-space construction reads `actuator_forcerange` and
`actuator_forcelimited` (quadruped_env.py:225-233), so the driver does not claim a torque envelope of its own and does
not narrow the simulator. The device is simulated (R0) and no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `mujoco:gym_quadruped.QuadrupedEnv(go2, flat)`, level F1
(rigid-body dynamics with contacts), determinism `seeded` with `seed_control` `parameter`, timestep 2.0 ms (the
`sim_dt` default 0.002 s, quadruped_env.py:90 and :183), `realtime_factor` 0, clock `lockstep`, reset `full`, no
snapshot and restore (the environment exposes no get_state/set_state). The gaps say what is not modelled: F2 is not
claimed, the fake has no contacts or actuator model and never terminates, no physical quadruped is modelled, and the
fake was not compared with the upstream simulator.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: quadruped, legged-locomotion, mujoco, reinforcement-learning, simulation, gymnasium
