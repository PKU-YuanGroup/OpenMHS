# Facts and tags for gh.amathislab/musclemimic

Every fact cites its source at commit `47b653db2bce25de834360d2ee6b2dd88142bd78`: `vendor_doc` (text in the clone)
or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| MyoFullBody is a concrete MuJoCo environment class of a full-body humanoid model with muscle actuation, deriving from LocoEnv | upstream_code | musclemimic/environments/humanoids/myofullbody.py:17-22 |
| The repository's base class for MuJoCo environments is its own Mujoco class, declared at loco_mujoco/core/mujoco_base.py:44 | upstream_code | loco_mujoco/core/mujoco_base.py:44-46 |
| The constructor defaults are timestep 0.002 s, n_substeps 5 and disable_fingers True | upstream_code | musclemimic/environments/humanoids/myofullbody.py:56-58 |
| The action specification is every actuator name of the model, in the model's actuator order | upstream_code | musclemimic/environments/humanoids/myofullbody.py:394-407 |
| Every muscle actuator's control range is set to [-1, 1] with ctrllimited True | upstream_code | musclemimic/environments/humanoids/myofullbody.py:317-322 |
| The default control function normalizes the agent action space to [-1, 1] and rescales it to the actuator range | upstream_code | loco_mujoco/core/control_functions/default.py:24-90 |
| When disable_fingers is true the environment deletes the finger joints, finger muscles and their tendons | upstream_code | musclemimic/environments/humanoids/myofullbody.py:157-301 |
| The README model table lists MyoFullBody as free-root with 123 joints, 416 muscles and 72 DoFs, or 83 joints, 354 muscles and 32 DoFs with finger muscles disabled | vendor_doc | README.md:45-50 |
| The default model XML path is resolved by musclemimic_models.get_xml_path('myofullbody'), a separate package from this clone | upstream_code | musclemimic/environments/humanoids/myofullbody.py:449-453 |
| musclemimic_models is a declared runtime dependency of the project | upstream_code | pyproject.toml:70 |
| The environment registry registers MyoFullBody when the humanoids package is imported | upstream_code | musclemimic/environments/humanoids/__init__.py:1-9 |
| LocoEnv.reset forwards to the MuJoCo reset with a JAX key and returns the initial observation | upstream_code | musclemimic/environments/base.py:687-701 |
| The MuJoCo reset restores the data with mj_resetData and mj_forward and returns the initial observation | upstream_code | loco_mujoco/core/mujoco_base.py:194-228 |
| The MuJoCo step preprocesses the action, writes data.ctrl, runs mj_step for n_substeps and returns observation, reward, absorbing, done and info | upstream_code | loco_mujoco/core/mujoco_base.py:230-288 |
| done is absorbing or the current step count reaches the configured episode horizon | upstream_code | loco_mujoco/core/mujoco_base.py:378-398 |
| The default episode horizon is 1000 steps | upstream_code | loco_mujoco/core/mujoco_base.py:80-85 |
| The environment timestep is model.opt.timestep and one environment step advances simulation_dt times n_intermediate_steps times n_substeps | upstream_code | loco_mujoco/core/mujoco_base.py:1315-1333 |

## Shape and limits

The card proposes a `MujocoDriver`, but this clone ships no MJCF and the card's `models` list is empty. The model is
supplied at runtime by the separate `musclemimic_models` package (`myofullbody.py:449-453`). The entry symbol is the
environment class, whose primary interface is `reset(key)` and `step(action)`; its spaces are exposed only through
`env.info` (`mujoco_base.py:158`, `:1296-1303`), not as `action_space`/`observation_space` attributes. The package is
therefore a direct `Driver` (see `RESULT.json`, DEVIATION FROM THE CARD) with two bound classes:
`cap.world.step.v1` and `cap.world.reset.v1`.

Limits: `action.values` is bounded to [-1, 1] per element, the control range the environment sets on every muscle
actuator (`myofullbody.py:317-322`). The vector length is model-dependent: the action specification takes every
actuator name (`myofullbody.py:394-407`), and the README lists 354 muscles with finger muscles disabled
(`README.md:48`), but this driver does not hard-code a length and the native environment rejects a wrong-sized row.
No `operator_required` limit is needed and no `site-limits.example.json` is shipped. The device is simulated (R0).

## Fidelity contract

Engine `analytic:FakeMyoFullBody`, level F0, timestep 10 ms (0.002 s times 5 substeps per environment step,
`myofullbody.py:56-57` and `mujoco_base.py:1326-1333`), `realtime_factor` 0, clock `lockstep`, reset `full`, no
snapshot and restore. Determinism is `none`: the native reset takes a JAX key, the driver passes no key, and no
operator seed selects a trajectory. The `gaps` in `driver.py` list the fake stand-in, the external model, the
model-dependent vector lengths and the dependencies that were not run.

## Safety

Simulated R0 device with no hardware backend. The e-stop is the runtime's software latch; after it, no step or reset
is accepted until `mhs.safety.reset` clears the latch, and the last observation and tick stay readable. No native
stop exists, so the package declares no `@estop` and no safe-state action.

Tags: biomechanics, humanoid, jax, mujoco, muscle, musculoskeletal, simulation
