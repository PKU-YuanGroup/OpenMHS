# Facts and tags for gh.sjtu-visys-team/visfly

Every fact cites its source at commit `6ff29bfcbc752da4f9474f6f0ece29d836111a22`: `vendor_doc` (a text file of the
clone such as `readme.md`) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| VisFly is a quadrotor simulator for vision-based flight and is built on Habitat-Sim | vendor_doc | readme.md:3-6 |
| The demo datasets are built from ReplicaCAD and are downloaded separately from Hugging Face with Git LFS | vendor_doc | readme.md:36-48 |
| The modified habitat-sim is cloned separately and built from source | vendor_doc | readme.md:62-73 |
| The conda environment pins habitat-sim==0.3.1 | upstream_code | environment.yml:334 |
| NavigationEnv extends DroneGymEnvsBase | upstream_code | envs/NavigationEnv.py:27 |
| DroneGymEnvsBase extends the stable-baselines3 VecEnv | upstream_code | envs/base/droneGymEnv.py:19 |
| NavigationEnv defaults to seed 42, visual=True and max_episode_steps=256 | upstream_code | envs/NavigationEnv.py:32-41 |
| The action space is a four-element Box with low -1 and high 1 for bodyrate, thrust, velocity and position control | upstream_code | envs/base/droneGymEnv.py:108-116 |
| The default action type is bodyrate | upstream_code | envs/base/dynamics.py:29 |
| The control interval ctrl_dt defaults to 0.03 s and the integration step dt to 0.005 s | upstream_code | envs/base/dynamics.py:32-33 |
| The state is position (3), orientation quaternion (4), velocity (3) and angular velocity (3), 13 values in total | upstream_code | envs/base/dynamics.py:779-786 |
| The observation space is a Dict whose state Box has state_size elements | upstream_code | envs/base/droneGymEnv.py:76-82 |
| NavigationEnv adds a target Box of 3 values to the observation space and the default target is [9, 0, 1] | upstream_code | envs/NavigationEnv.py:58-59 |
| When visual is true the observation also carries a depth array read from the sensor observations | upstream_code | envs/NavigationEnv.py:69-74 |
| reset accepts an optional state and returns the observations | upstream_code | envs/base/droneGymEnv.py:302-309 |
| The reset state is a four- or six-part tuple: position, orientation, velocity, angular velocity and optionally motor speed and thrust | upstream_code | envs/base/droneEnv.py:270-276 |
| step requires a reset first, converts the action to a tensor and advances the simulator | upstream_code | envs/base/droneGymEnv.py:141-146 |
| An episode is done on success, failure, out of bounds, collision, or when the step count reaches max_episode_steps | upstream_code | envs/base/droneGymEnv.py:187-193 |
| collect_info sets TimeLimit.truncated when the step count has reached max_episode_steps | upstream_code | envs/base/droneGymEnv.py:264-267 |
| Success means the distance from the position to the target is at most success_radius | upstream_code | envs/NavigationEnv.py:81-82 |
| The success radius defaults to 0.5 | upstream_code | envs/NavigationEnv.py:61 |
| DroneEnvsBase.set_seed forwards the seed to the dynamics and the scene manager | upstream_code | envs/base/droneEnv.py:381-385 |
| Dynamics.set_seed calls torch.manual_seed | upstream_code | envs/base/dynamics.py:556-557 |
| The dynamics constructor seeds itself with its seed argument | upstream_code | envs/base/dynamics.py:80 |

Limits: the driver declares none of its own. The only action bound is the environment's four-element action space,
which `GymnasiumBridge` derives from the live space (`-1` to `1` per component, `envs/base/droneGymEnv.py:108-116`);
`ticks` is bounded by the bridge (1 to 10000). The device is simulated (R0), so no limit is `operator_required` and
no `site-limits.example.json` is shipped.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `analytic`, level F0 (the checked fake is a kinematic
stand-in, not the Habitat-Sim model), determinism `seeded` with `seed_control` `parameter`, timestep 30 ms (the
upstream `ctrl_dt` of 0.03 s, `envs/base/dynamics.py:33`), `realtime_factor` 0, clock `lockstep`, reset `full`, no
snapshot and restore. The gaps say that rigid-body dynamics, motors, contacts, wind, sensor noise and the depth/RGB
rendering are not modelled and that the fake reward and start state are test data.

Safety: simulated R0 device. The e-stop is the runtime's software latch (there is no native stop to call); after it no
step, reset or seed is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and
the world state stays readable.

Tags: drone, quadrotor, navigation, vision-based-flight, reinforcement-learning, simulation, habitat-sim, gymnasium
