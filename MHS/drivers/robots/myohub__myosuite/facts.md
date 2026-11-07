# Facts and tags for gh.myohub/myosuite

Every fact cites its source at commit `2d08f42dfec85278566c95b1d09f5bd67662b3d6`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| myoChallengeBaodingP1-v1 is registered with entry point BaodingEnv, model hand/myohand_baoding.xml and max_episode_steps=200 | upstream_code | myosuite/envs/myo/tasks/challenge/__init__.py:501-505 |
| The normalized action space is a symmetric Box from -ones to +ones with one value per actuator | upstream_code | myosuite/envs/myo/tasks/challenge/baoding.py:202-209 |
| The default observation keys are hand_pos, object1_pos, object1_velp, object2_pos, object2_velp, target1_pos, target2_pos, target1_err and target2_err | upstream_code | myosuite/envs/myo/tasks/challenge/baoding.py:66-75 |
| act (the muscle activations) is appended to the observation when the model has muscle actuators | upstream_code | myosuite/envs/myo/tasks/challenge/baoding.py:197-200 |
| hand_pos is qpos[:-14], the hand coordinates before the two balls' free joints; the ball velocities are qvel[-12:-9] and qvel[-6:-3] times the control timestep | upstream_code | myosuite/envs/myo/tasks/challenge/baoding.py:279-283 |
| target1_err and target2_err are the target position minus the ball position | upstream_code | myosuite/envs/myo/tasks/challenge/baoding.py:288-289 |
| The observation space is an unbounded Box: the observations are physical quantities with no common bound and are not clipped | upstream_code | myosuite/envs/gymnasium_env.py:466-479 |
| step returns the Gymnasium five-tuple and always passes False for truncated; the TimeLimit wrapper owns the step limit | upstream_code | myosuite/envs/gymnasium_env.py:535-542 |
| reset restores qpos and qvel from the initial state and returns the observation | upstream_code | myosuite/envs/myo/tasks/challenge/baoding.py:505-515 |
| The episode is done when a ball's height is below the constructor option drop_th | upstream_code | myosuite/envs/myo/tasks/challenge/baoding.py:313-327 |
| The MuJoCo model timestep is 0.0025 s | upstream_code | myosuite/envs/myo/assets/hand/myohand_baoding.xml:14 |
| The control timestep is the model timestep times frame_skip | upstream_code | myosuite/envs/myo/tasks/challenge/baoding.py:141 |
| The baoding scene adds one free joint for each of the two balls, after the hand body | upstream_code | myosuite/envs/myo/assets/hand/myohand_baoding.xml:22-31 |

## Limits

The driver declares no Limit of its own. The action bound is derived from the environment's action space by the
Gymnasium bridge: with `normalize_act` each actuator's action lies in the symmetric interval from -1 to +1, and the bridge publishes
that Box as the per-element limits of `cap.world.step.v1` (`action.values`). The `ticks` bound (at least 1, at most
`max_ticks`) is the bridge's own. The device is simulated R0, so no bound is `operator_required` and there is nothing
for an operator overlay to narrow. The fake's `action_space` and `observation_space` sizes are test data marked
`# placeholder`; the real sizes come from the model's actuator block and the hand body's hinge joints plus the two balls'
free joints.

## Fidelity contract

`driver.py` declares the model as deployed on the fake backend (spec 05-fidelity FID-002): engine
`analytic:myosuite-baoding-stand-in`, level F0 (kinematic stand-in, no dynamics), determinism `seeded` with
`seed_control` `parameter`, timestep 25 ms (the model timestep 0.0025 s times the `frame_skip` default 10), lockstep
clock, full reset, no snapshot or restore. The gaps state that no MuJoCo integration, contacts, tendons, muscles or
actuator forces are modelled, that the observation values are placeholders with the real shape, that the fake was
never compared with upstream, and that the `sim` backend was not run.

## Safety

A simulated R0 device. The e-stop is the runtime's software latch: after it no step or reset is accepted until
`mhs.safety.reset` clears the latch, and the last observation stays readable. There is no hardware stop path because
there is no hardware backend.

Tags: baoding, musculoskeletal, reinforcement-learning, simulation, gymnasium, myosuite
