# Facts and tags for gh.fdcl-gwu/gym-rotor

Every fact cites its source at commit `86a25517f401a5ca3a4f393e4f0c04104a04d3a1` as `upstream_code`
(`path/in/clone:LINE`). The same facts are written into `driver.py` (`facts = [...]`); `reference.json` and
`REFERENCE.md` are generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Quad-v0 is registered with entry point gym_rotor.envs:QuadEnv and max_episode_steps=10000 | upstream_code | gym_rotor/__init__.py:3-7 |
| The action space is Box(-1.0, 1.0, shape=(4,)): four normalized motor commands | upstream_code | gym_rotor/envs/quad.py:126-132 |
| A normalized action is linearly scaled from [-1, 1] to [min_force, max_force] and clipped to that range before it becomes the four motor thrusts | upstream_code | gym_rotor/envs/quad.py:225-235 |
| The nominal quadrotor is mass 2.15 kg, arm length 0.23 m, inertia diag(0.022, 0.022, 0.035) kg m^2, torque-to-thrust coefficient 0.0135, thrust-to-weight coefficient 2.2 and standard gravity 9.81 m/s^2 | upstream_code | gym_rotor/envs/quad.py:27-33 |
| Each motor thrust is bounded by min_force 0.5 N and max_force = c_tw_nominal * hover_force, with hover_force = m * g / 4 | upstream_code | gym_rotor/envs/quad.py:36-42 |
| The simulation runs at 200 Hz, so one control step is dt = 1/200 s = 0.005 s | upstream_code | gym_rotor/envs/quad.py:59-61 |
| The default integrator is solve_ivp | upstream_code | gym_rotor/envs/quad.py:62 |
| The solve_ivp branch integrates over one dt per step with method DOP853 | upstream_code | gym_rotor/envs/quad.py:263-266 |
| The state limits are x_lim 1.0 m, v_lim 4.0 m/s, W_lim 2*pi rad/s and euler_lim 85 degrees | upstream_code | gym_rotor/envs/quad.py:103-107 |
| The observation space is an 18-element Box: position x (3), velocity v (3), rotation matrix entries (9) and angular velocity W (3), with x bounded by +-x_lim, v by +-v_lim, the rotation entries by +-1 and W by +-W_lim | upstream_code | gym_rotor/envs/quad.py:108-124 |
| The state vector is (x[0:3]; v[3:6]; R_vec[6:15]; W[15:18]) | upstream_code | gym_rotor/envs/quad.py:146 |
| QuadEnv.step returns (observation, reward, terminated, False, {}) | upstream_code | gym_rotor/envs/quad.py:168 |
| QuadEnv.reset takes env_type, seed and options | upstream_code | gym_rotor/envs/quad.py:171-175 |
| A reset draws position, velocity and angular velocity uniformly within +-init_x, +-init_v and +-init_W and roll and pitch within +-init_R, with the attitude from rotation.from_euler('xyz') | upstream_code | gym_rotor/envs/quad.py:184-204 |
| The initial yaw is sampled uniformly from [-pi, pi] | upstream_code | gym_rotor/envs/quad.py:338-339 |
| For the default train env_type a reset uses init_x 0.6 m, init_v = v_lim*0.5 (2.0 m/s), init_R 50 degrees and init_W = W_lim*0.5 (pi rad/s), except that 20% of resets use zero for all four | upstream_code | gym_rotor/envs/quad.py:340-351 |
| The episode terminates when any position, velocity or angular velocity component reaches its limit, or the absolute roll or pitch reaches 85 degrees | upstream_code | gym_rotor/envs/quad.py:301-318 |
| The equations of motion are x_dot = v, v_dot = g*e3 - f*R@e3/m, R_vec_dot = (R@hat(W)) flattened column-major and W_dot = J^-1 * (-hat(W)@J@W + M) | upstream_code | gym_rotor/envs/quad.py:321-335 |
| The four motor thrusts map to total thrust and body moments through the matrix [1,1,1,1; 0,-d,0,d; d,0,-d,0; -c_tf,c_tf,-c_tf,c_tf] | upstream_code | gym_rotor/envs/quad.py:51-56 |
| The reward is reward_alive minus Cx*||x-xd||^2, Cv*||v-vd||^2, Cb1*|heading error| and CW*||W||^2 | upstream_code | gym_rotor/envs/quad.py:274-298 |
| The reward_alive bonus is 0 and the reward_crash penalty is -1 | upstream_code | gym_rotor/envs/quad.py:73-74 |
| The default reward coefficients are Cx 6.0, Cv 0.4, Cb1 6.0 and Cw12 0.6 | upstream_code | args_parse.py:23-31 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the
environment (`Box(-1.0, 1.0, shape=(4,))`: `action.values` from -1.0 to 1.0 per element, with the source
`upstream_code` and the ref `gym_rotor/envs/quad.py:127-132`), and `ticks` (1 to `max_ticks`, 10000 by default). The
device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:Quad-v0`, level F1 (rigid-body dynamics; no
contact, actuator, sensor or noise model), determinism `seeded` with `seed_control` `parameter`, timestep 5 ms
(`dt = 1/200` s, `quad.py:59-61`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The
gaps say that the fake uses RK4 instead of solve_ivp/DOP853, that upstream's reset seed does not control its initial
state, that domain randomization and the wrapper reward/observation terms are not modelled, that there is no
rendering or gymnasium wrapper, and that the model was never compared with a physical quadrotor.

Safety: simulated R0 device. The e-stop is the runtime's software latch; a simulator has no native stop. After it no
step or reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the
state stays readable.

Tags: quadrotor, uav, reinforcement-learning, simulation, gymnasium, rotor
