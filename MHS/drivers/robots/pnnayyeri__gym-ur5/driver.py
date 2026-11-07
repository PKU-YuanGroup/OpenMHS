"""OpenMHS driver for gh.pnnayyeri/gym-ur5: the UR5 robot with a Jaco hand in a CoppeliaSim scene.

The upstream entry point is ``gym_ur5.envs:UR5Env``, a ``gym.Env`` (the legacy OpenAI Gym API, not gymnasium) that
connects to a running CoppeliaSim remote API server at 127.0.0.1:19997.  Its action space is a 3-vector of position
offsets in [-1.0, 1.0] (the code clips every component to the current observation +-0.1); its observation is
``[X, Y, Z, force_z_1, force_z_2, force_z_3]``.  ``step`` returns the legacy four-value ``obs, reward, done, info``
tuple and ``reset`` takes no seed or options argument and returns the observation only.

This is a simulator (card ``safety.expected_mode`` "simulated"), so the driver is a ``GymnasiumDriver`` configuration:
``env_id`` names the registered environment and the bridge derives the whole ``cap.world.*`` contract from the
environment's spaces.  The ``fake`` backend is this package's own pure Python stand-in (fake.py), because the gate
does not have CoppeliaSim, the upstream package, ``gym`` or the vendored PyCopp shared library.  A backend name that
``backends`` does not list (``sim``) would be served by ``gymnasium.make("ur5-v0")`` through ``GymnasiumDriver
.open_native``; upstream registers that id with legacy ``gym`` only, so on a machine with gymnasium installed the
bridge's ``gym.make`` fallback is not reached.  That path was not run here and is disclosed in the fidelity gaps.

The ``fidelity`` attribute is the contract of the model as deployed (spec 05-fidelity FID-002).  Every fact below
cites a line of the clone at commit e515a405d6619456a8cd77f8e5108e7f0bc08246.  The physics timestep is configured
inside the binary CoppeliaSim scene and the upstream code neither reads nor reports it, so ``timestep_ms`` is 0 and the
gap says so; no number was invented.  The package is model-authored and unreviewed and is checked on the fake backend
only (evidence ``contract_checked``).
"""

from mhs.driver import Fact, GymnasiumDriver

UR5_ENV = "gym_ur5/envs/ur5_env.py"


