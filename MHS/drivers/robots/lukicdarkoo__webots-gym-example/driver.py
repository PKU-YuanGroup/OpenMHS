"""OpenMHS driver for gh.lukicdarkoo/webots-gym-example: a Webots Pioneer3at pole-balancing Gym environment.

``controllers/gym_controller/gym_controller.py:16`` defines ``WebotsStickEnv`` as a ``Supervisor`` plus a legacy
``gym.Env``.  The controller runs only inside a Webots R2021a simulation: ``reset`` restarts the world
(``simulationResetPhysics`` and ``simulationReset``), binds four wheel motors and a hinge ``PositionSensor``, and
returns a fixed four-zero observation.  ``step`` sets every wheel target velocity to 1.3 or -1.3 rad/s, advances one
Webots step and returns the legacy four-tuple ``(state, reward, done, info)``.  There is no seed and no time limit.
The bridge therefore serves ``cap.world.step.v1`` (``{ticks, action}`` with ``action.index`` 0 or 1 from the
``Discrete(2)`` space), ``cap.world.reset.v1`` and ``cap.world.seed.v1``; the seed is recorded but the upstream reset
is fixed at zero.

This is a GymnasiumDriver, as the card says: the environment is a Gymnasium-shaped object, not a text transport.
The gate cannot run Webots, so the ``fake`` backend is this package's pure-Python analytic stand-in (``fake.py``).
No ``sim`` backend is offered: the class is not registered with ``gymnasium.make`` and its base ``Supervisor`` exists
only inside Webots.  The real Webots path was never run.

The ``fidelity`` contract describes the analytic model that is actually deployed on the checked backend (spec
05-fidelity FID-002): level F0, an analytic transition per step, no rigid-body dynamics and no physical time step.
It does not claim to reproduce Webots' physics.  Every fact cites a line of the clone at the pinned commit
dd825e00f89f187f53130bcbde1ddd2a3ca44ab2.  The package is model-authored and unreviewed; only the fake backend is
checked.
"""

from mhs.driver import Fact, GymnasiumDriver

CONTROLLER = "controllers/gym_controller/gym_controller.py"
WORLD = "worlds/webotsgym.wbt"


class WebotsStick(GymnasiumDriver):
    device_id = "webots-stick"
    env_id = "WebotsEnv-v0"
    native = "controllers.gym_controller.gym_controller:WebotsStickEnv"
    backends = {"fake": ".fake:FakeWebotsStickEnv"}
    action_space_ref = f"{CONTROLLER}:32"
    display_name = "Webots Pioneer3at pole balancer (legacy gym)"
    vendor, model = "lukicdarkoo", "webots-gym-example"
    tags = ["webots", "pioneer3at", "inverted-pendulum", "reinforcement-learning", "simulation", "gymnasium",
            "legacy-gym"]
    facts = [
        Fact("The controller imports Supervisor from Webots' embedded controller module, not from a serial, USB, VISA "
             "or vendor transport library", source="upstream_code", ref=f"{CONTROLLER}:2"),
        Fact("WebotsStickEnv subclasses Supervisor and gym.Env", source="upstream_code", ref=f"{CONTROLLER}:16"),
        Fact("The action space is Discrete(2)", source="upstream_code", ref=f"{CONTROLLER}:32"),
        Fact("The position threshold is 0.3 and the pole-angle threshold is 0.2 rad; the observation upper bound is "
             "twice each threshold for the position and angle entries and float32 maximum for the two velocity "
             "entries", source="upstream_code", ref=f"{CONTROLLER}:21-33"),
        Fact("Each action sets all four wheel target velocities to 1.3 rad/s when the action is 1 and to -1.3 rad/s "
             "otherwise", source="upstream_code", ref=f"{CONTROLLER}:76-77"),
        Fact("The observation is [robot position z, robot velocity z, position-sensor value, POLE_ENDPOINT angular "
             "velocity z]", source="upstream_code", ref=f"{CONTROLLER}:81-84"),
        Fact("The episode is done when the position or the pole angle passes its threshold", source="upstream_code",
             ref=f"{CONTROLLER}:87-92"),
        Fact("The reward is 0 on the step that reports done and 1 otherwise", source="upstream_code",
             ref=f"{CONTROLLER}:94-95"),
        Fact("reset restarts the simulation physics and the world, then rebinds the four wheels and the position "
             "sensor", source="upstream_code", ref=f"{CONTROLLER}:50-66"),
        Fact("reset takes no seed or options and returns a fixed four-zero observation", source="upstream_code",
             ref=f"{CONTROLLER}:50-72"),
        Fact("step returns the legacy four-tuple (state, reward, done, info)", source="upstream_code",
             ref=f"{CONTROLLER}:97"),
        Fact("The constructor default max_episode_steps is 1000 and is stored in EnvSpec(id='WebotsEnv-v0'); reset "
             "and step never enforce a time limit or truncate", source="upstream_code", ref=f"{CONTROLLER}:17-35"),
        Fact("The world file is a Webots R2021a world", source="upstream_code", ref=f"{WORLD}:1"),
        Fact("The world places a Pioneer3at with controller gym_controller and supervisor TRUE", source="upstream_code",
             ref=f"{WORLD}:13-15"),
        Fact("The balancing pole is attached through a HingeJoint with a PositionSensor", source="upstream_code",
             ref=f"{WORLD}:17-26"),
        Fact("The pole is a 0.5 m cylinder with a 0.1 m ball at POLE_ENDPOINT whose mass is 0.2 kg",
             source="upstream_code", ref=f"{WORLD}:31-56"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop no step or reset is accepted until "
                  "mhs.safety.reset clears the latch, and the last observation stays readable")
    #: Fidelity contract of the model on the checked fake backend (spec 05-fidelity section 2).  The upstream Webots
    #: physics is not reproduced: the fake is an analytic, event-driven transition with no physical time step.
    fidelity = {
        "engine": "analytic:webots-gym-example",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "exact",
            "notes": "the upstream reset always starts from the fixed four-zero observation and the fake has no "
                     "randomness, so the same action sequence from a fresh world gives the same state hashes; "
                     "cap.world.seed.v1 is recorded by the bridge but does not change the fixed reset",
        },
        "timestep_ms": 0.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "no rigid-body dynamics, contacts, friction, wheel slip, motor model, sensor noise or gravity: each step "
            "is a discrete analytic update, and the real trajectories come from Webots' physics, which was not run",
            "timestep_ms is 0 because the Webots basic time step is not stated in the clone (WorldInfo has no "
            "basicTimeStep); one tick is one controller step, not a physical duration",
            "the fake reset reproduces the upstream fixed four-zero observation but not simulationReset or "
            "simulationResetPhysics, and the fake was never compared with a Webots run",
            "no wall-clock pacing: realtime_factor is 0",
            "no physical device is modelled and there is no hardware backend",
            "snapshot and restore are not offered: the upstream class exposes no get_state or set_state",
        ],
    }
