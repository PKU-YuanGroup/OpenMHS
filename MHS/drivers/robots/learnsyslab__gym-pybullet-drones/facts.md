# Facts and tags for gh.learnsyslab/gym-pybullet-drones

Every fact cites its source at commit `7ebad1ecabd28a7000add2d05f888aa2e837c2cc`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| ctrl-aviary-v0 is registered with entry point gym_pybullet_drones.envs:CtrlAviary and no keyword arguments | upstream_code | gym_pybullet_drones/__init__.py:3-6 |
| CtrlAviary defaults to drone model CF2X, one drone, physics PYB (PyBullet), pyb_freq 240 Hz, ctrl_freq 240 Hz, no GUI and no recording | upstream_code | gym_pybullet_drones/envs/CtrlAviary.py:12-26 |
| The gravity constant is 9.8 m/s^2 | upstream_code | gym_pybullet_drones/envs/BaseAviary.py:74 |
| The CF2X drone's parameters come from its URDF: arm 0.0397 m, kf 3.16e-10, km 7.94e-12, thrust2weight 2.25, maximum speed 30 km/h, motor mass 0.027 kg | upstream_code | gym_pybullet_drones/assets/cf2x.urdf:5-11 |
| The thrust-to-weight constants give hover RPM sqrt(G*M/(4*KF)) and maximum RPM sqrt(thrust2weight*G*M/(4*KF)) | upstream_code | gym_pybullet_drones/envs/BaseAviary.py:116-119 |
| The action space is a Box of shape (NUM_DRONES, 4): the commanded propeller speeds of each drone, bounded by 0 and MAX_RPM | upstream_code | gym_pybullet_drones/envs/CtrlAviary.py:74-86 |
| The action is clipped to [0, MAX_RPM] before it is applied, so an out-of-range command is clamped by the environment itself | upstream_code | gym_pybullet_drones/envs/CtrlAviary.py:121-140 |
| The observation space is a Box of shape (NUM_DRONES, 20): position, quaternion, roll-pitch-yaw, linear velocity, angular velocity and the clipped motor commands; z has a lower bound of 0, the quaternion components are bounded by +-1, the angles by +-pi and the motor commands by 0 and MAX_RPM | upstream_code | gym_pybullet_drones/envs/CtrlAviary.py:90-102 |
| The observation of a drone is the horizontal stack of its position, quaternion, rpy, velocity, angular velocity and last clipped action | upstream_code | gym_pybullet_drones/envs/BaseAviary.py:541-561 |
| CtrlAviary's reward is the dummy value -1, its terminated flag is False, its truncated flag is False and its info is {'answer': 42} | upstream_code | gym_pybullet_drones/envs/CtrlAviary.py:142-200 |
| ctrl-aviary-v0 is registered without max_episode_steps, so make() adds no TimeLimit and the environment never truncates | upstream_code | gym_pybullet_drones/__init__.py:3-6 |
| A reset re-creates the PyBullet simulation and zeroes the kinematic state: the drones start at their initial XYZ positions with identity attitude and no velocity | upstream_code | gym_pybullet_drones/envs/BaseAviary.py:220-258 |
| Without initial_xyzs every drone starts on the x axis at multiples of 4*arm, so the single drone of ctrl-aviary-v0 starts at the origin | upstream_code | gym_pybullet_drones/envs/BaseAviary.py:194-205 |
| The simulation timestep is 1/pyb_freq = 1/240 s and pyb_freq must be a multiple of ctrl_freq | upstream_code | gym_pybullet_drones/envs/BaseAviary.py:77-83 |
| The drone models are the enumerations CF2X, CF2P and RACE and the physics backends are PYB, DYN, PYB_GND, PYB_DRAG, PYB_DW and PYB_GND_DRAG_DW | upstream_code | gym_pybullet_drones/utils/enums.py:3-21 |

Limits: none are declared. The action space of the environment is the whole envelope of the device, and the bridge
derives the step action's per-element bounds from it (Box low 0, high MAX_RPM, CtrlAviary.py:74-86); the device is
simulated at R0, so the driver declares no safety limit and no operator-required bound.

Safety: a simulator has no hardware stop; the family serves an e-stop as a latch that refuses further steps and
resets until `mhs.safety.reset`, and `safe_state` says that. The package declares no `estop_physical_ref` (it is an
R2+ hardware requirement).

Tags: quadrotor, drone, ctrl-aviary, pybullet, reinforcement-learning, simulation, gymnasium
