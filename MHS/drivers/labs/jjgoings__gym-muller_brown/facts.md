# Facts and tags for gh.jjgoings/gym-muller_brown

Every fact cites its source at commit `41467f4137008045c759a499cdcbb3aadf04f70c`: `upstream_code` is a
line of the clone at the pinned commit and `vendor_doc` is a text file of the clone. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| MullerBrownDiscrete-v0 is registered with env_kwargs m=5 and n=5, so the environment opens on a 5 by 5 grid by default | upstream_code | gym_muller_brown/__init__.py:3-7 |
| m and n are the number of grid points along the x and y axes | vendor_doc | README.md:42 |
| The grid extent is x from -1.5 to 1 and y from -0.5 to 2 | upstream_code | gym_muller_brown/envs/muller_brown_discrete.py:14 |
| The x and y grid coordinates are linspace over that extent with m and n points | upstream_code | gym_muller_brown/envs/muller_brown_discrete.py:15-16 |
| The observation space is MultiDiscrete([m, n]) and the action space is Discrete(5) | upstream_code | gym_muller_brown/envs/muller_brown_discrete.py:17-18 |
| Actions 0, 1, 2, 3 and 4 are up one grid point (+y), down (-y), left (-x), right (+x) and do nothing | vendor_doc | README.md:71-76 |
| The action table is {0: [0, 1], 1: [0, -1], 2: [-1, 0], 3: [1, 0], 4: [0, 0]} | upstream_code | gym_muller_brown/envs/muller_brown_discrete.py:19 |
| The potential sums four exponential terms with A [-200, -100, -170, 15], a [-1, -1, -6.5, 0.7], b [0, 0, 11, 0.6], c [-10, -10, -6.5, 0.7], x0 [1, 0, -0.5, -1] and y0 [0, 0.5, 1.5, 1] | upstream_code | gym_muller_brown/envs/muller_brown_discrete.py:75-80 |
| Each term is A[k] * exp(a[k]*(x-x0[k])**2 + b[k]*(x-x0[k])*(y-y0[k]) + c[k]*(y-y0[k])**2), summed over the four terms | upstream_code | gym_muller_brown/envs/muller_brown_discrete.py:82-87 |
| An on-grid step rewards old_energy - new_energy, the decrease in potential energy | upstream_code | gym_muller_brown/envs/muller_brown_discrete.py:103-110 |
| An off-grid move is penalized by a reward of -100 and leaves the agent at its current position | upstream_code | gym_muller_brown/envs/muller_brown_discrete.py:113-115 |
| step always returns done=False: the environment has no pre-set endpoint | upstream_code | gym_muller_brown/envs/muller_brown_discrete.py:105 |
| reset() draws the starting state from observation_space.sample() | upstream_code | gym_muller_brown/envs/muller_brown_discrete.py:117-120 |
| The README describes a discretized 2-D Muller-Brown potential in a gym-compatible format, a GridWorld variant with no pre-set endpoint | vendor_doc | README.md:7-10 |
| The README defines the potential over X = [-1.5, 1.0] and Y = [-0.5, 2.0] | vendor_doc | README.md:88 |

Limits: the driver declares none. The only action bound is the environment's action space, which the bridge derives
from the environment (`Discrete(5)`: `action.index` from 0 to 4, with the source `upstream_code` and the ref
`gym_muller_brown/envs/muller_brown_discrete.py:18`). `ticks` is bounded by the bridge's default `max_ticks` (1 to
10000). The device is simulated (R0), so no limit is `operator_required` and no site-limits overlay is needed.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:MullerBrownDiscrete-v0`, level F0 (an analytic
grid world: positions and state transitions are modelled directly, with no dynamics), determinism `seeded` with
`seed_control` `parameter`, timestep 0 ms (a tick is one grid move, not a physical interval), `realtime_factor` 0,
clock `lockstep`, reset `full`, no snapshot and restore. The gaps say what is not modelled, that the fake's seed
control is an extension of the upstream reset, and that the fake was not compared with the upstream environment.

Scope: this package serves the card's `MullerBrownDiscreteEnv` entry symbol only. The card's second entry symbol,
`MullerBrownContinuousEnv`, is a separate registered environment and is not modelled here.

Safety: simulated R0 device. The e-stop is the runtime's software latch (there is no native stop); after it no step
or reset is accepted until `mhs.safety.reset` clears the latch, and the grid state stays readable. No hardware
backend exists, so no physical stop is claimed.

Tags: muller-brown, potential-energy-surface, gridworld, reinforcement-learning, simulation, gymnasium
