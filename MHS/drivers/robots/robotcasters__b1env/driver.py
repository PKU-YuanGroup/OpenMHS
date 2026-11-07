"""OpenMHS driver for gh.robotcasters/b1env: the Unitree B1 simulation environment (a Gymnasium family driver).

A GymnasiumDriver is configuration only: the bridge derives the contract from the environment's action and
observation spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with a 12-element ``action.values`` bounded by
the URDF effort limits, ``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The
device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no operator-required limit.

The upstream ``B1Sim`` is a ``gymnasium.Env`` subclass but not a standard Gymnasium environment: ``reset`` and
``step`` return only the info dict ``{"q", "dq"}`` (B1Env/b1_env.py:118-121 and :132-138), and the class is not
registered with gymnasium (the clone calls no ``register``).  There is therefore no ``env_id`` and no implicit
``gymnasium.make`` backend: ``backends`` names the package's own fake, which is the only backend checked here.

The gate cannot import the upstream module: it imports numpy, pybullet and gymnasium and builds a pinocchio
``RobotWrapper`` (B1Env/b1_env.py:3-16 and :54-55), while the README installs pinocchio and bullet_utils separately
(README.md:12-24) and setup.cfg does not list them (setup.cfg:18-22).  The ``fake`` backend is a pure Python
per-joint kinematic stand-in (see fake.py).  The upstream PyBullet environment was not run and the fake was never
compared with it.

The ``fidelity`` attribute is the fidelity contract of the model as deployed (spec 05-fidelity FID-002): the tested
backend is the kinematic fake, so it is F0.  The bridge's derived contract calls the environment "seeded"; the
upstream reset draws no random values and this package claims no seed-controlled replay.  Every fact cites a line of
the clone at the pinned commit cdf57676193c1bbe15960157aac059a291c0e89c.  This package is model-authored and
unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

B1_ENV = "B1Env/b1_env.py"
B1_URDF = "B1Env/robots/b1_raw.urdf"


class UnitreeB1(GymnasiumDriver):
    device_id = "unitree-b1"
    env_id = None
    native = "B1Env.b1_env:B1Sim"
    backends = {"fake": ".fake:FakeB1Sim"}
    display_name = "Unitree B1 Simulation Environment (B1Sim)"
    vendor, model = "RobotCasters", "Unitree B1"
    tags = ["unitree", "b1", "quadruped", "pybullet", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("The project titles itself the Unitree B1 Simulation Environment, a simulation environment for the "
             "Unitree B1 robot", source="vendor_doc", ref="README.md:1-2"),
        Fact("B1Sim subclasses gymnasium.Env and imports Env and spaces from gymnasium", source="upstream_code",
             ref=f"{B1_ENV}:6-19"),
        Fact("The constructor opens an in-process PyBullet client: GUI when render_mode is 'human' and DIRECT "
             "otherwise", source="upstream_code", ref=f"{B1_ENV}:31-36"),
        Fact("PyBullet gravity is (0, 0, -9.81) and the PyBullet time step is 1/240 s", source="upstream_code",
             ref=f"{B1_ENV}:38-39"),
        Fact("The bundled b1_raw.urdf is loaded at base position [0.0, 0.0, 1.0], with useFixedBase passed through",
             source="upstream_code", ref=f"{B1_ENV}:46-52"),
        Fact("A pinocchio RobotWrapper is built from the same URDF", source="upstream_code",
             ref=f"{B1_ENV}:54-55"),
        Fact("The spaces are built from every non-fixed joint: observation q bounds from jointLowerLimit and "
             "jointUpperLimit, the velocity bound from jointMaxVelocity, and the action bounds from "
             "+-jointMaxForce", source="upstream_code", ref=f"{B1_ENV}:69-79"),
        Fact("The observation Box is the joint positions followed by the joint velocities and the action Box is the "
             "joint torques, all as float32 arrays", source="upstream_code", ref=f"{B1_ENV}:89-95"),
        Fact("reset sets 12 target joint angles to 0.0 and resets each active joint to angle 0.0 with velocity 0.0",
             source="upstream_code", ref=f"{B1_ENV}:113-116"),
        Fact("reset returns only the q/dq info dict, not a gymnasium (observation, info) pair", source="upstream_code",
             ref=f"{B1_ENV}:118-121"),
        Fact("step applies the torque command, advances PyBullet by one step and returns only the q/dq info dict, "
             "not a gymnasium five-tuple", source="upstream_code", ref=f"{B1_ENV}:132-138"),
        Fact("get_info returns {'q': q, 'dq': dq}", source="upstream_code", ref=f"{B1_ENV}:150-156"),
        Fact("get_state reads 12 joint positions and velocities with p.getJointState over the active joint ids",
             source="upstream_code", ref=f"{B1_ENV}:162-176"),
        Fact("send_joint_command applies the commanded torques with p.TORQUE_CONTROL and zero position and velocity "
             "gains", source="upstream_code", ref=f"{B1_ENV}:203-219"),
        Fact("The hip joint limit is effort 91.0035, lower -0.75, upper 0.75 and velocity 19.69; the same limit is "
             "declared for the other three hips", source="upstream_code", ref=f"{B1_URDF}:62"),
        Fact("The thigh joint limit is effort 93.33, lower -1.0, upper 3.5 and velocity 23.32; the same limit is "
             "declared for the other three thighs", source="upstream_code", ref=f"{B1_URDF}:119"),
        Fact("The knee joint limit is effort 140, lower -2.6, upper -0.6 and velocity 15.55; the same limit is "
             "declared for the other three knees", source="upstream_code", ref=f"{B1_URDF}:176"),
        Fact("setup.cfg declares numpy>=1.22.3, scipy==1.8.0, pybullet==3.2.5 and gymnasium==0.26.3 as "
             "install_requires; pinocchio and bullet_utils are installed separately per the README",
             source="upstream_code", ref="setup.cfg:18-22"),
        Fact("The README requires pinocchio and bullet_utils to be installed before the package itself",
             source="vendor_doc", ref="README.md:12-24"),
    ]
    safe_state = ("the simulation stops advancing: the runtime latches the e-stop, no further step or reset is "
                  "accepted until mhs.safety.reset clears the latch, and the last joint state stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine
    #: and clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "analytic:B1Sim-fake",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "seed_control": "none",
            "notes": "the upstream reset accepts seed and options but draws nothing from them: it zeroes the 12 "
                     "actuated joints and leaves the floating base and the PyBullet world in place, so a reset does "
                     "not restore a known initial state. The dynamics are deterministic given the same state and "
                     "torques, but no seed-controlled or reset-based replay is claimed; the fake follows the same "
                     "zeroing",
        },
        "timestep_ms": 1000.0 / 240.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "partial",
        "snapshot_restore": False,
        "gaps": [
            "the tested fake backend is a per-joint kinematic stand-in: no contacts, floating-base dynamics, "
            "inertia coupling, gravity, friction, actuator or sensor model, and no mesh or plane scene; it was "
            "never compared with the upstream PyBullet environment, which was not run",
            "the upstream reset zeroes only the 12 actuated joints (b1_env.py:113-116) and does not restore the "
            "PyBullet world or the floating base, so reset is partial; the fake mirrors that zeroing",
            "the upstream reset and step return only {'q', 'dq'} (b1_env.py:118-121 and :132-138); the fake converts "
            "q and dq into the 24-element observation and returns reward 0 with terminated and truncated false so "
            "the Gymnasium bridge can serve the environment",
            "the upstream reset sets every active joint to 0.0 (b1_env.py:113-116) while the four knees have the "
            "URDF upper limit -0.6 (b1_raw.urdf:176), so the reset observation lies outside the observation Box for "
            "those joints; the bridge carries the observation as returned and does not reject it",
            "the package is checked on the fake backend only: the upstream needs pybullet, gymnasium, numpy, "
            "pinocchio and bullet_utils (setup.cfg:18-22, README.md:12-24) and no upstream run was made",
            "no wall-clock pacing (realtime_factor 0); only cap.world.step.v1 advances simulated time, one 1/240 s "
            "PyBullet step per tick",
            "rendering (render_mode 'human', b1_env.py:31-34) is not exposed by the cap.world.* classes",
            "snapshot and restore are not offered: B1Sim exposes get_state but no set_state",
        ],
    }
