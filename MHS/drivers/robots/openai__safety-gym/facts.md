# Facts and tags for gh.openai/safety-gym

Every fact cites its source at commit `f31042f2f9ee61b9034dd6a416955972911544f5`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md, or a PDF page as `docs/manual.pdf:PAGE`) or
`upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The Engine default configuration uses the car model: `'robot_base': 'xmls/car.xml'` | upstream_code | safety_gym/envs/engine.py:112 |
| Engine builds a Robot from the configured robot XML before it derives the action space | upstream_code | safety_gym/envs/engine.py:305-306 |
| The action space is `Box(-1, 1, (robot.nu,))`: one control between -1 and 1 per actuator of the robot model | upstream_code | safety_gym/envs/engine.py:308 |
| Robot loads the configured XML with `load_model_from_path` and takes `nu` (the actuator count) from the loaded model | upstream_code | safety_gym/envs/world.py:370-383 |
| car.xml sets the simulation timestep to 0.004 s | upstream_code | safety_gym/xmls/car.xml:3 |
| The car model default motor has ctrlrange -1 1, ctrllimited true, forcerange -0.02 0.02 and forcelimited true | upstream_code | safety_gym/xmls/car.xml:7 |
| car.xml declares a free joint named robot, two hinge joints named left and right, and a ball joint named rear | upstream_code | safety_gym/xmls/car.xml:15-30 |
| car.xml has two motors, both jointinparent transmissions with gear 1, so the model has two actuators | upstream_code | safety_gym/xmls/car.xml:53-56 |
| The car body starts at 0 0 0.1 | upstream_code | safety_gym/xmls/car.xml:12 |
| The xmls README states each robot XML should be complete and simulate-able as-is | vendor_doc | safety_gym/xmls/README.md:7 |
| The xmls README states each robot XML should include actuators which provide control | vendor_doc | safety_gym/xmls/README.md:10 |
| The xmls README says a robot scene should be clear of other objects, with only the robot in the scene | vendor_doc | safety_gym/xmls/README.md:14-16 |
| The Engine default ends an episode after 1000 environment steps | upstream_code | safety_gym/envs/engine.py:98 |
| One Engine step advances the simulation by a binomial draw of up to 10 physics steps, and the default probability 1.0 makes it 10 steps | upstream_code | safety_gym/envs/engine.py:287-291 |
| Engine.step clips the action to the model's actuator_ctrlrange before writing data.ctrl | upstream_code | safety_gym/envs/engine.py:1245-1247 |

Limits: the driver declares none of its own. The only bound is the step's `action.ctrl`, which the MuJoCo bridge
derives from the model's `actuator_ctrlrange` and `actuator_ctrllimited` (`car.xml:7`: the two motors are limited to
-1 to 1). The model file is the source of the bound, so no limit is `operator_required` and no `site-limits.json` is
needed.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `mujoco:safety_gym/xmls/car.xml`, level F1 (rigid-body
dynamics with contacts of the model), determinism `seeded` with `seed_control` `none` (a reset restores the model
defaults and takes no seed), timestep 4 ms (`<option timestep="0.004">`, `car.xml:3`), `realtime_factor` 0, clock
`lockstep`, reset `full`, snapshot and restore offered by the bridge. The gaps say what is not modelled (the Engine's
task layer, MuJoCo's physics in the stand-in fake, the frameskip and the episode limit) and that MuJoCo itself was not
run.

Safety: simulated R0 device. The e-stop is the runtime's software latch (the bridge has no native stop); after it no
step or reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the
integration state stays readable.

Tags: car, mujoco, openai, reinforcement-learning, robot, safety-gym, simulation
