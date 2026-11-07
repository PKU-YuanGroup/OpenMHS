# Facts and tags for gh.leesweqq/drl_peg-in-hole_ur5

Every fact cites its source at commit `36f75b016315375918336db141ccd983a95acdef`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The environment is PegInHoleGymEnv(gym.Env) and its constructor connects a PyBullet GUI client | upstream_code | rlenv.py:13-16 |
| The observation space is a Dict with one Box field cam_image of shape (100, 100, 1), values 0 to 255, dtype uint8 | upstream_code | rlenv.py:32-40 |
| The camera image is 100 by 100 pixels | upstream_code | rlenv.py:22-23 |
| The action space is a Box of three elements, each from -0.005 to 0.005 | upstream_code | rlenv.py:42-43 |
| reset has the signature reset(self, seed=None, options=None) and draws the hole position with random.uniform from the module-level random generator | upstream_code | rlenv.py:97-113 |
| reset draws the hole position x from uniform(0.5, 0.6), y from uniform(0, 0.1) at z = 0.65 | upstream_code | rlenv.py:110-114 |
| The rest poses are [0, -1.57, 1.57, -1.5, -1.57, 0.0] and reset applies them, then steps the simulation 100 times | upstream_code | rlenv.py:90-104 |
| step increments the step counter, clips the action to the action-space bounds and moves the end effector by the action offset | upstream_code | rlenv.py:142-153 |
| step advances the PyBullet simulation 10 times after the motion command | upstream_code | rlenv.py:154 |
| The maximum episode length is max_steps = 500 | upstream_code | rlenv.py:25 |
| An episode is truncated when the step counter reaches max_steps | upstream_code | rlenv.py:175 |
| The reward is 10 * (-dist_xy - 0.5 * dist_z) plus 100 on insertion | upstream_code | rlenv.py:240-249 |
| Insertion succeeds when the end effector is within 0.01 of the hole in the XY plane and within 0.1 in Z | upstream_code | rlenv.py:257-262 |
| Collision is suppressed when the end effector is within 0.02 in XY and 0.15 in Z of the hole; otherwise contact with the table or the hole ends the episode | upstream_code | rlenv.py:179-191 |
| step returns the five-tuple (observation, reward, done, truncated, info) and info reports insertion_success | upstream_code | rlenv.py:142-177 |
| The camera projection uses a 60 degree field of view, near 0.01 and far 3.0 | upstream_code | rlenv.py:222-227 |
| close disconnects the PyBullet client | upstream_code | rlenv.py:267-268 |
| The project is a DRL environment built with PyBullet and Gymnasium that simulates a UR5 peg-in-hole insertion task | vendor_doc | README.md:5 |
| The camera captures 100x100 grayscale images as the visual observation | vendor_doc | README.md:7 |
| The README's main installation line installs pybullet, gymnasium, stable-baselines3, matplotlib and pandas | vendor_doc | README.md:81 |

Limits: the driver declares no `Limit` of its own. The only bound is the action space, which the Gymnasium bridge
derives from the environment: `action.values` has three elements with `-0.005 <= value <= 0.005` (rlenv.py:43), with
the source `upstream_code` and the environment's own space as ref. `ticks` is bounded by the bridge to 1..10000
(`GymnasiumDriver.max_ticks`). The device is simulated (R0), so no bound is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `analytic:rlenv.PegInHoleGymEnv (package fake backend)`,
level F0 because the only declared backend is a kinematic stand-in with no forces or contacts; determinism `seeded`
with `seed_control` `parameter` (a property of the fake; upstream ignores the reset seed, rlenv.py:97-113); timestep
0 ms because the fake models no simulated time (upstream calls `p.stepSimulation()` ten times per step and the clone
does not state PyBullet's timestep); `realtime_factor` 0; clock `lockstep`; reset `full`; no snapshot and restore.
The gaps state what is not modelled: rigid-body dynamics, inverse kinematics, contacts, the real OpenGL camera,
upstream determinism, wall-clock time, actuator/sensor/noise models, snapshots, and that the fake was never compared
with a real upstream run.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: peg-in-hole, ur5, pybullet, reinforcement-learning, simulation, gymnasium
