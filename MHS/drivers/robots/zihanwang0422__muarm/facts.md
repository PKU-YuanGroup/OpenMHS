# Facts and tags for gh.zihanwang0422/muarm

Every fact cites its source at commit `9d328f16df05b5a6199ebd0c59048d58c6cd6326`, path from the clone root. The same
facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this
page. The package serves the card's first MJCF model, `learning/assets/panda_pick_place.xml` (card `models[0]`).

| fact | source | ref |
|---|---|---|
| The package's model is the MJCF scene panda_pick_place, whose root element is `<mujoco model="panda_pick_place">` | upstream_code | learning/assets/panda_pick_place.xml:1 |
| The pick_place scene includes ../../models/franka_emika_panda/scene.xml | upstream_code | learning/assets/panda_pick_place.xml:2 |
| The pick_place scene adds a target site and a pick_obj body with a freejoint and a box geom | upstream_code | learning/assets/panda_pick_place.xml:4-8 |
| The included scene.xml includes panda.xml | upstream_code | models/franka_emika_panda/scene.xml:2 |
| panda.xml declares the radian angle unit, autolimits and the assets mesh directory | upstream_code | models/franka_emika_panda/panda.xml:2 |
| panda.xml sets the implicitfast integrator in its option element and states no timestep | upstream_code | models/franka_emika_panda/panda.xml:4 |
| The panda default class sets joint armature 0.1, damping 1, axis 0 0 1 and range -2.8973 to 2.8973 | upstream_code | models/franka_emika_panda/panda.xml:9 |
| The panda default general actuator sets ctrlrange -2.8973 to 2.8973 and forcerange -87 to 87 | upstream_code | models/franka_emika_panda/panda.xml:10 |
| The finger default class makes its joints slide with range 0 to 0.04 | upstream_code | models/franka_emika_panda/panda.xml:11-12 |
| joint2 overrides the default joint range to -1.7628 to 1.7628 | upstream_code | models/franka_emika_panda/panda.xml:144 |
| joint4 overrides the default joint range to -3.0718 to -0.0698 | upstream_code | models/franka_emika_panda/panda.xml:159 |
| joint6 overrides the default joint range to -0.0175 to 3.7525 | upstream_code | models/franka_emika_panda/panda.xml:178 |
| The model has eight general actuators: actuator1 to actuator7 act on joint1 to joint7, and actuator8 acts on the split tendon of the two finger joints | upstream_code | models/franka_emika_panda/panda.xml:264-278 |
| actuator2, actuator4 and actuator6 override the default ctrlrange with -1.7628 to 1.7628, -3.0718 to -0.0698 and -0.0175 to 3.7525 | upstream_code | models/franka_emika_panda/panda.xml:266-273 |
| actuator8 has ctrlrange 0 to 255 on the split tendon and forcerange -100 to 100 | upstream_code | models/franka_emika_panda/panda.xml:275-277 |
| The two finger joints are coupled by an equality constraint | upstream_code | models/franka_emika_panda/panda.xml:260-261 |
| The model has a home keyframe with qpos `0 0 0 -1.57079 0 1.57079 -0.7853 0.04 0.04` and ctrl `0 0 0 -1.57079 0 1.57079 -0.7853 255` | upstream_code | models/franka_emika_panda/panda.xml:280-281 |

Limits: the driver declares none. The only bound of the step action is `action.ctrl`, which the bridge derives per
actuator from the model's `actuator_ctrlrange` (`cap.world.step.v1` in `reference.json`); it is a bound of the model,
not a number this package invents. The device is simulated (R0), so no limit is `operator_required` and no
`site-limits.example.json` is needed.

The card's entry symbols are Gymnasium environment classes (`learning/robots/panda.py:82` `FrankaPandaEnv`,
`learning/robots/so_arm.py:29` `SoArm100Env`; and the three `panda_mujoco_gym` environments). They exist in the
clone, but this package serves the card's first MJCF model directly through `MujocoDriver` (the card's `helper`), so
it declares no `native` class; the environments are not served. Their reset and step behavior is not part of this
package.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `mujoco:panda_pick_place`, level F1, determinism
seeded, `seed_control` none, `realtime_factor` 0, clock `lockstep`, reset full. The time step is read from the model's
`<option>` element; `panda.xml:4` states only the integrator, so the deployed MuJoCo default applies and the fake
uses a marked placeholder. The gaps say what the stand-in does not model and that no MuJoCo run was compared.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable.

Tags: arm, franka, manipulation, mujoco, panda, robot, simulation
