# Facts and tags for gh.ritalaezza/gym-agx

Every fact cites its source at commit `1773c4aa3ecc2e509623ff3d14163f9d5721f227`: `upstream_code` (a Python file of
the clone) or `vendor_doc` (a text file of the clone such as README.md). The same facts are in `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| BendWire-v0 is registered with entry point gym_agx.envs:BendWireEnv, n_substeps=2 and max_episode_steps=1000 | upstream_code | gym_agx/__init__.py:30-35 |
| The action space is Box(-1, 1) with one element per velocity-controlled end-effector constraint | upstream_code | gym_agx/envs/agx_goal_env.py:142 |
| The default right gripper has three velocity-controlled translation constraints (x, y and z) and a hinge constraint that is not velocity-controlled, so its action vector has three elements | upstream_code | gym_agx/envs/explicit/bend_wire_env.py:74-102 |
| The action time step is the AGX simulation time step times n_substeps | upstream_code | gym_agx/envs/agx_goal_env.py:149-151 |
| The BendWire scene builder sets TIMESTEP to 1/100 s (100 Hz) and N_SUBSTEPS to 2 | upstream_code | gym_agx/sims/bend_wire.py:34-35 |
| The reward is dense with range -1.5 to 1.5, success when the curvature distance is below 0.05, and success does not end the episode | upstream_code | gym_agx/envs/explicit/bend_wire_env.py:110-114 |
| The dense reward is the negative curvature distance clipped to the configured reward range, or the upper reward bound minus 100 times the end-effector speed clipped to zero and the upper bound when the goal is reached | upstream_code | gym_agx/envs/explicit/bend_wire_env.py:24-37 |
| Rewards are rounded with np.round(..., decimals=4) | upstream_code | gym_agx/envs/explicit/bend_wire_env.py:39-40 |
| Success means the curvature distance is below the configured threshold | upstream_code | gym_agx/envs/explicit/bend_wire_env.py:42-44 |
| step() returns the legacy Gym tuple observation, reward, done, info | upstream_code | gym_agx/envs/agx_goal_env.py:166-178 |
| reset() restores the start scene and returns a fresh observation | upstream_code | gym_agx/envs/agx_goal_env.py:180-188 |
| The default observation configuration adds DLO curvature and end-effector position observations, with DLO curvature and end-effector velocity as goals | upstream_code | gym_agx/envs/explicit/bend_wire_env.py:104-108 |
| The observation is a dict with observation, achieved_goal and desired_goal | upstream_code | gym_agx/envs/dlo_env.py:107-116 |
| construct_space gives every numpy observation leaf a Box with infinite bounds | upstream_code | gym_agx/utils/utils.py:17-20 |
| The right gripper's max_velocity is 10/1000 m/s and its max_acceleration is 10/1000 m/s^2 | upstream_code | gym_agx/envs/explicit/bend_wire_env.py:79-80 |
| rescale_velocity limits the speed change per call to max_acceleration*dt and clamps the speed to max_velocity | upstream_code | gym_agx/rl/end_effector.py:183-186 |
| The goal assembly is added from the goal scene file and a randomized goal is sampled only when randomized_goal is set | upstream_code | gym_agx/envs/dlo_env.py:134-147 |
| The BendWire cable is declared with LENGTH 0.1 m, RADIUS as LENGTH/100, LENGTH increased by 2*RADIUS, and RESOLUTION 1000 segments per metre | upstream_code | gym_agx/sims/bend_wire.py:36-39 |
| get_cable_curvature allocates cable_segment_edges.shape[1] - 2 values, one per adjacent pair of cable segments | upstream_code | gym_agx/utils/utils.py:243-248 |
| AgxGoalEnv.__init__ calls self.seed(); the class defines no seed method of its own, so the method comes from its external Gym base | upstream_code | gym_agx/envs/agx_goal_env.py:133-134 |
| The README describes the package as the OpenAI Gym interface for the AGX Dynamics simulation software | vendor_doc | README.md:3 |
| The environments import AGX Dynamics and raise DependencyNotInstalled without it | upstream_code | gym_agx/envs/agx_env.py:9-20 |

Limits: the driver declares none of its own. The only bound is the environment's action space, which the bridge derives
from the backend (`Box(-1, 1)` with three elements, no source, ref
`action_space of the fake backend .fake:FakeBendWireEnv`), and `ticks` (1 to `max_ticks`, 10000 by default). The device
is simulated (R0), so no limit is `operator_required` and there is no `site-limits.example.json`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `agx-dynamics:BendWire-v0`, level F1 (rigid-body dynamics
with contacts in AGX Dynamics), determinism `seeded` with `seed_control` `parameter` and the caveat in the notes that
`BendWireEnv.reset()` takes no seed, timestep 20 ms (`TIMESTEP = 1/100` s times `n_substeps = 2`, `gym_agx/sims/bend_wire.py:34-35`
and `gym_agx/__init__.py:33`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps say
what is not modelled: the fake is analytic and not AGX Dynamics, the real curvature array comes from cable segments in
the binary scene file `gym_agx/envs/assets/bend_wire.agx` (one value per adjacent segment pair, about 100 for the 0.1 m
cable at 1000 segments per metre, while the fake returns 8), and nothing was validated against a physical device.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable.

Tags: gym-agx, bend-wire, deformable-linear-object, reinforcement-learning, simulation, agx-dynamics
