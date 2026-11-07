# Facts and tags for gh.robotcasters/b1env

Every fact cites its source at commit `cdf57676193c1bbe15960157aac059a291c0e89c`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The project titles itself the Unitree B1 Simulation Environment, a simulation environment for the Unitree B1 robot | vendor_doc | README.md:1-2 |
| B1Sim subclasses gymnasium.Env and imports Env and spaces from gymnasium | upstream_code | B1Env/b1_env.py:6-19 |
| The constructor opens an in-process PyBullet client: GUI when render_mode is 'human' and DIRECT otherwise | upstream_code | B1Env/b1_env.py:31-36 |
| PyBullet gravity is (0, 0, -9.81) and the PyBullet time step is 1/240 s | upstream_code | B1Env/b1_env.py:38-39 |
| The bundled b1_raw.urdf is loaded at base position [0.0, 0.0, 1.0], with useFixedBase passed through | upstream_code | B1Env/b1_env.py:46-52 |
| A pinocchio RobotWrapper is built from the same URDF | upstream_code | B1Env/b1_env.py:54-55 |
| The spaces are built from every non-fixed joint: observation q bounds from jointLowerLimit and jointUpperLimit, the velocity bound from jointMaxVelocity, and the action bounds from +-jointMaxForce | upstream_code | B1Env/b1_env.py:69-79 |
| The observation Box is the joint positions followed by the joint velocities and the action Box is the joint torques, all as float32 arrays | upstream_code | B1Env/b1_env.py:89-95 |
| reset sets 12 target joint angles to 0.0 and resets each active joint to angle 0.0 with velocity 0.0 | upstream_code | B1Env/b1_env.py:113-116 |
| reset returns only the q/dq info dict, not a gymnasium (observation, info) pair | upstream_code | B1Env/b1_env.py:118-121 |
| step applies the torque command, advances PyBullet by one step and returns only the q/dq info dict, not a gymnasium five-tuple | upstream_code | B1Env/b1_env.py:132-138 |
| get_info returns {'q': q, 'dq': dq} | upstream_code | B1Env/b1_env.py:150-156 |
| get_state reads 12 joint positions and velocities with p.getJointState over the active joint ids | upstream_code | B1Env/b1_env.py:162-176 |
| send_joint_command applies the commanded torques with p.TORQUE_CONTROL and zero position and velocity gains | upstream_code | B1Env/b1_env.py:203-219 |
| The hip joint limit is effort 91.0035, lower -0.75, upper 0.75 and velocity 19.69; the same limit is declared for the other three hips | upstream_code | B1Env/robots/b1_raw.urdf:62 |
| The thigh joint limit is effort 93.33, lower -1.0, upper 3.5 and velocity 23.32; the same limit is declared for the other three thighs | upstream_code | B1Env/robots/b1_raw.urdf:119 |
| The knee joint limit is effort 140, lower -2.6, upper -0.6 and velocity 15.55; the same limit is declared for the other three knees | upstream_code | B1Env/robots/b1_raw.urdf:176 |
| setup.cfg declares numpy>=1.22.3, scipy==1.8.0, pybullet==3.2.5 and gymnasium==0.26.3 as install_requires; pinocchio and bullet_utils are installed separately per the README | upstream_code | setup.cfg:18-22 |
| The README requires pinocchio and bullet_utils to be installed before the package itself | vendor_doc | README.md:12-24 |

Limits: the driver declares none. The only bounds are the action space and the observation space the fake builds from
the URDF, which the bridge derives from the environment (`Box`: `action.values` with the 12 effort bounds, no source,
ref `action_space of the fake backend .fake:FakeB1Sim`) and `ticks` (1 to `max_ticks`, 10000 by default). The device
is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `analytic:B1Sim-fake`, level F0 (the tested fake has no
dynamics beyond a per-joint kinematic update), determinism `none` with `seed_control` `none` (the upstream reset draws
no random values and does not restore the floating base), timestep 1000/240 ms (the PyBullet 1/240 s step,
`B1Env/b1_env.py:39`), `realtime_factor` 0, clock `lockstep`, reset `partial`, no snapshot and restore. The gaps say
what is not modelled, that the upstream reset/step return only the q/dq info dict, that the reset state is above the
knee upper limit and outside the observation Box for those four joints, and that the fake was not compared with the
upstream PyBullet environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: unitree, b1, quadruped, pybullet, reinforcement-learning, simulation, gymnasium
