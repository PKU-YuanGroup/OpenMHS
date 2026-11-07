"""Fake backend of the pc-gym Gymnasium driver: a pure Python stand-in for ``pcgym.pcgym:make_env``.

Why a fake: pc-gym needs Python 3.11 or newer and numpy, casadi, jax, equinox, diffrax, do-mpc and gymnasium
(requirements.txt:1-9), and package code never imports the clone; the acceptance gate runs without them.  This module
re-implements the served configuration of the README quick start (README.md:23-45): the CSTR model of
``model_classes.py:24-63`` with its default parameters, integrated over ``dt = tsim / N`` (``pcgym.py:104``), with the
normalised action and observation spaces of ``pcgym.py:69-86`` and the setpoint reward of ``pcgym.py:544-560``.  The
public members are the ones ``make_env`` has (``reset``, ``step``; gate G7) and the two duck-typed space attributes the
bridge reads (``action_space``, ``observation_space``).

What this is not: the upstream environment.  Differences, all listed in the fidelity ``gaps`` of the driver:

* upstream integrates with casadi (or jax) through its integration engine (``pcgym.py:436-440``); this module uses one
  explicit RK4 step with 0.01 s substeps per environment step, so a trajectory differs from a real pc-gym run;
* upstream returns numpy arrays and has the full model registry (``pcgym.py:146-166``); this module serves only the
  CSTR quick start and returns Python floats and lists;
* there is no rendering, no constraint penalty, no noise, no uncertainty and no custom reward.

Nothing here talks to a device.
"""

import math

# pcgym/model_classes.py:25-34 (the cstr class defaults)
Q = 100.0
V = 100.0
RHO = 1000.0
C_P = 0.239
DELTA_HR = -5e4
EA_OVER_R = 8750.0
K0 = 7.2e10
UA = 5e4
TI = 350.0
CAF = 1.0

# README.md:23-45 (the quick-start env_params); dt from pcgym/pcgym.py:104
NSTEPS = 100
TSIM = 25.0
DT = TSIM / NSTEPS
ACTION_LOW, ACTION_HIGH = 295.0, 302.0
OBSERVATION_LOW = [0.7, 300.0, 0.8]
OBSERVATION_HIGH = [1.0, 350.0, 0.9]
X0 = [0.8, 330.0, 0.8]
# README.md:27: 0.85 for the first 50 steps and 0.9 for the last 50
SETPOINTS = [0.85] * int(NSTEPS / 2) + [0.9] * int(NSTEPS / 2)


class Box:
    """Duck-typed one-dimensional ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


def _balances(ca, temperature, tc):
    """``cstr.__call__`` (model_classes.py:46-63): the Ca and T derivatives for a jacket temperature tc."""
    rate = K0 * math.exp(-EA_OVER_R / temperature) * ca
    dcadt = Q / V * (CAF - ca) - rate
    dtdt = (Q / V * (TI - temperature)
            + (-DELTA_HR) * rate / (RHO * C_P)
            + UA * (tc - temperature) / (RHO * C_P * V))
    return dcadt, dtdt


def _advance(ca, temperature, tc, dt):
    """One environment step of the ODE, RK4 with 0.01 s substeps (a stand-in for the casadi engine)."""
    substeps = max(1, int(round(dt / 0.01)))
    h = dt / substeps
    for _ in range(substeps):
        k1 = _balances(ca, temperature, tc)
        k2 = _balances(ca + h * k1[0] / 2, temperature + h * k1[1] / 2, tc)
        k3 = _balances(ca + h * k2[0] / 2, temperature + h * k2[1] / 2, tc)
        k4 = _balances(ca + h * k3[0], temperature + h * k3[1], tc)
        ca += h * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0]) / 6
        temperature += h * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1]) / 6
    return ca, temperature


def _normalise(state):
    """``2 * (obs - low) / (high - low) - 1`` (pcgym/pcgym.py:490-498)."""
    return [2 * (state[i] - OBSERVATION_LOW[i]) / (OBSERVATION_HIGH[i] - OBSERVATION_LOW[i]) - 1
            for i in range(len(state))]


class FakePcGymEnv:
    """The CSTR quick start without numpy and without the pc-gym package: ``reset`` and ``step``."""

    def __init__(self, **options):
        if options:
            raise ValueError(f"the fake pc-gym environment takes no options, got {sorted(options)}")
        self.env_params = {"N": NSTEPS, "tsim": TSIM, "model": "cstr"}     # pcgym.py:45
        self.N = NSTEPS                                                    # pcgym.py:100
        self.tsim = TSIM                                                   # pcgym.py:101
        self.x0 = list(X0)                                                 # pcgym.py:102
        self.dt = DT                                                       # pcgym.py:104
        self.done = False                                                  # pcgym.py:105
        self.normalise_a = True                                            # pcgym.py:61
        self.normalise_o = True                                            # pcgym.py:62
        self.action_space = Box([-1.0], [1.0])                             # pcgym.py:70-72
        self.observation_space_base = Box(OBSERVATION_LOW, OBSERVATION_HIGH)   # pcgym.py:80
        self.observation_space = Box([-1.0] * 3, [1.0] * 3)                # pcgym.py:82-84
        self.SP = {"Ca": list(SETPOINTS)}                                  # pcgym.py:90
        self.Nx = 3                                                        # pcgym.py:179-183
        self.Nx_oracle = 2                                                 # pcgym.py:181
        self.Nu = 1                                                        # pcgym.py:183
        self.state = list(X0)                                              # pcgym.py:325
        self.obs = list(self.state)                                        # pcgym.py:326
        self.t = 0                                                         # pcgym.py:323
        self.info = {}                                                     # pcgym.py:113

    def reset(self, seed=0, **kwargs):
        """``reset`` (pcgym.py:274-359): restore x0, normalise the observation and return (obs, info)."""
        self.t = 0                                                         # pcgym.py:287
        self.state = list(self.x0)
        self.obs = list(self.state)                                        # pcgym.py:325-326
        self.done = False                                                  # pcgym.py:353
        self.info = {}
        observation = _normalise(self.obs)                                 # pcgym.py:336-343
        self.info["obs"] = list(observation)
        self.info["r_init"] = 0                                            # pcgym.py:358
        return observation, self.info

    def step(self, action):
        """``step`` (pcgym.py:361-508): denormalise, integrate one dt, update the setpoint, reward."""
        if self.t >= self.N:
            raise RuntimeError("the episode is over; call reset()")
        value = float(action[0] if isinstance(action, (list, tuple)) else action)
        if self.normalise_a:                                               # pcgym.py:382-385
            tc = (value + 1) * (ACTION_HIGH - ACTION_LOW) / 2 + ACTION_LOW
        else:
            tc = value
        ca, temperature = _advance(self.state[0], self.state[1], tc, self.dt)   # pcgym.py:436-440
        self.state = [ca, temperature, self.state[2]]
        if self.SP is not None:                                            # pcgym.py:442-449
            self.state[self.Nx_oracle:self.Nx_oracle + len(self.SP)] = [self.SP["Ca"][self.t]]
        self.t += 1                                                        # pcgym.py:452
        if self.t == self.N - 1:                                           # pcgym.py:459-460
            self.done = True
        self.obs = list(self.state)                                        # pcgym.py:463
        # SP_reward_fn (pcgym.py:544-560) runs after the increment and uses self.SP['Ca'][self.t]
        reward = -((self.state[0] - self.SP["Ca"][self.t]) ** 2)
        observation = _normalise(self.obs)                                 # pcgym.py:490-498
        self.info["obs"] = list(observation)
        return observation, reward, self.done, False, self.info            # pcgym.py:508
