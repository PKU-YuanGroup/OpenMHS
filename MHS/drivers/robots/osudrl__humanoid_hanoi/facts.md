# Facts and tags for gh.osudrl/humanoid_hanoi

Every fact cites its source at commit `64bc880efe38c7a357f57ac2d2bb888334ec0284`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md, or a PDF page as `docs/manual.pdf:PAGE`) or `upstream_code`
(`path/in/clone.py:LINE`). The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated
from the driver, not from this page.

The package serves the card's first model, the MJCF scene `sim/digit_sim/digit-v3-box-tower-of-hanoi.xml` (`models[0]`),
as a `MujocoDriver`. Digit is the default `--robot` of the upstream evaluation entry point (`eval.py:12`; README.md:47).
The card also lists the g1 and h1 scenes; one `MujocoDriver` serves one model file, so those two are not served by this
package. It reads the model file from the read-only clone; the package copies neither the model nor its assets.

| fact | source | ref |
|---|---|---|
| The card's first model is the MJCF scene digit-v3-box-tower-of-hanoi.xml, whose root element is `<mujoco model='digit'>` | upstream_code | sim/digit_sim/digit-v3-box-tower-of-hanoi.xml:1 |
| The model integrates with timestep 0.0005 s, Newton solver, 50 iterations, impratio 20, elliptic cone and gravity 0 0 -9.80665 | upstream_code | sim/digit_sim/digit-v3-box-tower-of-hanoi.xml:3 |
| The floating base of the torso is three slide joints (x, y and z, the z joint with ref 1.01) and a ball joint | upstream_code | sim/digit_sim/digit-v3-box-tower-of-hanoi.xml:89-92 |
| The scene adds three box bodies (box0, box1 and box2), each with three slide joints and a ball joint | upstream_code | sim/digit_sim/digit-v3-box-tower-of-hanoi.xml:360-391 |
| The actuator section has 20 motor actuators, one per named leg and arm joint, with per-motor ctrlrange: hip-roll, shoulder-roll, shoulder-pitch and elbow -1.4125 to 1.4125; hip-yaw and shoulder-yaw -1.5835307242068533 to 1.5835307242068533; hip-pitch -13.557993638726353 to 13.557993638726353; knee -14.457309387714753 to 14.457309387714753; toe-a and toe-b -0.8395188473154137 to 0.8395188473154137 | upstream_code | sim/digit_sim/digit-v3-box-tower-of-hanoi.xml:404-423 |
| The joint tree gives 82 qpos and 72 qvel coordinates: the base 3 slides and 1 ball, the three boxes 9 slides and 3 balls, and 30 hinges plus 6 balls in the legs and arms | upstream_code | sim/digit_sim/digit-v3-box-tower-of-hanoi.xml:89-387 |
| The equality section has six connect constraints coupling the left and right achilles rods, toe-a rods and toe-b rods | upstream_code | sim/digit_sim/digit-v3-box-tower-of-hanoi.xml:394-401 |
| The model has a gyro, an accelerometer and a magnetometer on the torso IMU site, with cutoff 34.9, 157 and 2.5 and noise 0.00173, 0.0396 and 0.001 | upstream_code | sim/digit_sim/digit-v3-box-tower-of-hanoi.xml:425-428 |
| The upstream evaluation entry point defaults --robot to "digit", with "h1" and "g1" as the other choices | upstream_code | eval.py:12 |
| The README names the Digit humanoid robot as the default robot | vendor_doc | README.md:47 |

Limits: the driver declares none. The only bound is the bridge's `cap.world.step.v1` input `action.ctrl`, which the
bridge derives from the model itself (one interval per actuator, `actuator_ctrlrange`; source `upstream_code` and the
reference is the model file). The 20 intervals are listed in the actuator fact above: the widest are the knee
+-14.457309387714753 and the hip-pitch +-13.557993638726353, the narrowest the toe +-0.8395188473154137. No limit is
`operator_required`: every numeric bound is stated by the model at the cited lines.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `mujoco:digit`, level F1 (rigid-body model of the Digit and
the three boxes), determinism `seeded` with `seed_control` `none` (a reset restores the model defaults; the bridge takes
no seed input), timestep 0.5 ms (`timestep='0.0005'` s, `sim/digit_sim/digit-v3-box-tower-of-hanoi.xml:3`),
`realtime_factor` 0, clock `lockstep`, reset `full`, snapshot and restore through the bridge's fallback copy of time,
qpos, qvel and ctrl. The gaps say what is not modelled and that this package's fake was not compared with the real
engine.

The fake backend (`fake.py`) is a stand-in for the `mujoco` library, not MuJoCo: it parses the MJCF for the actuator
count, control ranges, joint dimensions and time step, but integrates a placeholder first-order motion of each actuated
joint toward its control target. It loads no mesh or texture, resolves no contact, equality or tendon constraint,
simulates none of the three IMU sensors, and was never compared with the real engine. MuJoCo was not installable where
the gate ran (no network, no pip), so the real `sim` backend was not run.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable. No operator-required limit and no hardware stop apply.

Tags: digit, humanoid, hanoi, manipulation, mujoco, simulation, robot
