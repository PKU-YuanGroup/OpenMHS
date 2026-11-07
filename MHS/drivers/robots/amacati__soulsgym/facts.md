# Facts and tags for gh.amacati/soulsgym

Every fact cites its source at commit `29c94d89ac8a47846c619019296d0ba55c6e80d5`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md) or `upstream_code` (`path/in/clone.py:LINE`).  The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The Iudex environment is registered as SoulsGymIudex-v0 with max_episode_steps=3000 and nondeterministic=True | upstream_code | soulsgym/__init__.py:51-54 |
| The Iudex observation is a Dict of 15 members: phase, player HP/SP and max HP/SP, boss HP and max HP, player/boss/camera poses, player/boss animations and durations, and lock_on | upstream_code | soulsgym/envs/darksouls3/iudex.py:97-115 |
| The Iudex action space is a Discrete space over the game's action table | upstream_code | soulsgym/envs/darksouls3/iudex.py:116 |
| The game action table maps 0-7 to walking, 8-15 to rolling, 16 and 17 to light and heavy attacks, 18 to parry and 19 to no action | upstream_code | soulsgym/core/data/darksouls3/actions.yaml:1-25 |
| SoulsEnv.step_size is 0.1 seconds between each step | upstream_code | soulsgym/envs/soulsenv.py:61 |
| SoulsEnv.step returns (observation, reward, terminated, False, info) and raises ResetNeeded when called after the episode terminated | upstream_code | soulsgym/envs/soulsenv.py:141-166 |
| The episode terminates when the player HP or the boss HP reaches zero | upstream_code | soulsgym/envs/soulsenv.py:413 |
| The Iudex reward is boss damage over boss max HP plus the player HP change over player max HP, with a +-0.1 terminal bonus and a small distance-to-centre shaping term | upstream_code | soulsgym/envs/darksouls3/iudex.py:388-400 |
| IudexEnv.reset accepts seed and options but does not use them, and it sets the player and boss to their fixed start poses | upstream_code | soulsgym/envs/darksouls3/iudex.py:193-224 |
| The README states that the environments are nondeterministic and cannot provide reproducible results by setting RNG seeds | vendor_doc | README.md:37 |
| The README requires the latest Dark Souls III running, on Windows or on Linux under Proton/Wine | vendor_doc | README.md:16-22 |
| SoulsEnv constructs a GameInput, a GameWindow and a game interface, and refuses to initialize when the player is not loaded into the game | upstream_code | soulsgym/envs/soulsenv.py:78-84 |
| SoulsEnv.close resumes the game, restores the altered game properties and kills the player to force a reload | upstream_code | soulsgym/envs/soulsenv.py:168-185 |
| SoulsEnv.render is a no-op because the game window must already be open | upstream_code | soulsgym/envs/soulsenv.py:229-234 |

Limits: the driver declares none.  The only bound is the action space, which the bridge derives from the fake's
`Discrete(20)` (`action.index` from 0 to 19, with no source and the ref
`action_space of the fake backend .fake:FakeIudexEnv`), and `ticks` (1 to `max_ticks`, 10000 by default).  The device
is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `soulsgym:IudexEnv`, level F0 (analytic; HP, poses and
ticks advance directly, no physics, collision, contact, actuator, sensor or noise model), determinism `seeded` with
`seed_control` `parameter` (the fake only; upstream says RNG seeds cannot make SoulsGym reproducible), timestep 100 ms
(`step_size = 0.1` s, `soulsenv.py:61`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and
restore, and gaps that say what is not modelled.

Safety: simulated R0 device.  The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: soulsgym, dark-souls-iii, boss-fight, reinforcement-learning, simulation, gymnasium
