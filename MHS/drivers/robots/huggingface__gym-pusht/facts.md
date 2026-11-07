# Facts and tags for gh.huggingface/gym-pusht

Every fact cites its source at commit `1dce32970bc3d25e7fad5872c3020159bc5eb31f`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md, or a PDF page as `docs/manual.pdf:PAGE`) or `upstream_code`
(`path/in/clone.py:LINE`). The same facts are written into `driver.py` (`facts = [...]`); the reference file is
generated from the driver, not from this page. This package is model-authored: it writes `upstream_code` facts only,
because the clone has no separate vendor documentation of the bounds.

| fact | source | ref |
|---|---|---|
| PushT-v0 is registered with entry point gym_pusht.envs:PushTEnv, max_episode_steps 300 and kwargs obs_type state | upstream_code | gym_pusht/__init__.py:3-8 |
| The action space is a Box of two values in the range 0 to 512 | upstream_code | gym_pusht/envs/pusht.py:161 |
| The action [x, y] is the target position of the agent | upstream_code | gym_pusht/envs/pusht.py:50-51 |
| With obs_type state the observation space is a Box of five values: the agent x and y and the block x and y bounded by 0 and 512 and the block angle bounded by 0 and 2*pi | upstream_code | gym_pusht/envs/pusht.py:184-190 |
| The state observation is [agent_x, agent_y, block_x, block_y, block_angle] and the block angle is taken modulo 2*pi | upstream_code | gym_pusht/envs/pusht.py:382-386 |
| The PD control gains are k_p 100 and k_v 20 | upstream_code | gym_pusht/envs/pusht.py:164 |
| Each physics substep adds acceleration = k_p * (action - agent position) + k_v * (0 - agent velocity) times dt to the agent velocity | upstream_code | gym_pusht/envs/pusht.py:247-250 |
| The physics timestep is dt 0.01 s and control_hz is the metadata render_fps | upstream_code | gym_pusht/envs/pusht.py:165-166 |
| metadata render_fps is 10, which control_hz takes as the control rate | upstream_code | gym_pusht/envs/pusht.py:135 |
| One step runs int(1 / (dt * control_hz)) = 10 physics substeps of dt, so it advances 0.1 s of simulated time | upstream_code | gym_pusht/envs/pusht.py:242 |
| self.success_threshold is 0.95, so a success needs the block at least 95% in the goal zone | upstream_code | gym_pusht/envs/pusht.py:181 |
| The reward is coverage / success_threshold clipped to 0 and 1, and the episode terminates when the coverage is above the success threshold | upstream_code | gym_pusht/envs/pusht.py:256-258 |
| step always returns truncated False: the 300-step limit is the TimeLimit wrapper that gymnasium.make adds | upstream_code | gym_pusht/envs/pusht.py:265 |
| The coverage is the area of the intersection of the goal tee and the block tee over the area of the goal tee | upstream_code | gym_pusht/envs/pusht.py:232-238 |
| The goal pose is x 256, y 256 and angle pi/4 radians | upstream_code | gym_pusht/envs/pusht.py:447 |
| The agent is a kinematic circle of radius 15 that starts at (256, 400) | upstream_code | gym_pusht/envs/pusht.py:445 |
| The block starts at (256, 300) with angle 0, and add_tee builds the tee from two rectangles with scale 30, length 4 and mass 1 | upstream_code | gym_pusht/envs/pusht.py:446 |
| add_tee sets the body centre of gravity to the mean of the two rectangle centres of gravity | upstream_code | gym_pusht/envs/pusht.py:511 |
| The goal body of get_goal_pose_body never sets a centre of gravity | upstream_code | gym_pusht/envs/pusht.py:403-412 |
| The walls are four segments at x 5, x 506, y 5 and y 506 with radius 2 | upstream_code | gym_pusht/envs/pusht.py:436-441 |
| The physics space has gravity 0 and damping 0.0 when no damping argument is given | upstream_code | gym_pusht/envs/pusht.py:430-432 |
| A reset draws the agent x and y from the integers 50 to 449, the block x and y from 100 to 399 and the block angle uniformly from -pi to pi | upstream_code | gym_pusht/envs/pusht.py:276-284 |
| Passing the reset option reset_to_state sets the state from the option | upstream_code | gym_pusht/envs/pusht.py:272-273 |
| _set_state puts the first two state values on the agent, the next two on the block position and the last on the block angle | upstream_code | gym_pusht/envs/pusht.py:456-462 |
| info carries pos_agent, vel_agent, block_pose, goal_pose and n_contacts | upstream_code | gym_pusht/envs/pusht.py:414-424 |
| step adds coverage and is_success to info | upstream_code | gym_pusht/envs/pusht.py:261-263 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the environment
(`Box(0, 512)` of shape (2,), so `action.values[*]` is bounded element by element with the source `upstream_code` and
the ref `gym_pusht/envs/pusht.py:161`), and `ticks` (1 to `max_ticks`, 10000 by default). The device is simulated
(R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:gym_pusht/PushT-v0`, level F1 (pymunk
rigid-body dynamics with contacts; the collision solver, the friction and the tee inertia of the fake backend are
approximations), determinism `seeded` with `seed_control` `parameter` (the reset seed drives the environment's random
generator, `pusht.py:276-284`), timestep 100 ms (one tick = 10 substeps of dt 0.01 s, `pusht.py:242`),
`realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps say what is not modelled and
that this package's fake was never compared with the upstream environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no hardware stop and no native stop method
exist); after it no step, reset or seed is accepted until `mhs.safety.reset` clears the latch (a simulator needs no
operator for that), and the environment state stays readable.

Tags: pusht, 2d-manipulation, reinforcement-learning, simulation, pymunk, gymnasium
