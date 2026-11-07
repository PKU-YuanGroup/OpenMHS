"""OpenMHS driver for gh.learnsyslab/gym-pybullet-drones: the CtrlAviary drone-control environment.

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives the
whole contract from the environment's spaces.  ``ctrl-aviary-v0`` is registered with entry point
``gym_pybullet_drones.envs:CtrlAviary`` and no keyword arguments (gym_pybullet_drones/__init__.py:3-6), so
``env_kwargs`` is empty and the environment runs with the class defaults: one CF2X drone, PyBullet and control
frequencies of 240 Hz, no GUI and no recording (CtrlAviary.py:12-26).

* ``cap.world.step.v1`` takes ``{ticks, action}`` with ``action`` ``{values: [..]}``: the four commanded propeller
  speeds of the drone, flattened from the ``(NUM_DRONES, 4)`` action ``Box`` whose bounds are 0 to ``MAX_RPM``
  (CtrlAviary.py:74-86).  CtrlAviary's own reward is the dummy value -1, its terminated and truncated flags are
  always False and its info is ``{"answer": 42}`` (CtrlAviary.py:144-200), so the episode never ends by itself.
* ``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``; a reset puts every drone
  back at its initial XYZ, identity attitude and zero velocity (BaseAviary.py:451-470, :194-205).
* the observation is the 20-value state vector per drone: position, quaternion, roll-pitch-yaw, linear velocity,
  angular velocity and the clipped motor commands (BaseAviary.py:541-561; the bounds in CtrlAviary.py:90-102).

The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no operator-required
limit.  The gate cannot import gym_pybullet_drones (it needs pybullet, numpy, Pillow and a PyBullet client), and
package code never imports the clone, so the ``fake`` backend is the package's own pure Python aviary (fake.py).
A backend name that ``backends`` does not list (``sim``) is served by ``gymnasium.make("ctrl-aviary-v0")``
(GymnasiumDriver.open_native); that path needs pybullet and the upstream package and was not run here.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002).
Every constant and rule cites a line of the clone at the pinned commit 7ebad1ecabd28a7000add2d05f888aa2e837c2cc.
This package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

REGISTRATION = "gym_pybullet_drones/__init__.py"
AVIARY = "gym_pybullet_drones/envs/BaseAviary.py"
CTRL = "gym_pybullet_drones/envs/CtrlAviary.py"
CF2X = "gym_pybullet_drones/assets/cf2x.urdf"
ENUMS = "gym_pybullet_drones/utils/enums.py"


class CtrlAviary(GymnasiumDriver):
    device_id = "ctrl-aviary"
    env_id = "ctrl-aviary-v0"
    native = "gym_pybullet_drones.envs:CtrlAviary"
    backends = {"fake": ".fake:FakeCtrlAviary"}
    display_name = "gym-pybullet-drones CtrlAviary (ctrl-aviary-v0)"
    vendor, model = "LearnSysLab", "gym-pybullet-drones (PyBullet drone simulation)"
    tags = ["quadrotor", "drone", "ctrl-aviary", "pybullet", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("ctrl-aviary-v0 is registered with entry point gym_pybullet_drones.envs:CtrlAviary and no keyword "
             "arguments", source="upstream_code", ref=f"{REGISTRATION}:3-6"),
        Fact("CtrlAviary defaults to drone model CF2X, one drone, physics PYB (PyBullet), pyb_freq 240 Hz, "
             "ctrl_freq 240 Hz, no GUI and no recording (CtrlAviary.py:12-26)", source="upstream_code",
             ref=f"{CTRL}:12-26"),
        Fact("The gravity constant is 9.8 m/s^2", source="upstream_code", ref=f"{AVIARY}:74"),
        Fact("The CF2X drone's parameters come from its URDF: arm 0.0397 m, kf 3.16e-10, km 7.94e-12, "
             "thrust2weight 2.25, maximum speed 30 km/h, motor mass 0.027 kg", source="upstream_code",
             ref=f"{CF2X}:5-11"),
        Fact("The thrust-to-weight constants give hover RPM sqrt(G*M/(4*KF)) and maximum RPM "
             "sqrt(thrust2weight*G*M/(4*KF))", source="upstream_code", ref=f"{AVIARY}:116-119"),
        Fact("The action space is a Box of shape (NUM_DRONES, 4): the commanded propeller speeds of each drone, "
             "bounded by 0 and MAX_RPM", source="upstream_code", ref=f"{CTRL}:74-86"),
        Fact("The action is clipped to [0, MAX_RPM] before it is applied, so an out-of-range command is clamped by "
             "the environment itself", source="upstream_code", ref=f"{CTRL}:121-140"),
        Fact("The observation space is a Box of shape (NUM_DRONES, 20): position, quaternion, roll-pitch-yaw, "
             "linear velocity, angular velocity and the clipped motor commands; z has a lower bound of 0, the "
             "quaternion components are bounded by +-1, the angles by +-pi and the motor commands by 0 and MAX_RPM",
             source="upstream_code", ref=f"{CTRL}:90-102"),
        Fact("The observation of a drone is the horizontal stack of its position, quaternion, rpy, velocity, "
             "angular velocity and last clipped action", source="upstream_code", ref=f"{AVIARY}:541-561"),
        Fact("CtrlAviary's reward is the dummy value -1, its terminated flag is False, its truncated flag is False "
             "and its info is {'answer': 42}", source="upstream_code", ref=f"{CTRL}:142-200"),
        Fact("ctrl-aviary-v0 is registered without max_episode_steps, so make() adds no TimeLimit and the "
             "environment never truncates", source="upstream_code", ref=f"{REGISTRATION}:3-6"),
        Fact("A reset re-creates the PyBullet simulation and zeroes the kinematic state: the drones start at their "
             "initial XYZ positions with identity attitude and no velocity", source="upstream_code",
             ref=f"{AVIARY}:220-258"),
        Fact("Without initial_xyzs every drone starts on the x axis at multiples of 4*arm, so the single drone of "
             "ctrl-aviary-v0 starts at the origin", source="upstream_code", ref=f"{AVIARY}:194-205"),
        Fact("The simulation timestep is 1/pyb_freq = 1/240 s and pyb_freq must be a multiple of ctrl_freq",
             source="upstream_code", ref=f"{AVIARY}:77-83"),
        Fact("The drone models are the enumerations CF2X, CF2P and RACE and the physics backends are PYB, DYN, "
             "PYB_GND, PYB_DRAG, PYB_DW and PYB_GND_DRAG_DW", source="upstream_code", ref=f"{ENUMS}:3-21"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "gymnasium:ctrl-aviary-v0",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the reset places the drone at a fixed initial state, so the seed does not change the "
                     "trajectory of this environment; the fake integrates a vertical model in Python floats while "
                     "the upstream environment runs PyBullet, so the two do not agree on a trajectory",
        },
        "timestep_ms": 1000.0 / 240.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "PyBullet rigid-body dynamics of the drone against the ground: the fake integrates only the vertical "
            "force balance (thrust from the mean motor speed against gravity) and leaves x, y, attitude and angular "
            "velocity at their reset values",
            "the four rotor forces, ground effect, drag, downwash, collisions with obstacles and the URDF collision "
            "shapes are not modelled",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by the 1/240 s pybullet timestep "
            "only",
            "no rendering, no video recording, no GUI debug sliders and no image capture (the vision attributes are "
            "off by default)",
            "the fake backend re-implements the environment in pure Python and was not compared with the upstream "
            "PyBullet environment (gym_pybullet_drones was not importable where the gate ran)",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
        ],
    }
