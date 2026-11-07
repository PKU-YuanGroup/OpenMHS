# Facts and tags for gh.jbakams/slimebot-volleyball

Every fact cites its source at commit `0733b0ad1f9d1f62ba8b5717f69edf6b0cb1544a`. The same facts are written into
`driver.py` (`facts = [...]`); the reference files are generated from the driver, not from this page. Paths are
relative to the clone root, which keeps the `slimebot-volleyball/` repository subdirectory.

| fact | source | ref |
|---|---|---|
| Slimebot-volleyball is a 3D version of slime volleyball, implemented on top of slimevolleygym and using Webots as a simulator for visualization | vendor_doc | README.md:3 |
| The README calls the project a gym-like environment and says gym must be installed | vendor_doc | README.md:26 |
| The README says the same physics as slimevolleygym is used, so the environment can run in a CMD without Webots | vendor_doc | README.md:30 |
| The Webots Supervisor import is optional: outside Webots the import fails and WEBOTS_MODE is False | upstream_code | slimebot-volleyball/1_vs_1/environments/volleybot.py:24-29 |
| The game settings are TIMESTEP = 1/30 s, NUDGE = 0.1, FRICTION = 1.0, INIT_DELAY_FRAMES = 30, GRAVITY = -9.8*2*1.5 and MAXLIVES = 5 | upstream_code | slimebot-volleyball/1_vs_1/environments/volleybot.py:36-41 |
| The non-pixel action space is spaces.MultiBinary(5) and the observation space is a Box with 18 values bounded by +-np.finfo(np.float32).max | upstream_code | slimebot-volleyball/1_vs_1/environments/volleybot.py:744-752 |
| The episode limit is t_limit = 3000 | upstream_code | slimebot-volleyball/1_vs_1/environments/volleybot.py:732 |
| An episode is done when t reaches t_limit or when either agent's life is <= 0 | upstream_code | slimebot-volleyball/1_vs_1/environments/volleybot.py:823-829 |
| The observation is [agent x, y, z, vx, vy, vz, ball x, y, z, vx, vy, vz, opponent x, y, z, vx, vy, vz] divided by 10.0 | upstream_code | slimebot-volleyball/1_vs_1/environments/volleybot.py:369-374 |
| Action values 0 to 4 select forward, backward, jump, right and left when they are greater than 0 | upstream_code | slimebot-volleyball/1_vs_1/environments/volleybot.py:420-455 |
| The caller's action controls agent_right and the baseline policy controls agent_left unless otherAction is supplied | upstream_code | slimebot-volleyball/1_vs_1/environments/volleybot.py:805-815 |
| Game.reset starts the ball at x=0, y=width/4-1.5, z=0 with vx uniform in [-20, 20], vy uniform in [10, 25] and vz uniform in [-10, 10]; the agents start at -width/4 and width/4 at height 1.5 | upstream_code | slimebot-volleyball/1_vs_1/environments/volleybot.py:588-604 |
| A ball at the floor scores for the opposite side: checkEdges returns -1 when x <= 0 and 1 otherwise, and the game negates that for the right agent's reward | upstream_code | slimebot-volleyball/1_vs_1/environments/volleybot.py:225-235 |
| The README lists the observation shape as 18 for 1 vs 1 and 30 for 2 vs 2 | vendor_doc | README.md:39-40 |
| TeamVolleyBot uses the same MultiBinary(5) action space and a Box observation with 30 values | upstream_code | slimebot-volleyball/2_vs_2/environments/team_volleybot.py:967-977 |

## Limits

The driver declares no `Limit` object. The only bounds are derived by the family bridge from the environment's
spaces, which is why G4 has no driver limit to verify:

- `cap.world.step.v1` `action.values` is five binary values (0 or 1) from `spaces.MultiBinary(5)`
  (`volleybot.py:744`), and `ticks` is 1 to 10000 from `GymnasiumBridge` (`max_ticks`).
- `cap.world.reset.v1` `seed` is a non-negative integer and `options` is an object; the class schema carries the
  seed minimum.
- `cap.world.seed.v1` `seed` is a non-negative integer.

No bound is `operator_required`: the card is a simulated R0 device, and the operator cannot narrow a simulation's
action space in a meaningful way. There is no `site-limits.example.json`.

## Fidelity contract

`driver.py` declares the complete fidelity contract: engine `slimebot-volleyball:VolleyBotEnv (1_vs_1)`, level F1,
determinism `seeded` with `seed_control` `parameter`, timestep 1000/30 ms (`TIMESTEP = 1/30.`, `volleybot.py:36`),
`realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps disclose the reduced fake
physics, the Python random generator, the static baseline opponent, the ignored reset options, the absence of
rendering, pixels, Webots and 2-vs-2, the lack of any upstream comparison, and the simplified scoring.

## Safety

Simulated R0 device. The e-stop is the runtime's software latch: after it no step, reset or seed is accepted until
`mhs.safety.reset` clears the latch, and the environment state stays readable. There is no hardware stop path and no
safe-state action, because there is no hardware backend and no actuating physical resource.

## Tags

slimebot, volleyball, 3d, multiagent, reinforcement-learning, simulation, gymnasium
