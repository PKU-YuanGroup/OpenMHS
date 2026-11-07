# Facts and tags for gh.kousheekc/isaac_drone_racer

Every fact cites its source at commit `d530f67768d53701454f406e4da967e0e9c30842`: `vendor_doc` is documentation text
of the clone, `upstream_code` is its code or a comment. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The drone racing task is registered as a standard Gym environment with the ID Isaac-Drone-Racer-v0 | vendor_doc | README.md:62 |
| Isaac-Drone-Racer-v0 is registered with entry_point isaaclab.envs:ManagerBasedRLEnv, the environment configuration DroneRacerEnvCfg and the env checker disabled | upstream_code | tasks/drone_racer/__init__.py:13-20 |
| Isaac-Drone-Racer-Play-v0 is registered the same way with the configuration DroneRacerEnvCfg_PLAY | upstream_code | tasks/drone_racer/__init__.py:23-30 |
| The project is an open-source simulation framework for autonomous drone racing built on IsaacLab | vendor_doc | README.md:12 |
| The Isaac Sim badge pins version 4.5.0 | vendor_doc | README.md:7 |
| The setup instructions require the IsaacLab v2.1.0 release tag | vendor_doc | README.md:44-48 |
| The default scene spawns 4096 environments with env_spacing 0.0 | upstream_code | tasks/drone_racer/drone_racer_env_cfg.py:197 |
| The policy observation group concatenates the position, attitude, linear velocity, angular velocity, target position in the body frame and last action terms, with corruption disabled | upstream_code | tasks/drone_racer/drone_racer_env_cfg.py:88-97 |
| The default configuration disables the critic observation group (observations.critic = None) | upstream_code | tasks/drone_racer/drone_racer_env_cfg.py:215 |
| The environment uses decimation 4 and a simulation step of 1/400 s, so one environment step advances 0.01 s of simulated time | upstream_code | tasks/drone_racer/drone_racer_env_cfg.py:220-226 |
| The episode length is 20 s (episode_length_s = 20) | upstream_code | tasks/drone_racer/drone_racer_env_cfg.py:221 |
| The episode terminates on a time out, when the drone is more than 20 m from the target gate, and on an illegal contact above threshold 0.01 | upstream_code | tasks/drone_racer/drone_racer_env_cfg.py:187-191 |
| The track configuration places seven gates; gate 1 is at (0.0, 0.0, 1.0) and gate 4 at (-5.0, -5.0, 2.5) | upstream_code | tasks/drone_racer/drone_racer_env_cfg.py:39-49 |
| The reset pose range is x from -3.5 to -1.5, y from -0.5 to 0.5 and z written as (1.5, 0.5), with all linear and angular velocities zero | upstream_code | tasks/drone_racer/drone_racer_env_cfg.py:128-139 |
| The default action configuration disables the motor model (use_motor_model=False) | upstream_code | tasks/drone_racer/drone_racer_env_cfg.py:77 |
| The action term stores four raw actions per environment | upstream_code | tasks/drone_racer/mdp/actions.py:44 |
| The raw action is clamped to [-1, 1] and mapped by (x + 1) / 2 to a motor speed up to omega_max | upstream_code | tasks/drone_racer/mdp/actions.py:97-99 |
| The action configuration declares arm length 0.035 m, thrust coefficient 2.25e-7 and omega_max 5145 rad/s, the last computed from a 1950 KV motor on a 6S battery at 4.2 V per cell | upstream_code | tasks/drone_racer/mdp/actions.py:144-155 |
| The processed action is applied as a body-z thrust and a three-axis body moment | upstream_code | tasks/drone_racer/mdp/actions.py:106-109 |
| The drone is a simulated USD articulation spawned from assets/5_in_drone/5_in_drone.usd, not a hardware connection | upstream_code | assets/five_in_drone.py:28-31 |

Limits: the driver declares none. The only numeric bound is the action space, which the bridge derives from the
environment (`Box` of four values from -1 to 1 per component, no source, ref
`action_space of the fake backend .fake:FakeDroneRacerEnv`); the clamp it mirrors is in
`tasks/drone_racer/mdp/actions.py:97`. `ticks` is bounded by the class schema (1 to 10000).
The device is simulated (R0), so no limit is `operator_required` and there is no site-limits overlay.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `isaaclab:Isaac-Drone-Racer-v0`, level F1 (rigid-body
dynamics with contacts in the upstream Isaac Sim/PhysX scene), determinism `seeded` with `seed_control`
`parameter`, timestep 10 ms (decimation 4 of the 1/400 s simulation step,
`tasks/drone_racer/drone_racer_env_cfg.py:220-226`), `realtime_factor` 0, clock `lockstep`, reset `full`, no
snapshot and restore. The gaps say what the fake does not model and that nothing was run or validated.

Safety: simulated R0 device with no hardware backend. The e-stop is the runtime's software latch; after it no
step, reset or seed is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that),
and the environment state stays readable. The configuration's own terminations (time out, 20 m flyaway, collision
threshold 0.01, `tasks/drone_racer/drone_racer_env_cfg.py:187-191`) are reported through `terminated`/`truncated`.

Tags: drone, racing, quadrotor, reinforcement-learning, simulation, isaaclab, gymnasium
