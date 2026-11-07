# Facts and tags for gh.fdcl-gwu/gym-rotor-modularrl

Every fact cites its source at commit `3d70dfbe4ccee71bf30953cba3a1a810f2084494`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md, or a PDF page as `docs/manual.pdf:PAGE`) or
`upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [Fact(text, source=..., ref=...)]`); `reference.json` and `REFERENCE.md` are generated from the driver, not
from this page.

| fact | source | ref |
|---|---|---|
| Quad-v0 is registered with entry point gym_rotor.envs:QuadEnv and max_episode_steps 10000 | upstream_code | gym_rotor/__init__.py:3-6 |
| The state vector is 18 numbers: position (3), velocity (3), the rotation matrix in column-major order (9) and body angular velocity (3) | upstream_code | gym_rotor/envs/quad.py:146 |
| The action space is Box(-1.0, 1.0, shape=(4,)): four normalized motor commands | upstream_code | gym_rotor/envs/quad.py:126-132 |
| The observation space bounds position at +-1 m, velocity at +-4 m/s, the nine rotation-matrix elements at +-1 and angular velocity at +-2*pi rad/s | upstream_code | gym_rotor/envs/quad.py:103-117 |
| The nominal quadrotor parameters are mass 2.15 kg, arm length 0.23 m, inertia diag(0.022, 0.022, 0.035) kg m2, torque-to-thrust coefficient 0.0135, thrust-to-weight coefficient 2.2 and gravity 9.81 | upstream_code | gym_rotor/envs/quad.py:27-33 |
| The hover thrust of each motor is m*g/4, the minimum thrust is 0.5 N and the maximum is c_tw times the hover thrust | upstream_code | gym_rotor/envs/quad.py:36-42 |
| A normalized action is scaled linearly from [-1, 1] to [min_force, max_force] and clipped to that range | upstream_code | gym_rotor/envs/quad.py:225-229 |
| The simulation advances at 200 Hz, so one step is 0.005 s | upstream_code | gym_rotor/envs/quad.py:59-61 |
| The equations of motion are x_dot = v, v_dot = g*e3 - f*R*e3/m, R_vec_dot = (R*hat(W)) in column-major order and W_dot = J^-1(-hat(W)*J*W + M) | upstream_code | gym_rotor/envs/quad.py:323-337 |
| The default ODE integrator is solve_ivp with the DOP853 method | upstream_code | gym_rotor/envs/quad.py:262-266 |
| A reset draws yaw uniformly in [-pi, pi]; in 80 percent of training resets the initial position, velocity, attitude and angular-velocity bounds are 0.6 m, 2.0 m/s, 50 degrees and pi rad/s, and in the other 20 percent they are zero | upstream_code | gym_rotor/envs/quad.py:340-353 |
| The state limits are position 1.0 m, velocity 4.0 m/s, angular velocity 2*pi rad/s and Euler angle 85 degrees | upstream_code | gym_rotor/envs/quad.py:103-107 |
| The episode terminates when any position, velocity or angular-velocity component reaches its limit, or when abs(roll) or abs(pitch) reaches 85 degrees | upstream_code | gym_rotor/envs/quad.py:311-318 |
| The scalar reward is -Cx*norm(x-xd)^2 - Cv*norm(v-vd)^2 - Cb1*abs(e_b1) - CW*norm(W)^2 plus reward_alive | upstream_code | gym_rotor/envs/quad.py:291-300 |
| The default reward coefficients are Cx 6.0, CIx 0.1, Cv 0.4, Cb1 6.0, CIb1 0.1 and Cw12 (used as CW) 0.6 | upstream_code | args_parse.py:21-29 |
| QuadEnv.step indexes the scalar returned by reward_wrapper and the boolean returned by done_wrapper, so it raises TypeError before returning under any framework value | upstream_code | gym_rotor/envs/quad.py:153-168 |
| QuadEnv.reset returns the observation array alone, not an (observation, info) tuple | upstream_code | gym_rotor/envs/quad.py:222 |
| The rotation matrix is stored in column-major order and state_decomposition reshapes it with order='F', re-orthonormalizing it when it is not in SO(3) | upstream_code | gym_rotor/envs/quad_utils.py:12-16 |

Limits: the driver declares none. The only bounds are the action space, which the bridge derives from the
environment (`Box(-1, 1, (4,))`: `action.values` from -1 to 1 per element, with the source `upstream_code` and the
ref `gym_rotor/envs/quad.py:127-132`), and `ticks` (1 to `max_ticks`, 10000). The device is simulated (R0), so no
limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gym_rotor:Quad-v0`, level F1 (rigid-body equations of
motion, no contacts, aerodynamics, actuator lag, sensor or noise model), determinism `seeded` with `seed_control`
`parameter`, timestep 5 ms (200 Hz, `quad.py:60-61`), `realtime_factor` 0, clock `lockstep`, reset `full`, no
snapshot and restore. The gaps say what is not modelled, that the fake uses explicit Euler instead of the upstream's
solve_ivp DOP853, and that it was not compared with the upstream environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable.

Tags: quadrotor, uav, flight-dynamics, reinforcement-learning, simulation, gymnasium
