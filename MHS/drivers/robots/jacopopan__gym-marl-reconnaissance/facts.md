# Facts and tags for gh.jacopopan/gym-marl-reconnaissance

Every fact cites its source at commit `85a4373f3ebee66b12c88a0bdd5e4e96f9606e5a` (`upstream_code` is a line of the
clone). The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the
driver, not from this page.

| fact | source | ref |
|---|---|---|
| The environment is registered with gym as recon-arena-v0, entry point gym_marl_reconnaissance.envs.recon_arena:ReconArena | upstream_code | gym_marl_reconnaissance/__init__.py:3-5 |
| The constructor defaults are seed -1, ctrl_freq 5 Hz, pyb_freq 60 Hz, episode_length_sec 30 s, action_type task_assignment, obs_type global, reward_choice reward_a, adv_type avoidant, visibility_threshold 8 and a setup of edge 10 m, 0 obstacles, 1 Tello, 1 RoboMaster, 2 adversaries and 1 neutral agent | upstream_code | gym_marl_reconnaissance/envs/recon_arena.py:74-87 |
| A seed of -1 leaves numpy's global generator unseeded; any other seed calls np.random.seed(seed) | upstream_code | gym_marl_reconnaissance/envs/recon_arena.py:122-125 |
| The constructor derives _PYB_UPDATES_PER_STEP = pyb_freq/ctrl_freq and _PYB_TIMESTEP = 1/pyb_freq after rejecting a pyb_freq that is not divisible by ctrl_freq or is smaller | upstream_code | gym_marl_reconnaissance/envs/recon_arena.py:130-134 |
| step raises RuntimeError until reset has been called at least once | upstream_code | gym_marl_reconnaissance/envs/recon_arena.py:274-275 |
| The simulation gravity is 9.8 m/s2 and the Tello mass is 0.08 kg | upstream_code | gym_marl_reconnaissance/envs/recon_arena.py:136-139 |
| reset resets the PyBullet simulation, sets gravity, loads the plane and creates the obstacle, Tello, RoboMaster, adversary and neutral teams | upstream_code | gym_marl_reconnaissance/envs/recon_arena.py:210-221 |
| The action space is MultiDiscrete with one entry per learning agent (Tello plus RoboMaster): the number of adversaries plus neutrals for task_assignment (3 with the default setup) and 5 for tracking (stay, forward, backward, left, right) | upstream_code | gym_marl_reconnaissance/envs/recon_arena.py:353-359 |
| The global observation space is a Box of 5 values per Tello, RoboMaster, adversary, neutral and obstacle, with bounds -inf to +inf and dtype float32 | upstream_code | gym_marl_reconnaissance/envs/recon_arena.py:372-376 |
| The global observation concatenates, for each Tello and RoboMaster, its body id, class and position, then the same for visible adversaries and neutrals (zeros when not visible), then the obstacles | upstream_code | gym_marl_reconnaissance/envs/recon_arena.py:398-418 |
| A Tello has class 1 and a RoboMaster class 2 in the state | upstream_code | gym_marl_reconnaissance/envs/recon_arena.py:671-688 |
| An adversary has class 3 in the state | upstream_code | gym_marl_reconnaissance/envs/recon_arena.py:692-696 |
| A neutral agent has class 4 in the state | upstream_code | gym_marl_reconnaissance/envs/recon_arena.py:749-753 |
| An obstacle has class 5 in the state | upstream_code | gym_marl_reconnaissance/envs/recon_arena.py:807-814 |
| task_assignment forces the number of obstacles to 0 and the visibility threshold to np.inf | upstream_code | gym_marl_reconnaissance/envs/recon_arena.py:152-155 |
| Without obstacles, an adversary or neutral is visible when it is within visibility_threshold of a Tello or RoboMaster; with obstacles the line-of-sight ray must strike it as well | upstream_code | gym_marl_reconnaissance/envs/recon_arena.py:699-782 |
| A task_assignment action computes target_id = val + 1 + obstacles + tt + s1 and sets a velocity of 2 m/s toward the target, multiplied by 1.5 for a RoboMaster | upstream_code | gym_marl_reconnaissance/envs/recon_arena.py:518-542 |
| A tracking action is 0 stay, 1 forward, 2 backward, 3 left, 4 right, and the move vector is scaled by 1.2 | upstream_code | gym_marl_reconnaissance/envs/recon_arena.py:549-565 |
| An avoidant adversary flees a Tello or RoboMaster closer than 3 m at 2.25 times its own speed; otherwise it patrols along [1, -1] and flips its direction with probability 0.05 | upstream_code | gym_marl_reconnaissance/envs/recon_arena.py:609-621 |
| Adversary and neutral patrol speeds are drawn uniformly from 0.5 to 1.5 | upstream_code | gym_marl_reconnaissance/envs/recon_arena.py:223-226 |
| reward_a is +1 for every adversary within 1.5 of any Tello or RoboMaster | upstream_code | gym_marl_reconnaissance/envs/recon_arena.py:450-456 |
| reward_b sums 1/(the distance to the closest Tello or RoboMaster + 0.01) over the adversaries | upstream_code | gym_marl_reconnaissance/envs/recon_arena.py:467-472 |
| reward_c sums 1/(d^2+0.01) over the adversaries and 0.25/(d^2+0.01) for every Tello and RoboMaster over the closest adversary | upstream_code | gym_marl_reconnaissance/envs/recon_arena.py:485-502 |
| The episode ends when (ctrl_step_counter + 1) / ctrl_freq >= episode_length_sec | upstream_code | gym_marl_reconnaissance/envs/recon_arena.py:657-661 |
| step returns the observation, reward, done and an empty info dict, the legacy gym four-tuple | upstream_code | gym_marl_reconnaissance/envs/recon_arena.py:305-313 |
| A Tello starts at z=1.5 and a RoboMaster at z=0.5, each with x and y uniform in [0, edge/3] | upstream_code | gym_marl_reconnaissance/envs/recon_arena.py:847-876 |
| An adversary or neutral starts at z=0.5 with x and y uniform in [2*edge/3, edge] | upstream_code | gym_marl_reconnaissance/envs/recon_arena.py:893-922 |
| The render frame is 640 by 480 | upstream_code | gym_marl_reconnaissance/envs/recon_arena.py:159-160 |
| close disconnects from PyBullet | upstream_code | gym_marl_reconnaissance/envs/recon_arena.py:334-342 |

Limits: the driver declares none. The only bound is the environment's action space, which the bridge derives from
the fake's `MultiDiscrete` and the upstream `MultiDiscrete` (`recon_arena.py:353-359`): `action.values` has one
entry per learning agent, 0 to 2 in the default task_assignment setup (2 adversaries plus 1 neutral) and 0 to 4
with tracking. `ticks` is bounded 1 to 10000 by the bridge. The device is simulated (R0), so no limit is
`operator_required` and no site-limits overlay is needed.

Fidelity contract (`driver.py`, `fidelity = {...}`): the checked model is the package's kinematic fake, so the
level is F0; engine `gym_marl_reconnaissance:recon-arena-v0 (fake backend: kinematic stand-in for the PyBullet
simulation)`, determinism `seeded` with `seed_control` `parameter`, timestep 200 ms (the default 1/5 s control
period, `recon_arena.py:76` and `:133`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and
restore. The gaps list the missing rigid-body dynamics and contacts, the missing line-of-sight ray cast, the
single default setup, the missing render path, the different random generator and the fact that the fake was never
compared with the upstream environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step
or reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the
state stays readable.

Tags: multi-agent, reconnaissance, tello, robomaster, pybullet, reinforcement-learning, simulation, gymnasium