class GymUR5(GymnasiumDriver):
    device_id = "gym-ur5"
    env_id = "ur5-v0"
    native = "gym_ur5.envs:UR5Env"
    backends = {"fake": ".fake:FakeUR5Env"}
    action_space_ref = f"{UR5_ENV}:33"
    display_name = "gym-ur5: UR5 robot with Jaco hand in CoppeliaSim"
    vendor, model = "pnnayyeri", "gym-ur5"
    tags = ["ur5", "coppeliasim", "robotics", "reinforcement-learning", "simulation", "gym"]
    facts = [
        Fact("gym_ur5 registers the environment id ur5-v0 with entry point gym_ur5.envs:UR5Env",
             source="upstream_code", ref="gym_ur5/__init__.py:3-6"),
        Fact("UR5Env is a gym.Env subclass whose constructor opens a CoppeliaSim remote API connection to 127.0.0.1 "
             "port 19997, tries five times and raises IOError when the client id is -1",
             source="upstream_code", ref=f"{UR5_ENV}:10-22"),
        Fact("The environment switches CoppeliaSim to synchronous mode with simxSynchronous(clientID, True)",
             source="upstream_code", ref=f"{UR5_ENV}:24"),
        Fact("The action space is a float32 Box of shape (3,) with bounds -1.0 and 1.0, and the observation space is "
             "a float32 Box of shape (6,) with bounds -inf and +inf", source="upstream_code",
             ref=f"{UR5_ENV}:33-34"),
        Fact("step clips every requested action component to the current observation's first three values minus or "
             "plus 0.1", source="upstream_code", ref=f"{UR5_ENV}:64"),
        Fact("The clipped action is written as the float signals actionX, actionY and actionZ and the simulation is "
             "advanced with one simxSynchronousTrigger call", source="upstream_code", ref=f"{UR5_ENV}:74-87"),
        Fact("The observation is [X, Y, Z, F1z, F2z, F3z]: the XYZ values from getKinectXYZ and the z component "
             "of each of the three force vectors", source="upstream_code", ref=f"{UR5_ENV}:94-98"),
        Fact("getKinectXYZ reads the actX, actY and actZ float signals, in simx_opmode_streaming when initialize "
             "is true and in simx_opmode_buffer otherwise", source="upstream_code", ref=f"{UR5_ENV}:192-202"),
        Fact("The force sensor handles are built in a loop over range(1, 4) from the name pattern "
             "JacoHand_forceSens2_finger{}", source="upstream_code", ref=f"{UR5_ENV}:140-142"),
        Fact("getForce reads the three force sensor handles with simxReadForceSensor and returns their three "
             "vectors", source="upstream_code", ref=f"{UR5_ENV}:205-215"),
        Fact("The episode is done when the movePathDone float signal equals 1", source="upstream_code",
             ref=f"{UR5_ENV}:101-104"),
        Fact("step returns obs, reward, done, info, the four-value legacy Gym API result", source="upstream_code",
             ref=f"{UR5_ENV}:61-71"),
        Fact("reset takes no arguments, writes renderEnv=0, runs resetSim and prepareSim, and returns the observation "
             "only (the legacy Gym API)", source="upstream_code", ref=f"{UR5_ENV}:107-113"),
        Fact("resetSim stops the simulation with simxStopSimulation and raises IOError unless it returns "
             "simx_return_ok, sleeps one second, re-enters synchronous mode, starts the simulation, clears the "
             "actionX, actionY and actionZ signals and zeroes the reward and step counter", source="upstream_code",
             ref=f"{UR5_ENV}:271-292"),
        Fact("prepareSim calls initializeFunctions and then advances the simulation one synchronous step at a time "
             "until the isTracking float signal equals 1, writing the current X, Y and Z signals as the action at "
             "each iteration", source="upstream_code", ref=f"{UR5_ENV}:251-268"),
        Fact("The reward accumulates the negative squared distance between the Tip and TargetObject positions; step "
             "adds to the previous reward instead of replacing it", source="upstream_code", ref=f"{UR5_ENV}:241-248"),
        Fact("The simulation timestep is not set by this code: the sim_timestep = 0.5 assignment is commented out "
             "and its comment says the step is set in CoppeliaSim", source="upstream_code", ref=f"{UR5_ENV}:30"),
        Fact("The environment imports a module named sim", source="upstream_code", ref=f"{UR5_ENV}:1"),
        Fact("The vendored PyCopp client chooses remoteApi.so, remoteApi.dll or remoteApi.dylib by platform and "
             "loads it from the pycopp directory with ctypes.CDLL", source="upstream_code", ref="pycopp/sim.py:11-21"),
        Fact("setup.py installs only gym>=0.12.1", source="upstream_code", ref="setup.py:5"),
        Fact("The README describes the repository as a UR5 robot with a Jaco hand as gripper", source="vendor_doc",
             ref="README.md:2"),
        Fact("The README instructs opening the coppelia scene UR5-Gripper-thread-pyapi.ttt in coppeliaSim",
             source="vendor_doc", ref="README.md:10"),
    ]
    safe_state = ("the simulation stops advancing: the runtime's e-stop latch refuses step, reset and seed calls "
                  "until mhs.safety.reset clears it, and the last observation stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The timestep is chosen inside the
    #: binary CoppeliaSim scene and is not exposed by the upstream code, so it is 0 rather than an invented number;
    #: the environment has no seed and no snapshot, so no determinism claim is made.
    fidelity = {
        "engine": "coppeliasim:UR5-Gripper-thread-pyapi.ttt",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "none",
            "notes": "the environment exposes no seed and no snapshot/restore and this package did not run a "
                     "repeatability test against CoppeliaSim, so it makes no determinism claim (FID-008 to FID-010); "
                     "the cap.world.* bindings carry the Gymnasium bridge's derived 'seeded' field, which is the "
                     "bridge's default and not a claim of this driver",
        },
        "timestep_ms": 0.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the physics timestep is configured inside the binary CoppeliaSim scene and the upstream code neither "
            "reads nor reports it (the only value is the commented-out 0.5 s at ur5_env.py:30), so timestep_ms is 0 "
            "and a tick does not carry a declared simulated duration",
            "the model is a rigid-body CoppeliaSim scene: its physics engine, contact parameters, friction, mass "
            "properties and noise are chosen inside the binary scene file and are not modelled or disclosed by this "
            "package; the force sensors and the camera are scene objects",
            "no actuator, sensor or noise model: the action is an ideal position offset written as three float "
            "signals and the three Jaco hand force vectors are returned by the scene as raw values",
            "no wall-clock pacing and no validation: realtime_factor is 0, the fake is a kinematic stand-in that was "
            "not compared with CoppeliaSim, and the model was never validated against a physical UR5",
            "the sim backend was not run: it needs CoppeliaSim with the UR5-Gripper-thread-pyapi.ttt scene, the "
            "upstream package installed, legacy gym importable and the PyCopp remoteApi library for the running "
            "platform (the clone vendors only remoteApi.dll); the environment is registered with gym, not gymnasium",
            "the legacy Gym API carries no seed and no snapshot: reset() takes no seed or options argument and "
            "returns only the observation, step() returns obs, reward, done, info, and there is no get_state/set_state",
        ],
    }
