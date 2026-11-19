# Facts and tags for gh.kscalelabs/ksim-legacy

Every fact cites a text file of the clone at commit `c1b92feabeab90ad1ecd2c7ff8b6beb4b7a30652`; the
`driver.py` `facts` list is the source of truth and the reference file is generated from it, not from this page.
`upstream_code` means a code line or comment, `vendor_doc` a documentation text file (this clone has no PDF manual).

## Scope

The card names the brax `PipelineEnv` `ksim.mjx_gym.envs.stompy_env.stompy:StompyEnv` (`stompy.py:21`) and the
family `mujoco` with the `MujocoDriver` helper. This package serves the card model
`ksim/assets/stompy/stompy.xml`, the file that environment loads (`stompy.py:33-34`), through
`MujocoDriver`: the bridge's `cap.world.step.v1` writes a 31-element `action.ctrl` and runs `mj_step`, and
`cap.world.reset.v1` restores the model defaults. The environment's own reset noise, reward, healthy
termination, observation assembly and four-physics-step control period are not re-implemented; they remain
upstream and are listed as fidelity gaps. No upstream code is imported or run by this package.

The fake publishes engine `analytic:stompy` and level F0 through `fidelity_by_backend`. The raw-model F1
declaration does not describe this placeholder integration. The environment also overrides the XML solver with
CG and six solver/line-search iterations (`stompy.py:35-37`); the raw bridge does not apply those settings.
The e-stop halts bridge-owned lockstep integration and retains velocities and controls. Releasing the latch
advances no ticks; a new step without an action reuses the retained controls.

## Facts

| fact | source | ref |
|---|---|---|
| The repository describes itself as a library for training humanoid locomotion in MJX and MuJoCo | vendor_doc | README.md:17 |
| The environment registry maps the name stompy to StompyEnv | upstream_code | ksim/mjx_gym/envs/__init__.py:9 |
| get_env registers the selected class with brax and returns a brax environment | upstream_code | ksim/mjx_gym/envs/__init__.py:12-14 |
| StompyEnv is a brax PipelineEnv subclass | upstream_code | ksim/mjx_gym/envs/stompy_env/stompy.py:21 |
| StompyEnv builds its MJCF path as MODEL_DIR plus /stompy/stompy.xml | upstream_code | ksim/mjx_gym/envs/stompy_env/stompy.py:33 |
| StompyEnv loads the model with mujoco.MjModel.from_xml_path and converts it with brax.io.mjcf.load_model | upstream_code | ksim/mjx_gym/envs/stompy_env/stompy.py:34-39 |
| The environment declares four physics steps per control step and selects the mjx backend | upstream_code | ksim/mjx_gym/envs/stompy_env/stompy.py:41-43 |
| The initial qpos is read from the model keyframe named default, and the reward function is built from the reward parameters and the environment time step | upstream_code | ksim/mjx_gym/envs/stompy_env/stompy.py:53-55 |
| reset(rng) splits the key into three generators and adds uniform noise of plus or minus reset_noise_scale to the keyframe qpos and to the zero qvel before pipeline_init | upstream_code | ksim/mjx_gym/envs/stompy_env/stompy.py:57-72 |
| step takes a brax State, advances it with pipeline_step, computes the reward and sets done to 1 - is_healthy when terminate_when_unhealthy is true | upstream_code | ksim/mjx_gym/envs/stompy_env/stompy.py:89-119 |
| The model compiles in radians with autolimits enabled | upstream_code | ksim/assets/stompy/stompy.xml:3 |
| The model option sets a 0.001 s timestep, 50 iterations, the PGS solver and gravity 0 0 -9.81 | upstream_code | ksim/assets/stompy/stompy.xml:16 |
| The root body carries three slide joints (root_x, root_y, root_z) and one ball joint (root_ball) | upstream_code | ksim/assets/stompy/stompy.xml:61-64 |
| The left shoulder pitch joint declares range -3.14159 to 3.14159, actuatorfrcrange -80 to 80 and ref -0.534 | upstream_code | ksim/assets/stompy/stompy.xml:69 |
| The actuator section declares 31 motor actuators, each with ctrllimited true and ctrlrange -200 200 | upstream_code | ksim/assets/stompy/stompy.xml:230-262 |
| The model declares a keyframe named default with a qpos vector | upstream_code | ksim/assets/stompy/stompy.xml:360-361 |
| The runtime stack lists brax, jax and mujoco-mjx | upstream_code | ksim/requirements.txt:3-7 |
| The package requires Python 3.11 or newer | upstream_code | setup.py:35 |

## Limits

The package declares no `Limit` of its own. The control envelope is derived at run time from the model:
`stompy.xml:230-262` states `ctrllimited="true"` and `ctrlrange="-200 200"` for every one of the 31 motors, and
the `MujocoBridge` publishes that range per actuator as `action.ctrl`. No operator-required bound exists, so no
`site-limits.example.json` is needed. The bridge also bounds `ticks` with its `max_ticks` configuration; that is a
service limit of the bridge, not a device fact.

## Tags

`humanoid`, `kscale`, `locomotion`, `mujoco`, `mjx`, `simulation`, `stompy`, `world`, `robot`
