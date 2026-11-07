# Facts and tags for gh.pnnayyeri/gym-ur5

Every fact cites its source at commit `e515a405d6619456a8cd77f8e5108e7f0bc08246`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| gym_ur5 registers the environment id ur5-v0 with entry point gym_ur5.envs:UR5Env | upstream_code | gym_ur5/__init__.py:3-6 |
| UR5Env is a gym.Env subclass whose constructor opens a CoppeliaSim remote API connection to 127.0.0.1 port 19997, tries five times and raises IOError when the client id is -1 | upstream_code | gym_ur5/envs/ur5_env.py:10-22 |
| The environment switches CoppeliaSim to synchronous mode with simxSynchronous(clientID, True) | upstream_code | gym_ur5/envs/ur5_env.py:24 |
| The action space is a float32 Box of shape (3,) with bounds -1.0 and 1.0, and the observation space is a float32 Box of shape (6,) with bounds -inf and +inf | upstream_code | gym_ur5/envs/ur5_env.py:33-34 |
| step clips every requested action component to the current observation's first three values minus or plus 0.1 | upstream_code | gym_ur5/envs/ur5_env.py:64 |
| The clipped action is written as the float signals actionX, actionY and actionZ and the simulation is advanced with one simxSynchronousTrigger call | upstream_code | gym_ur5/envs/ur5_env.py:74-87 |
| The observation is [X, Y, Z, F1z, F2z, F3z]: the XYZ values from getKinectXYZ and the z component of each of the three force vectors | upstream_code | gym_ur5/envs/ur5_env.py:94-98 |
| getKinectXYZ reads the actX, actY and actZ float signals, in simx_opmode_streaming when initialize is true and in simx_opmode_buffer otherwise | upstream_code | gym_ur5/envs/ur5_env.py:192-202 |
| The force sensor handles are built in a loop over range(1, 4) from the name pattern JacoHand_forceSens2_finger{} | upstream_code | gym_ur5/envs/ur5_env.py:140-142 |
| getForce reads the three force sensor handles with simxReadForceSensor and returns their three vectors | upstream_code | gym_ur5/envs/ur5_env.py:205-215 |
| The episode is done when the movePathDone float signal equals 1 | upstream_code | gym_ur5/envs/ur5_env.py:101-104 |
| step returns obs, reward, done, info, the four-value legacy Gym API result | upstream_code | gym_ur5/envs/ur5_env.py:61-71 |
| reset takes no arguments, writes renderEnv=0, runs resetSim and prepareSim, and returns the observation only (the legacy Gym API) | upstream_code | gym_ur5/envs/ur5_env.py:107-113 |
| resetSim stops the simulation with simxStopSimulation and raises IOError unless it returns simx_return_ok, sleeps one second, re-enters synchronous mode, starts the simulation, clears the actionX, actionY and actionZ signals and zeroes the reward and step counter | upstream_code | gym_ur5/envs/ur5_env.py:271-292 |
| prepareSim calls initializeFunctions and then advances the simulation one synchronous step at a time until the isTracking float signal equals 1, writing the current X, Y and Z signals as the action at each iteration | upstream_code | gym_ur5/envs/ur5_env.py:251-268 |
| The reward accumulates the negative squared distance between the Tip and TargetObject positions; step adds to the previous reward instead of replacing it | upstream_code | gym_ur5/envs/ur5_env.py:241-248 |
| The simulation timestep is not set by this code: the sim_timestep = 0.5 assignment is commented out and its comment says the step is set in CoppeliaSim | upstream_code | gym_ur5/envs/ur5_env.py:30 |
| The environment imports a module named sim | upstream_code | gym_ur5/envs/ur5_env.py:1 |
| The vendored PyCopp client chooses remoteApi.so, remoteApi.dll or remoteApi.dylib by platform and loads it from the pycopp directory with ctypes.CDLL | upstream_code | pycopp/sim.py:11-21 |
| setup.py installs only gym>=0.12.1 | upstream_code | setup.py:5 |
| The README describes the repository as a UR5 robot with a Jaco hand as gripper | vendor_doc | README.md:2 |
| The README instructs opening the coppelia scene UR5-Gripper-thread-pyapi.ttt in coppeliaSim | vendor_doc | README.md:10 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the environment
(`Box(-1.0, 1.0, shape=(3,))`: `action.values` from -1.0 to 1.0 per element, source `upstream_code`, ref
`gym_ur5/envs/ur5_env.py:33`), and `ticks` (1 to `max_ticks`, 10000 by default). The device is simulated (R0), so no
limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `coppeliasim:UR5-Gripper-thread-pyapi.ttt`, level F1
(rigid-body dynamics with contacts; the scene is a CoppeliaSim UR5/Jaco scene), determinism `none` (no seed, no
snapshot and no repeatability test), timestep 0 ms because the timestep lives inside the binary scene and the upstream
code neither reads nor reports it (`ur5_env.py:30`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot
and restore. The gaps say what is not modelled: the physics engine and its parameters, the actuator and sensor models,
the wall-clock pacing, the validation and the never-run sim backend.

Safety: simulated R0 device with no hardware backend. The e-stop is the runtime's software latch; after it no step,
reset or seed is accepted until `mhs.safety.reset` clears the latch, and the last observation stays readable. The
fake backend is a kinematic stand-in, so the last three observation values never change and the "force" reading is
all zeros.

Tags: ur5, coppeliasim, robotics, reinforcement-learning, simulation, gym
