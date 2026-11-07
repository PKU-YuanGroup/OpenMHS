# Facts and tags for gh.openai/mujoco-worldgen

Every fact cites its source at commit `39f52b1b47aed499925a6a214b58bdbdb4e2f75e`: `vendor_doc` for a text file
of the clone (README.md) and `upstream_code` for the MJCF model, the requirements file and the Python code. The same
facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this
page.

| fact | source | ref |
|---|---|---|
| The card's primary model is assets/xmls/particle/main.xml: its root is a <mujoco> element whose worldbody contains the body 'particle' with three slide joints named slide0, slide1 and slide2 on the x, y and z axes | upstream_code | assets/xmls/particle/main.xml:2-8 |
| The model's <option> element sets the integration timestep to 0.005 s | upstream_code | assets/xmls/particle/main.xml:3 |
| slide0 and slide1 have damping 0.1, while slide2 has damping 10000 | upstream_code | assets/xmls/particle/main.xml:6-8 |
| The particle body has a sphere geom of mass 1, half-size 0.15 and position 0 0 0 | upstream_code | assets/xmls/particle/main.xml:9 |
| The model declares two <motor> actuators with gear 100 on slide0 and slide1, and neither actuator states a ctrlrange, so the model file gives the two controls no limit | upstream_code | assets/xmls/particle/main.xml:16-19 |
| The README says actions in the action_space are all actuators of objects added during world building, and names ObjFromXML('particle') as an object with actuators | vendor_doc | README.md:7 |
| The README states that worldgen uses meters, kilograms and radians, with angles in [-pi, pi] | vendor_doc | README.md:33 |
| The README says the repository requires the MuJoCo physics engine, was tested with MuJoCo 1.50 and installs through mujoco-py | vendor_doc | README.md:13 |
| requirements.txt pins mujoco-py to >=1.50.1 and <1.50.2 | upstream_code | requirements.txt:7 |
| The repository is archived and its code is provided as-is with no updates expected | vendor_doc | README.md:1 |
| The simple_particle example loads the 'particle' object with ObjFromXML and builds a 4 x 4 x 2.5 world | upstream_code | examples/simple_particle.py:13-17 |
| The simple_particle example runs the environment with horizon 30 | upstream_code | examples/simple_particle.py:25 |
| ctrl_set_action copies a torque actuator's action into sim.data.ctrl, and adds the current qpos for a position actuator | upstream_code | mujoco_worldgen/util/sim_funcs.py:12-25 |
| When no explicit action bounds are given, Env's action space has nmocap * 7 + model.nu entries | upstream_code | mujoco_worldgen/env.py:241-243 |
| Env.step clamps the action to the action space, calls set_action and then sim.step | upstream_code | mujoco_worldgen/env.py:346-354 |

Limits: the driver declares none. The bridge derives `action.ctrl` from the model's `actuator_ctrlrange` and
`actuator_ctrllimited`; this model states no `ctrlrange` (assets/xmls/particle/main.xml:16-19) and no control value is
bounded by the model, so the bridge publishes `action.ctrl` as `operator_required`: the endpoint refuses a step that sets it
(`MHS.SAFETY.LIMITS_UNSET`, before any native call) until the site's `site-limits.json` bounds it, and a
step without `action` keeps the controls as they are. `site-limits.example.json` is operator example data
(-10 to 10 for every control), not a bound of the model; the package invents none. The step input still requires exactly `model.nu` = 2 control values, which the
bridge derives from the model.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `mujoco:worldgen-particle`, level F1, determinism `seeded`
with `seed_control` `none`, timestep 5 ms (`main.xml:3`), `realtime_factor` 0, clock `lockstep`, reset `full`, snapshot
and restore offered through the bridge's integration-state fallback. The gaps say that the fake is a placeholder
integrator, that it resolves no contact or friction, that MuJoCo was never imported, that the upstream world builder
and Env wrapper are not served, and that the card's second model is not served.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable. No hardware was attached and
no trajectory was compared with the real MuJoCo engine.

Tags: mujoco, particle, reinforcement-learning, robot, simulation, worldgen
