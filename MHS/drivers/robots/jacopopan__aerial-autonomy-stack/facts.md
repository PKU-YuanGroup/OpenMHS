# Facts and tags for gh.jacopopan/aerial-autonomy-stack

Every fact cites its source at commit `bf1ca32ac8b13339da4b9bce742f46fcb9b5567c`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The README lists a steppable Gymnasium environment and faster-than-real-time, multi-instance simulation | vendor_doc | README.md:20 |
| The installation requires nvidia-driver, docker and nvidia-container-toolkit and builds the images with sim_build.sh | vendor_doc | README.md:46-47 |
| Installing aas-gym is pip3 install -e . from the aas-gym directory after the Installation steps | vendor_doc | README.md:321-325 |
| aas-gym describes itself as a Gymnasium wrapper for the aerial-autonomy-stack | upstream_code | aas-gym/pyproject.toml:4 |
| aas-gym requires Python ^3.12 and depends on numpy ^2.4, gymnasium ^1.2, docker ^7.1 and pyzmq ^27.1 | upstream_code | aas-gym/pyproject.toml:11-18 |
| AASEnv is a Gymnasium environment class with render modes human and ansi | upstream_code | aas-gym/src/aas_gym/aas_env.py:15-16 |
| The action space is a one-element Box of floats from -1.0 to 1.0 with dtype float32 | upstream_code | aas-gym/src/aas_gym/aas_env.py:35-40 |
| The observation space is a Box of the Gazebo /clock [seconds, nanoseconds] with low [0.0, 0.0] and high [inf, 1e9] | upstream_code | aas-gym/src/aas_gym/aas_env.py:41-46 |
| The constructor defaults are gym_freq_hz 50, an init duration of 80.0 s and a maximum episode length of 300.0 s | upstream_code | aas-gym/src/aas_gym/aas_env.py:20-33 |
| max_steps is int(MAX_EPISODE_LENGTH_SEC * GYM_FREQ_HZ), 15000 at the default 50 Hz | upstream_code | aas-gym/src/aas_gym/aas_env.py:33-51 |
| AASEnv creates the simulation container from the simulation-image:latest image | upstream_code | aas-gym/src/aas_gym/aas_env.py:165-166 |
| AASEnv creates one aircraft container from aircraft-image:latest per drone | upstream_code | aas-gym/src/aas_gym/aas_env.py:227-228 |
| reset restarts the simulation and aircraft containers, opens the ZeroMQ socket and sends the special action 9999.0 to reset the world | upstream_code | aas-gym/src/aas_gym/aas_env.py:290-352 |
| step reads force = action[0], sends it to the simulator and receives the clock in reply | upstream_code | aas-gym/src/aas_gym/aas_env.py:359-373 |
| Every step returns reward -1.0, terminated False, and truncated when step_count >= max_steps | upstream_code | aas-gym/src/aas_gym/aas_env.py:385-391 |
| The observation is np.array([sim_sec, sim_nanosec]) and info repeats them as sim_time_sec and sim_time_nanosec | upstream_code | aas-gym/src/aas_gym/aas_env.py:284-288 |
| reset passes seed only to gym.Env.reset, while the ZeroMQ reset payload is the constant 9999.0 and carries no seed | upstream_code | aas-gym/src/aas_gym/aas_env.py:290-328 |
| AASEnv-v0 is registered in gym_run.py with entry_point=AASEnv | upstream_code | tools_and_docs/gym_run.py:17-20 |
| The ZeroMQ bridge runs the world unpaused for init_duration seconds on reset and pauses it afterwards | upstream_code | simulation/simulation_ws/src/zmq_bridge_cpp/src/zeromq_bridge.cpp:165-186 |
| The ZeroMQ bridge publishes the double action on /action and advances the paused world by step_size physics steps | upstream_code | simulation/simulation_ws/src/zmq_bridge_cpp/src/zeromq_bridge.cpp:188-201 |
| The step target time is current_sim_time + step_size * physics_dt - 0.0001 s | upstream_code | simulation/simulation_ws/src/zmq_bridge_cpp/src/zeromq_bridge.cpp:197 |
| The bridge computes step_size = physics_freq_hz / gym_freq_hz and physics_dt is 0.004 s for PX4, so with the default gym_freq_hz 50 one control step is nominally 20 ms | upstream_code | simulation/simulation.yml.erb:23-42 |

Limits: the driver declares no limit of its own. The only action bound is the environment's action space, which the
Gymnasium bridge derives from ``Box(low=-1.0, high=1.0, shape=(1,))`` (`aas_env.py:35-40`) and publishes as
``action.values`` with no source and the reference ``action_space of the fake backend .fake:FakeAASEnv``. ``ticks``
is bounded by the family bridge's ``max_ticks``. The device is simulated (R0), so no bound is ``operator_required``.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine ``analytic``, level F0 (the checked fake models the clock
and the constant step reward, not Gazebo/PX4), determinism ``none`` with ``seed_control`` ``none`` (the seed reaches
only gym.Env's generator, not the simulator, `aas_env.py:291` and `:327-328`), timestep 20 ms nominal
(`simulation.yml.erb:23-42` and `zeromq_bridge.cpp:197`), ``realtime_factor`` 0, clock ``lockstep``, reset ``full``,
no snapshot and restore. The ``gaps`` say what the fake and the checked package do not model, including the unrun
Gazebo/PX4 simulation, rendering, camera and LiDAR, and the numpy observation arrays.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until ``mhs.safety.reset`` clears the latch, and the state stays readable.

Tags: aerial, drone, gazebo, px4, reinforcement-learning, simulation, gymnasium
