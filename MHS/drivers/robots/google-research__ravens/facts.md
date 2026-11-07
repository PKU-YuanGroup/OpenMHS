# Facts and tags for gh.google-research/ravens

Every fact cites its source at commit `4752ffab487ebd387781ad7890aa540ae2780970`; the same facts are written into
`driver.py` (`facts = [...]`), and the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Ravens is a collection of simulated tasks in PyBullet for learning vision-based robotic manipulation, with a Gym-like API | vendor_doc | README.md:3-4 |
| Environment subclasses gym.Env and its docstring calls it an OpenAI Gym-style environment class | upstream_code | ravens/environments/environment.py:42-43 |
| The observation space is a Dict of color and depth Tuples, with color boxes 0 to 255 and depth boxes 0.0 to 20.0 for each RealSenseD415 camera | upstream_code | ravens/environments/environment.py:77-88 |
| The default camera configuration has three RealSenseD415 entries with 480 by 640 images | upstream_code | ravens/tasks/cameras.py:27-73 |
| The action space is a Dict with pose0 and pose1, each a Tuple of the position box and a four-value box in -1.0 to 1.0 | upstream_code | ravens/environments/environment.py:94-103 |
| The position box has low [0.25, -0.5, 0.] and high [0.75, 0.5, 0.28] | upstream_code | ravens/environments/environment.py:89-93 |
| Environment.seed(seed) installs a numpy RandomState in _random and returns the seed | upstream_code | ravens/environments/environment.py:175-177 |
| Environment.reset() rebuilds the PyBullet scene, resets the task and returns the observation of a first step | upstream_code | ravens/environments/environment.py:179-222 |
| Environment.step(action) executes a task primitive and returns the (obs, reward, done, info) tuple; a timed-out primitive also returns done True | upstream_code | ravens/environments/environment.py:224-255 |
| Environment.close() unloads the EGL plugin and disconnects the PyBullet client | upstream_code | ravens/environments/environment.py:257-260 |
| The PyBullet physics time step is 1./hz | upstream_code | ravens/environments/environment.py:138 |
| The hz parameter of the Environment constructor defaults to 240 | upstream_code | ravens/environments/environment.py:50 |

Limits: the driver declares none.  The only device bounds are the environment's action space (position and rotation
boxes, `environment.py:89-103`); the gymnasium bridge exports the Tuple structure but no per-element limits inside a
Tuple, which is the SDK's simulation-only residual and is listed in `fidelity.gaps`.  The device is simulated at R0,
so no operator bound is needed, and `site-limits.example.json` is absent.

Fidelity: engine `pybullet`, level F1 (rigid-body dynamics with contacts), determinism `none` because
`Environment.seed()` only seeds the camera-noise generator (`environment.py:175-177`) while task resets use the global
numpy RNG; timestep 4.166666666666667 ms from the constructor default `hz=240` (`environment.py:50`) and `1./hz`
(`environment.py:138`); realtime_factor 0, clock lockstep, reset full, no snapshot/restore.  The gaps disclose that the
fake is not the upstream simulator, returns placeholder RGB-D arrays and a constant reward, and was not compared with
an upstream run.  `hz` is a constructor option, so a deployment can change the timestep; the published value is the
default, not a bound.

Safety: simulated R0 device, no hardware backend and no native stop.  The runtime's software e-stop latch refuses
step, reset and seed until `mhs.safety.reset` clears it; the state stays readable.

Tags: ravens, pybullet, robot-manipulation, reinforcement-learning, simulation
