# Facts and tags for gh.denisgriaznov/custommujocoenviromentforrl

Every fact cites its source at commit `a6d91aeb4e9770feda5210753706e7a431643242`: `vendor_doc` (a text file of the
clone, here README.md) or `upstream_code` (`path/in/clone:LINE`, including the MJCF model text). The same facts are
written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository is an example of creating a custom MuJoCo model and training a reinforcement-learning agent with the Gymnasium shell and StableBaselines | vendor_doc | README.md:3 |
| The README describes a ball-balancing environment with a 10-value observation (position and speed for rotating the platform along two axes and moving the ball along three axes), a reward of 1 per step and episodes of 500 steps by default | vendor_doc | README.md:12 |
| BallBalanceEnv subclasses gymnasium's MujocoEnv and utils.EzPickle | upstream_code | ball_balance_env.py:9 |
| BallBalanceEnv loads the MJCF model at os.path.abspath('assets/ball_balance.xml') and constructs MujocoEnv with frame_skip 5 | upstream_code | ball_balance_env.py:25-28 |
| The observation space is an unbounded 10-value Box of float64 | upstream_code | ball_balance_env.py:23 |
| The default episode length is 500 steps | upstream_code | ball_balance_env.py:20 |
| The environment returns a constant reward of 1.0 and terminates when the observation is not finite or its third value obs[2] is below 0 | upstream_code | ball_balance_env.py:36-44 |
| The environment truncates once step_number exceeds episode_len | upstream_code | ball_balance_env.py:43 |
| The environment's observation concatenates the ball's first three qpos values, its first three qvel values, and the qpos and qvel of rotate_x and rotate_y | upstream_code | ball_balance_env.py:62-68 |
| The model's box body has two hinge joints rotate_x and rotate_y on the x and y axes, each with range -.25 to .25 and damping 20 | upstream_code | assets/ball_balance.xml:13-16 |
| The model's ball body has a freejoint named ball and a sphere geom of radius .05 | upstream_code | assets/ball_balance.xml:18-20 |
| The model has two general actuators, act_x on rotate_x and act_y on rotate_y, each with ctrlrange -1 to 1 and gainprm '1000 0 0' | upstream_code | assets/ball_balance.xml:25-27 |
| model_viewer.py loads the XML with mujoco.MjModel.from_xml_path, creates mujoco.MjData, steps with mujoco.mj_step and reads model.opt.timestep | upstream_code | model_viewer.py:21-33 |

Limits: the driver declares none of its own. The only bounds are derived by the MuJoCo bridge from the model and
the class:

- `action.ctrl` is two numbers, one per actuator, each within the model's `ctrlrange` of -1 to 1
  (`assets/ball_balance.xml:25-27`). The bridge generates the per-element limits from `actuator_ctrlrange`; the
  reference shows them with source `upstream_code` and ref `assets/ball_balance.xml:actuator_ctrlrange`.
- `ticks` is the class bound 1 to `max_ticks` (10000 by default), not a device fact.
- The device is simulated (R0), so no limit is `operator_required` and no `site-limits.example.json` is needed.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `mujoco:ball_balance`, level F1 (MuJoCo rigid-body
dynamics with contacts, no validation), determinism `exact` with `seed_control` `none` (the bridge takes no seed
input; a reset restores the model defaults), timestep 2 ms from the stand-in's placeholder for MuJoCo's library
default because the model sets no `<option timestep>`, `realtime_factor` 0, clock `lockstep`, reset `full`, snapshot
and restore by the bridge's fallback copy. The gaps say what the fake does not model and that the upstream
environment's reward, termination and 10-value observation selection are not applied by this world-level driver.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the world
state stays readable.

Tags: ball-balance, mujoco, reinforcement-learning, simulation, world-model
