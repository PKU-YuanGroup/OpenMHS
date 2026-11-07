OpenMHS is not affiliated with, endorsed by, or a reimplementation of Anthropic's MHS research preview.

# Facts and tags for gh.benelot/pybullet-gym

Every fact cites its source at commit `bc68201c8101c4e30dde95f425647a0709ee2f29`: `vendor_doc` (README.md) or
`upstream_code` (`path/in/clone:LINE`). The same facts are written into `driver.py` (`facts = [...]`); the reference
files are generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| InvertedPendulumPyBulletEnv-v0 is registered with entry point pybulletgym.envs.roboschool.envs.pendulum.inverted_pendulum_env:InvertedPendulumBulletEnv | upstream_code | pybulletgym/envs/__init__.py:5-10 |
| The InvertedPendulumPyBulletEnv-v0 registration sets max_episode_steps to 1000 | upstream_code | pybulletgym/envs/__init__.py:8 |
| The inverted pendulum robot declares action_dim=1 and obs_dim=5 | upstream_code | pybulletgym/envs/roboschool/robots/pendula/interted_pendulum.py:9 |
| The action space is a one-element Box with both bounds from np.ones([action_dim]), that is -1 and 1 | upstream_code | pybulletgym/envs/roboschool/robots/robot_bases.py:24-25 |
| The observation space is a Box of obs_dim elements with bounds from -np.inf to np.inf | upstream_code | pybulletgym/envs/roboschool/robots/robot_bases.py:26-27 |
| The observation vector is [cart position, cart velocity, cos(theta), sin(theta), theta angular velocity] | upstream_code | pybulletgym/envs/roboschool/robots/pendula/interted_pendulum.py:48-51 |
| apply_action sets the slider motor torque to 100 times the action clipped to -1 to 1 | upstream_code | pybulletgym/envs/roboschool/robots/pendula/interted_pendulum.py:25 |
| The reset draws the pole angle uniformly from -0.1 to 0.1 (the swing-up reset adds 3.1415) and sets the motor torque to 0 | upstream_code | pybulletgym/envs/roboschool/robots/pendula/interted_pendulum.py:16-18 |
| The non-swing-up episode terminates when abs(theta) is greater than 0.2 and each step pays reward 1.0 | upstream_code | pybulletgym/envs/roboschool/envs/pendulum/inverted_pendulum_env.py:34-39 |
| The environment creates a scene with gravity 9.8, timestep 0.0165 s and frame_skip 1 | upstream_code | pybulletgym/envs/roboschool/envs/pendulum/inverted_pendulum_env.py:13-14 |
| The scene stores timestep and frame_skip and computes dt as timestep times frame_skip | upstream_code | pybulletgym/envs/roboschool/scenes/scene_bases.py:14-17 |
| The MJCF model gives the cart a slide joint named slider on the x axis with range -1 to 1 and the pole an unlimited hinge | upstream_code | pybulletgym/envs/assets/mjcf/inverted_pendulum.xml:15-18 |
| The documented gym environment methods are reset(self), which returns the observation, and step(self, action), which returns observation, reward, done and info | vendor_doc | README.md:67-68 |
| The environments are reimplemented with the pybullet wrapper of Bullet Physics | vendor_doc | README.md:6 |

Limits: The checked fake keeps one action value in -1..1. The Gymnasium bridge derives these unchanged action bounds with source `upstream_code` and ref `pybulletgym/envs/roboschool/robots/robot_bases.py:24-25`, where the same-span ones assignment and Box construction state the bounds. The selected environment and width were source-reviewed separately; symbolic shapes alone do not prove a width. `ticks` remains the SDK bridge budget (1 to max_ticks, 10000 by default), not a device limit. This simulated R0 package declares no operator-required hardware limit.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `pybullet-gym:InvertedPendulumPyBulletEnv-v0`, level F1,
determinism `seeded` with `seed_control` `parameter`, timestep 16.5 ms (scene timestep 0.0165 s times frame_skip 1,
`inverted_pendulum_env.py:14`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps
state what the fake does not model: Bullet joints, solver and integrator (the fake uses placeholder masses and Euler
integration), numpy's random stream, the four-tuple step result and the `TimeLimit` wrapper of `gym.make`, rendering,
and wall-clock pacing.

Safety: simulated R0 device with no hardware backend. An e-stop is the runtime's software latch: it refuses further
step and reset calls and keeps the last observation readable until the runtime's safety reset clears the latch. No
physical stop exists to cite and none is claimed.

Tags: inverted-pendulum, roboschool, reinforcement-learning, simulation, pybullet
