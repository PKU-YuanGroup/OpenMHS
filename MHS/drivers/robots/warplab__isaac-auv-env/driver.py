"""OpenMHS driver for gh.warplab/isaac-auv-env: the Isaac-WarpAUV-Direct-v1 Gymnasium task.

A GymnasiumDriver is configuration only: ``env_id`` names the environment and the bridge derives the contract from
the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action ``{values}`` bounded per
element by the environment's six-dimensional thruster Box (``-1.0`` to ``1.0``); ``cap.world.reset.v1`` takes
``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0): there is no hardware
backend and no native e-stop; the runtime's software latch is the stop.

The gate cannot run the upstream stack (IsaacSim 4.5.0, IsaacLab 2.2.0 and a GPU, README.md:12), and package code
never imports the clone.  The ``fake`` backend is therefore a pure Python stand-in written from the equations of
``warpauv_env.py``, ``thruster_dynamics.py`` and ``rigid_body_hydrodynamics.py``; it was not compared with a real
IsaacSim run.  A backend name that ``backends`` does not list (``sim``) is served by ``gymnasium.make(env_id)``
(GymnasiumDriver.open_native); that path needs the upstream stack and was not run here (README.md).

The ``fidelity`` attribute is the fidelity contract of the model as deployed (spec 05-fidelity FID-002).  The
driver is simulated R0 and serves a reduced analytic model, so the level is F0 and the gaps say which parts of
the upstream model are absent.  This package is model-authored and unreviewed: it is checked on the fake backend
only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "warpauv_env.py"
THRUSTER = "thruster_dynamics.py"
HYDRO = "rigid_body_hydrodynamics.py"


class WarpAUV(GymnasiumDriver):
    device_id = "warpauv"
    env_id = "Isaac-WarpAUV-Direct-v1"
    native = "warpauv_env:WarpAUVEnv"
    backends = {"fake": ".fake:FakeWarpAUVEnv"}
    action_space_ref = f"{ENV}:71"
    display_name = "WarpAUV IsaacLab direct environment"
    vendor, model = "WarpLab", "Isaac-WarpAUV-Direct-v1"
    tags = ["auv", "underwater", "isaac-lab", "isaac-sim", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("The task registers the Gymnasium id Isaac-WarpAUV-Direct-v1 with WarpAUVEnv as its entry point",
             source="upstream_code", ref="__init__.py:19-21"),
        Fact("The registration disables the Gymnasium environment checker", source="upstream_code",
             ref="__init__.py:22"),
        Fact("WarpAUVEnv is a DirectRLEnv subclass", source="upstream_code", ref=f"{ENV}:129"),
        Fact("The action space is Box(-1.0, 1.0, shape=(6,)): six continuous inputs in the range -1.0 to 1.0",
             source="upstream_code", ref=f"{ENV}:71"),
        Fact("The six actions are PWM commands between -1 and 1, one per thruster", source="upstream_code",
             ref=f"{ENV}:401-410"),
        Fact("The observation space is Box(-inf, inf, shape=(17,))", source="upstream_code", ref=f"{ENV}:70"),
        Fact("The observation concatenates the goal, the offset from the origin in the body frame, the root "
             "quaternion, the body-frame linear velocity and the body-frame angular velocity", source="upstream_code",
             ref=f"{ENV}:248-257"),
        Fact("The simulation physics timestep is 1/120 s", source="upstream_code", ref=f"{ENV}:61"),
        Fact("The configuration sets decimation = 2", source="upstream_code", ref=f"{ENV}:74"),
        Fact("The episode length cap is enabled with episode_length_s = 3.0", source="upstream_code",
             ref=f"{ENV}:75-76"),
        Fact("The configuration enables boundaries with max_auv_x = 7, max_auv_y = 7 and max_auv_z = 7",
             source="upstream_code", ref=f"{ENV}:81-84"),
        Fact("The done flags returned by _get_dones are the out-of-bounds flags and the time-out flags",
             source="upstream_code", ref=f"{ENV}:283-304"),
        Fact("starting_depth is 8", source="upstream_code", ref=f"{ENV}:85"),
        Fact("The robot's initial position is (0.0, 0.0, starting_depth)", source="upstream_code",
             ref=f"{ENV}:213"),
        Fact("goal_spawn_radius is 2.0", source="upstream_code", ref=f"{ENV}:91"),
        Fact("A reset offsets the initial position by a sample from a sphere of radius goal_spawn_radius",
             source="upstream_code", ref=f"{ENV}:316-318"),
        Fact("A reset draws the goal orientation from a random orientation", source="upstream_code",
             ref=f"{ENV}:346-348"),
        Fact("Actions are clipped to the range -1 to 1 before the dynamics are computed", source="upstream_code",
             ref=f"{ENV}:227-232"),
        Fact("Thruster commands with absolute value below 0.08 are zeroed; from 0.08 upward the command is "
             "converted by -139*v^2 + 500*v + 8.28 and from -0.08 downward by 161*v^2 + 517.86*v - 5.72",
             source="upstream_code", ref=f"{ENV}:408-410"),
        Fact("rotor_constant is 0.1/100.0", source="upstream_code", ref=f"{ENV}:111"),
        Fact("The rotor force conversion returns rotorConstant * |value| * value", source="upstream_code",
             ref=f"{THRUSTER}:141"),
        Fact("The first-order rotor time constant is 0.05 s", source="upstream_code", ref=f"{ENV}:112"),
        Fact("The rotor update sets alpha to zero so the state follows the command", source="upstream_code",
             ref=f"{THRUSTER}:110-115"),
        Fact("The dynamics allocate six thrusters per environment", source="upstream_code", ref=f"{ENV}:209"),
        Fact("The water density is 997.0 kg/m^3 and the dynamic viscosity is 0.001306 Pa s", source="upstream_code",
             ref=f"{ENV}:109-110"),
        Fact("The AUV mass is 22.701 kg and the volume is 0.022747843530591776 m^3, which the comment describes "
             "as neutrally buoyant", source="upstream_code", ref=f"{ENV}:113-115"),
        Fact("The inertia tensor used by the dynamics is (0.37, 0.97, 1.19)", source="upstream_code",
             ref=f"{ENV}:174-176"),
        Fact("The centre-of-buoyancy offset is [0.0, 0.0, 0.01] m", source="upstream_code", ref=f"{ENV}:108"),
        Fact("The quadratic drag force on each body axis is -2*rho*rj*rk*|v|*v and the viscous force is "
             "-6*beta*pi*r_eq*v", source="upstream_code", ref=f"{HYDRO}:68-90"),
        Fact("The reward scales are position 0.2, angle 0.5 and actions 0.2, with linear velocity, angular "
             "velocity and terminated at 0.0", source="upstream_code", ref=f"{ENV}:96-105"),
        Fact("The total reward is the sum of the angular, action, position and angular-velocity terms",
             source="upstream_code", ref=f"{ENV}:607"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    fidelity_level = "F0"
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the
    #: engine, determinism kind and lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "isaaclab:Isaac-WarpAUV-Direct-v1",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the initial position and goal of the fake, and the "
                     "integration is deterministic, so one implementation repeats a trajectory for the same seed "
                     "and actions; the fake draws with Python's random.Random while upstream uses torch and numpy "
                     "generators, so a seed does not reproduce upstream trajectories",
        },
        "timestep_ms": 1000.0 / 120.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is a reduced pure-Python model, not IsaacSim/PhysX: no contacts, no GPU physics, "
            "no domain randomization of mass or volume, no sensor or noise model, and its initial orientation "
            "and velocities are placeholders",
            "the fake integrates thrust, quadratic drag and viscous drag in one 1/120 s step per env.step, while "
            "the upstream environment runs decimation=2 physics substeps per control step and uses PhysX for the "
            "rigid-body integration; ticks therefore name fake timesteps, not upstream control steps",
            "the clone configures four parallel environments in one scene; the fake serves one environment and a "
            "17-element observation",
            "buoyancy and gravity are assumed to cancel, following the clone's comment that the volume makes the "
            "body neutrally buoyant; the fake does not model the small net buoyancy or the buoyancy torque from "
            "the centre-of-buoyancy offset",
            "the angular reward uses 1 - dot(goal, quaternion)^2 as a stand-in for the upstream "
            "quat_error_magnitude; no rendering is offered",
            "no wall-clock pacing: realtime_factor 0, so ticks advance simulated time by timestep_ms only",
            "no snapshot or restore: the environment exposes no get_state/set_state",
            "the fake was not compared with an IsaacSim/IsaacLab run; the upstream stack (IsaacSim 4.5.0, "
            "IsaacLab 2.2.0 and a GPU) was not installed or run here",
        ],
    }
