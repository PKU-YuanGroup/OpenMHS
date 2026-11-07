# Facts and tags for gh.carolzyy/modesuite

Every fact cites its source at commit `470681a7ff117e487060ad52bc4f199e3fa34474`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| MoDeSuite is built on NVIDIA Isaac Sim and the Isaac Lab framework | vendor_doc | README.md:19 |
| The prerequisites are Ubuntu 22.04, Python 3.10, NVIDIA Isaac Sim 4.2.0 and Isaac Lab | vendor_doc | README.md:50-53 |
| MoDe-Spot-Bend-v0 is registered with entry point task.Bend.spot_bend_env:SpotBendRodEnv | upstream_code | task/Bend/__init__.py:11-13 |
| The action space has 9 components: 3 for the base and 6 for the arm | upstream_code | task/Bend/spot_bend_env.py:21 |
| The observation space has 58 components and the rod is sampled at node_num=4 points | upstream_code | task/Bend/spot_bend_env.py:25-26 |
| The simulation dt is 1/200 s and the decimation is 2 | upstream_code | task/Bend/spot_bend_env.py:19-33 |
| SpotBendRodEnv sets self.dt = cfg.sim.dt * cfg.decimation | upstream_code | task/Bend/spot_bend_env.py:128 |
| The episode length is episode_length_s = 1000.0/40.0, i.e. 25 s | upstream_code | task/Bend/spot_bend_env.py:20 |
| The target position is [3, 3, 1] | upstream_code | task/Bend/spot_bend_env.py:47 |
| The first three action components drive the base and the last six the arm; the arm target is command + dt * command * action_scale | upstream_code | task/Bend/spot_bend_env.py:205-214 |
| The observation concatenates sampled rod nodal positions, root position, root quaternion, target, joint positions and joint velocities | upstream_code | task/Bend/spot_bend_env.py:284-293 |
| The reward is the negative sum of four target distances, +1 when the arm end or the rod end beats its reference, +10 when the flag is set and -500 when the base is unbalanced | upstream_code | task/Bend/spot_bend_env.py:317-325 |
| reach_flag is true when the rod end is closer than 0.3 to the target | upstream_code | task/Bend/spot_bend_env.py:330-335 |
| The base is unbalanced when the gravity direction deviates by more than 45 degrees | upstream_code | task/Bend/spot_bend_env.py:249-253 |
| An episode ends on timeout or when reach_flag or the balance check fires | upstream_code | task/Bend/spot_bend_env.py:342-345 |

Limits: the driver declares none. The action bounds are the environment's action space; the clone does not write
the Box bounds because Isaac Lab's `DirectRLEnv` is outside the clone, so the fake uses marked placeholder bounds
(see `fake.py`) and no `Limit` or `Fact` claims a bound the clone does not state. The device is simulated (R0), so
no bound is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `isaac-lab:MoDe-Spot-Bend-v0`, level F0 (the fake is
kinematic: no forces, contacts, soft bodies or actuator/sensor/noise model), determinism `seeded` with `seed_control`
`parameter`, timestep 10 ms (`1/200` s times decimation 2, `spot_bend_env.py:19`, `:33`, `:128`),
`realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps say what is not modelled and
that the fake was never compared with the upstream environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (there is no native stop to call); after it
no step, reset or seed is accepted until `mhs.safety.reset` clears the latch, and the world state stays readable.
There is no hardware backend and no operator-required limit.

Tags: modesuite, mobile-manipulation, deformable-objects, isaac-lab, simulation, gymnasium
