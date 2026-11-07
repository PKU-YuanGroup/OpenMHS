# Facts and tags for gh.enac-drones/dronesim

Every fact cites its source at commit `158e40f4631e64d731f16f81641f629fa7b2a986`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| dronesim is a pyBullet and gym-pybullet-drones based heterogeneous multi vehicle control and simulation framework | vendor_doc | README.md:3 |
| BaseAviary subclasses gym.Env | upstream_code | dronesim/envs/BaseAviary.py:122 |
| CtrlAviary subclasses BaseAviary | upstream_code | dronesim/envs/CtrlAviary.py:7 |
| CtrlAviary's action space is a Dict with one Box per drone, its low from that drone's MIN_PWM and its high from MAX_PWM | upstream_code | dronesim/envs/CtrlAviary.py:111-116 |
| The default tello drone has four actuators (actuator_nr=4) | upstream_code | dronesim/assets/tello.urdf:30 |
| The tello URDF's PWM limit is 0 to 1 per actuator | upstream_code | dronesim/assets/tello.urdf:47 |
| CtrlAviary declares a per-drone observation Dict {state: Box(16), neighbors: MultiBinary(NUM_DRONES)} | upstream_code | dronesim/envs/CtrlAviary.py:196-208 |
| The observation state vector stacks position (3), quaternion (4), roll-pitch-yaw (3), velocity (3), angular velocity (3) and the last motor command (4 for tello); its docstring declares it (20,) | upstream_code | dronesim/envs/BaseAviary.py:764-783 |
| BaseAviary.reset() takes no seed or options argument | upstream_code | dronesim/envs/BaseAviary.py:406 |
| BaseAviary.step returns the four-value tuple obs, reward, done, info | upstream_code | dronesim/envs/BaseAviary.py:555 |
| BaseAviary.step advances the PyBullet simulation with p.stepSimulation for each aggregate physics step | upstream_code | dronesim/envs/BaseAviary.py:543 |
| CtrlAviary's default physics frequency is 240 Hz | upstream_code | dronesim/envs/CtrlAviary.py:21 |
| BaseAviary sets TIMESTEP = 1.0 / SIM_FREQ | upstream_code | dronesim/envs/BaseAviary.py:185-186 |
| BaseAviary uses gravity 9.8 m/s^2 | upstream_code | dronesim/envs/BaseAviary.py:182 |
| CtrlAviary returns reward -1 on every step | upstream_code | dronesim/envs/CtrlAviary.py:278 |
| CtrlAviary returns done False on every step: it declares no terminal state | upstream_code | dronesim/envs/CtrlAviary.py:293 |
| CtrlAviary returns info {'answer': 42} on every step | upstream_code | dronesim/envs/CtrlAviary.py:308-310 |
| When initial_xyzs is None, drone i starts at (i*4*L, i*4*L, COLLISION_H/2 - COLLISION_Z_OFFSET + 0.1) | upstream_code | dronesim/envs/BaseAviary.py:360-372 |
| The adjacency matrix starts as the identity and marks a pair of drones as neighbours when their distance is below NEIGHBOURHOOD_RADIUS | upstream_code | dronesim/envs/BaseAviary.py:901-921 |
| setup.py installs only the top-level dronesim package and requires numpy, scipy, Pillow, matplotlib, cycler, gym and pybullet | upstream_code | setup.py:5-15 |

Limits: this driver declares none. The only bound is the action space, which the gymnasium bridge derives from the
fake environment (`CtrlAviary.py:111-116`): one Box per drone whose elements are the drone's PWM limits, and for the
default tello that is 0 to 1 per actuator (`tello.urdf:47`), four actuators (`tello.urdf:30`). The bridge publishes
those numbers as `action.values` limits with no source and ref `action_space of the fake backend .fake:FakeCtrlAviary`
(a derived limit, not a driver-declared one). The device is simulated, so no limit is `operator_required` and no
site-limits overlay is needed. `ticks` is bounded by the catalogue class and the family's `max_ticks` (1 to 10000).

The default one-tello world is what this package serves. The action bound depends on the configured drone model, so
another model or a multi-drone world needs its own fake and contract; the fidelity `gaps` say so. The fake publishes
the single tello's four PWM commands as one Box(4) instead of upstream's numeric-keyed Dict (`action.0` is not a valid
bridge limit path); for one drone the four commands are the same, and the fake's `step` also accepts the upstream
Dict form.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `dronesim:pybullet-CtrlAviary (package fake: analytic
kinematics)`, level F0 (the fake is kinematic; no forces, contacts, actuator, sensor or noise model), determinism
`seeded` with `seed_control` `parameter`, timestep 4.1667 ms (`freq=240`, `BaseAviary.py:185-186`), `realtime_factor` 0,
clock `lockstep`, reset `full`, no snapshot and restore. The upstream `reset()` takes no seed and the fake uses no RNG,
so every seed repeats the same trajectory; the seed is recorded but not consumed. The gaps also record that
CtrlAviary declares a 16-element state Box while `_getDroneStateVector` returns 20 values for tello (16 plus the last
four motor commands), and that the fake models one tello and was never compared with the upstream environment.

Safety: simulated world (mode `simulated`, risk R0, catalogue classes `cap.world.step.v1`, `cap.world.reset.v1` and
`cap.world.seed.v1` are R0). There is no hardware backend and no native stop path to a machine. The e-stop is the
runtime's software latch; after it no step, reset or seed is accepted until `mhs.safety.reset` clears the latch, and
the world state stays readable.

Tags: dronesim, pybullet, gym, quadrotor, multi-drone, simulation, world-sim
