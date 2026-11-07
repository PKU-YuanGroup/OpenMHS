# Facts and tags for gh.turagalab/flybody

Every fact cites its source at commit `d015e9bfe441bd90ae431bac24c55cb74bdbce26`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The model sets its integration step to 0.0001 s, gravity (0, 0, -981), density 0.00128 and viscosity 0.000185 | upstream_code | flybody/fruitfly/assets/fruitfly.xml:4 |
| The environment loads the model from assets/fruitfly.xml (the file this package carries as model.xml) | upstream_code | flybody/fruitfly/fruitfly.py:21 |
| The floor scene includes fruitfly.xml and adds a 5 by 5 plane floor at z -0.132 | upstream_code | flybody/fruitfly/assets/floor.xml:10-13 |
| The walker spawns at (0, 0, 0.1278) m | upstream_code | flybody/fruitfly/fruitfly.py:23 |
| The action groups are adhesion, head, mouth, antennae, wings, abdomen, legs and user, each disabled until it is enabled | upstream_code | flybody/fruitfly/fruitfly.py:24-32 |
| The root body carries the free joint named 'free' | upstream_code | flybody/fruitfly/assets/fruitfly.xml:309 |
| The actuator section declares the model's actuators as general and adhesion elements | upstream_code | flybody/fruitfly/assets/fruitfly.xml:819-898 |
| The default section scales the meshes by 0.1 and gives the geoms friction 0.5 | upstream_code | flybody/fruitfly/assets/fruitfly.xml:9-10 |
| The main default class makes every general actuator ctrl-limited | upstream_code | flybody/fruitfly/assets/fruitfly.xml:11 |

Model: `model.xml` is a byte-identical copy of `flybody/fruitfly/assets/fruitfly.xml` (918 lines, 65 787 bytes); the
package carries the model XML only. The 80 mesh `.obj` assets the XML references (about 154 MB) are not carried, so a
real MuJoCo load of this package needs them beside `model.xml`.

Fake backend: the MuJoCo engine is not installed where the gate runs. The card's mock path is the upstream simulator,
so `fake.py` is a stand-in `mujoco` module that parses the integration step and the joint and actuator counts of
`model.xml` and advances a minimal state (time and qpos = qvel * timestep). It computes no equations of motion,
contacts, adhesion or actuator dynamics; it reads each actuator's `ctrlrange` and `ctrllimited` from the model's
default classes (model review 2026-11-05: the author's stand-in published none), and the `fidelity` `gaps` of the driver
state every difference.

Limits: the step limits are the model's per-actuator `ctrlrange`, which the bridge derives from the stand-in's
reading of `model.xml` (`upstream_code`, ref `model.xml:actuator_ctrlrange`): the main default makes every actuator
ctrl-limited (`flybody/fruitfly/assets/fruitfly.xml:11`) and the default classes give the ranges (the wings -1 to 1,
the adhesion actuators 0 to 1, each leg joint its own). No Limit is declared and no operator overlay is needed.

Tags: mujoco, fruit-fly, drosophila, biomechanics, simulation
