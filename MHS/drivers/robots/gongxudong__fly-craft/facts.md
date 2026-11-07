# Facts and tags for gh.gongxudong/fly-craft

Every fact cites its source at commit `a54a1c2a1005b6d6ba67d8cea9fbc78c8769f449`: `vendor_doc` (a text file of the
clone, here README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| FlyCraft is a goal-conditioned reinforcement learning environment for fixed-wing UAV velocity vector control based on Gymnasium | vendor_doc | README.md:3 |
| FlyCraft-v0 is registered with entry point flycraft.env:FlyCraftEnv | upstream_code | flycraft/__init__.py:8-10 |
| FlyCraft-Level-Turn-v0 is registered with entry point flycraft.env_level_turn:FlyCraftLevelTurnEnv | upstream_code | flycraft/__init__.py:13-15 |
| FlyCraftEnv is a gymnasium.Env subclass | upstream_code | flycraft/env.py:20 |
| The observation space is a Dict of three Boxes named observation, desired_goal and achieved_goal | upstream_code | flycraft/env.py:34-40 |
| The observation vector is ordered phi, theta, psi, v, mu, chi, p, h | upstream_code | flycraft/env.py:36 |
| The observation lower bounds are phi -180, theta -90, psi -180, v 0, mu -90, chi -180, p -300 and h 0 | upstream_code | flycraft/tasks/velocity_vector_control_task.py:454 |
| The observation upper bounds are phi 180, theta 90, psi 180, v 1000, mu 90, chi 180, p 300 and h 20000 | upstream_code | flycraft/tasks/velocity_vector_control_task.py:464 |
| The desired and achieved goal vector is [v, mu, chi] with bounds v 0 to 1000, mu -90 to 90 and chi -180 to 180 | upstream_code | flycraft/tasks/velocity_vector_control_task.py:467-474 |
| The action space is a Box built from F16Plane.get_action_lower_bounds and get_action_higher_bounds for the configured control mode | upstream_code | flycraft/env.py:54-59 |
| In guidance_law_mode the action is [p, nz, pla] with bounds p -180 to 180, nz -4 to 9 and pla 0 to 1 | upstream_code | flycraft/planes/f16_plane.py:161-172 |
| In end_to_end_mode the action is [ail, ele, rud, pla] with bounds ail -21.5 to 21.5, ele -25 to 25, rud -30 to 30 and pla 0 to 1 | upstream_code | flycraft/planes/f16_plane.py:163-174 |
| The plane's step time is 1/step_frequence seconds | upstream_code | flycraft/planes/f16_plane.py:144-145 |
| The default NMR configuration sets step_frequence to 10 | upstream_code | flycraft/configs/NMR.json:8 |
| reset(seed, options) reseeds the task and goal sampler when a seed is given, resets the plane and the task, and returns (observation, info) | upstream_code | flycraft/env.py:91-107 |
| step(action) returns (observation, reward, terminated, truncated, info) | upstream_code | flycraft/env.py:234 |
| The timeout termination reports terminated and truncated when step_cnt >= max_episode_steps - 1 | upstream_code | flycraft/terminations/timeout_termination.py:22-26 |
| max_episode_steps is max_simulate_time times step_frequence | upstream_code | flycraft/terminations/termination_base.py:106-107 |
| Upstream needs dynamic *.so/*.dll libraries and documents Linux or Windows only | vendor_doc | README.md:74 |

Limits: the driver declares none. The only bounds are the action space, which the bridge derives from the
environment (`action.values` per element: p -180 to 180, nz -4 to 9, pla 0 to 1, with the source `upstream_code`
and the ref `flycraft/planes/f16_plane.py:161-172`), the `ticks` input (1 to `max_ticks`, 10000 by default) and the
reset `seed` minimum 0. The device is simulated (R0), so no limit is `operator_required` and there is no
`site-limits.example.json`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `flycraft:analytic-stand-in (F16 flight model absent)`,
level F0 (the fake models the spaces and the reset/step protocol, not the flight dynamics), determinism `seeded`
with `seed_control` `parameter`, timestep 100 ms (the default NMR.json `step_frequence` of 10, with
`step_time = 1/step_frequence` at `flycraft/planes/f16_plane.py:144-145`; a custom config can change it),
`realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps say what is not modelled:
the F16 flight model and control law, the upstream reward and termination rules, the numpy-based goal sampler,
`end_to_end_mode`, the platform-specific compiled libraries, and the fact that the fake was never compared with
upstream.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step,
reset or seed is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and
the world state stays readable.

Tags: fixed-wing, uav, velocity-vector-control, reinforcement-learning, simulation, gymnasium
