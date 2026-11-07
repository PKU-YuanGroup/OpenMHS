# Facts and tags for gh.amathislab/musclemimic_models

Every fact cites its source at commit `001b723e1be89a055a4cf79d23e2e7aaf968fb40`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

The package serves the card's main model, the MJCF scene `musclemimic_models/model/arm/myoarm_bimanual.xml`
(`models[0]`), as a `MujocoDriver`. It reads the model file from the read-only clone; the package copies neither the
model nor its assets.

| fact | source | ref |
|---|---|---|
| The card's main model is the MJCF scene myoarm_bimanual.xml, whose root element is '<mujoco model="MuscleMimic MyoBiamanualArm">' | upstream_code | musclemimic_models/model/arm/myoarm_bimanual.xml:2 |
| The repository registry maps the name bimanual to arm/myoarm_bimanual.xml and myofullbody to body/myofullbody.xml | upstream_code | musclemimic_models/__init__.py:10-13 |
| The upstream load() builds the model with mujoco.MjModel.from_xml_path and returns it with mujoco.MjData(model) | upstream_code | musclemimic_models/__init__.py:25-27 |
| The scene includes the shared scene file ../scene/musclemimic_scene.xml | upstream_code | musclemimic_models/model/arm/myoarm_bimanual.xml:19 |
| The scene includes the arm's asset and default-class definitions from ./assets/myoarm_bimanual_assets.xml | upstream_code | musclemimic_models/model/arm/myoarm_bimanual.xml:20 |
| The arm is the fixed-base body named Bimanual, attached directly under worldbody at pos -.025 0.1 1 | upstream_code | musclemimic_models/model/arm/myoarm_bimanual.xml:23-24 |
| The scene includes the kinematic chain ./assets/myoarm_bimanual_body.xml inside the Bimanual body | upstream_code | musclemimic_models/model/arm/myoarm_bimanual.xml:25 |
| The model sets the integration timestep to 0.002 s with <option timestep="0.002"/> | upstream_code | musclemimic_models/model/arm/assets/myoarm_bimanual_assets.xml:21 |
| The nested default class muscle sets the muscle control range -1 to 1 (ctrllimited true, ctrlrange "-1 1") | upstream_code | musclemimic_models/model/arm/assets/myoarm_bimanual_assets.xml:37-38 |
| The default class upperarm_muscle repeats the -1 to 1 control range for the upper-arm muscle actuators | upstream_code | musclemimic_models/model/arm/assets/myoarm_bimanual_assets.xml:53-54 |
| The default class forearm_muscle sets the -1 to 1 control range for the forearm muscle actuators | upstream_code | musclemimic_models/model/arm/assets/myoarm_bimanual_assets.xml:57-58 |
| The MyoBimanualArm row of the model table lists 76 joints (36 with finger muscles disabled) and 126 muscles (64 with finger muscles disabled) | vendor_doc | README.md:127 |
| The README states that the minimum required MuJoCo version for both models is mujoco==3.2.1 | vendor_doc | README.md:154 |

Limits: the driver declares none. The bridge derives the `cap.world.step.v1` input `action.ctrl` from the model
itself (one `[-1, 1]` interval per actuator, from `actuator_ctrlrange`; the class source is `upstream_code` and the
reference is the model file), so no `operator_required` bound is needed. The control range is the model's normalized
muscle excitation range, not a hardware limit.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `mujoco:MuscleMimic MyoBimanualArm`, level F1 (a
musculoskeletal MuJoCo model with muscles and tendons), determinism `seeded` with `seed_control` `none` (the bridge
has no seed input; a reset restores the model defaults), timestep 2 ms (`option timestep="0.002"`,
`myoarm_bimanual_assets.xml:21`), `realtime_factor` 0, clock `lockstep`, reset `full`, snapshot and restore offered
by the bridge. The gaps say what is not modelled and that this package's fake was not compared with MuJoCo.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable.

Tags: biomechanics, bimanual, mujoco, muscle, musculoskeletal, simulation
