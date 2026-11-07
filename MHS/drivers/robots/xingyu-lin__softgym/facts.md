# Facts and tags for gh.xingyu-lin/softgym

Every fact cites its source at commit `bb383f64cd488062587714abbae38f27ed9f2457`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md) or `upstream_code` (`path/in/clone.py:LINE`).  The `facts` list in `driver.py`
is the authoritative copy; `reference.json` and `REFERENCE.md` are generated from it.

| fact | source | ref |
|---|---|---|
| SoftGym is a set of benchmark environments for deformable object manipulation built on the Nvidia FleX simulator with a standard Gym API | vendor_doc | README.md:2 |
| The README documents compiling PyFleX with CMake and Pybind11 | vendor_doc | README.md:22 |
| FlexEnv is a gym.Env, the legacy Gym API | upstream_code | softgym/envs/flex_env.py:17 |
| FlexEnv imports pyflex and raises gym.error.DependencyNotInstalled when the compiled binding is missing | upstream_code | softgym/envs/flex_env.py:12-15 |
| PourWaterPosControlEnv extends FluidEnv | upstream_code | softgym/envs/pour_water.py:12 |
| FluidEnv extends FlexEnv | upstream_code | softgym/envs/fluid_env.py:7 |
| PourWaterPosControlEnv accepts the observation modes cam_rgb, point_cloud and key_point and the action modes rotation_bottom and rotation_top | upstream_code | softgym/envs/pour_water.py:22-23 |
| The key_point observation has 13 elements: the two cups' positions and shapes, the water height and the water fractions of the two cups | upstream_code | softgym/envs/pour_water.py:32-41 |
| The key_point observation space is a Box of 13 values bounded by -inf and +inf | upstream_code | softgym/envs/pour_water.py:42 |
| In the rotation_bottom and rotation_top action modes the action space is a 3-element Box: (dx, dy) for the floor centre and dtheta for its rotation | upstream_code | softgym/envs/pour_water.py:49-54 |
| The key_point observation is built from the glass pose and shape, the poured glass pose and shape, the water height and the two water fractions | upstream_code | softgym/envs/pour_water.py:368-370 |
| The reward is the fraction of water particles inside the poured glass and outside the control glass | upstream_code | softgym/envs/pour_water.py:377-392 |
| The reward range is 0 to 1 | upstream_code | softgym/envs/pour_water.py:59-60 |
| FlexEnv's default action_repeat is 8 | upstream_code | softgym/envs/flex_env.py:26 |
| FlexEnv.step calls _step once per action_repeat before it computes the observation and reward | upstream_code | softgym/envs/flex_env.py:180-185 |
| FlexEnv.step increments time_step and marks the episode done when time_step reaches the horizon | upstream_code | softgym/envs/flex_env.py:190-194 |
| FlexEnv.step returns the legacy four-value (observation, reward, done, info) tuple | upstream_code | softgym/envs/flex_env.py:197 |
| FlexEnv's default horizon is 100 | upstream_code | softgym/envs/flex_env.py:22 |
| The PourWaterPosControl-v0 registration sets the horizon to 75 | upstream_code | softgym/__init__.py:26 |
| The PourWaterPosControl-v0 registration passes action_mode='direct' | upstream_code | softgym/__init__.py:21 |
| The class itself only accepts action_mode rotation_bottom or rotation_top, so the registered value 'direct' fails its assertion | upstream_code | softgym/envs/pour_water.py:23 |
| PourWaterPosControl-v0 is registered with entry point softgym.envs.pour_water:PourWaterPosControlEnv | upstream_code | softgym/__init__.py:16-18 |
| FluidEnv.set_scene creates the fluid scene with pyflex.set_scene | upstream_code | softgym/envs/fluid_env.py:51-57 |
| FlexEnv.reset loads a cached configuration and state and returns only the observation | upstream_code | softgym/envs/flex_env.py:153-175 |

Tags (short lowercase keywords): softgym, pour-water, fluid, deformable-object, reinforcement-learning,
simulation, gymnasium.
