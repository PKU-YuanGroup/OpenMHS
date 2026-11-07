"""OpenMHS driver for gh.maximilianb2/pc-gym: the CSTR process-control environment (a Gymnasium family driver).

``pcgym.pcgym.make_env`` is a Gymnasium environment class (``gymnasium.Env``): ``cap.world.step.v1`` takes
``{ticks, action}``, ``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The
bridge derives the action and observation spaces from the environment, so this package serves the configuration of the
README quick start: a CSTR with 100 steps over 25 simulated seconds, a normalised jacket-temperature action in
[-1, 1] and a three-value normalised observation [Ca, T, Ca_SP].  The device is simulated (R0): there is no hardware
backend, no e-stop path to a machine and no operator-required limit.

The card names ``GymnasiumDriver``, and the family fits, with one difference from ``gymnasium.make``: pc-gym registers
no Gymnasium id and ``make_env`` requires an ``env_params`` dictionary (README.md:34-45), so the family's ``env_id``
path cannot construct the upstream environment.  ``make_bridge`` therefore passes the bridge an environment factory
(``pcgym.pcgym:make_env`` with the quick-start ``env_params``); the ``fake`` backend still passes the package's own
environment object, and no gate run opens pc-gym.  The upstream needs Python 3.11 or newer and numpy, casadi, jax,
equinox, diffrax, do-mpc and gymnasium (requirements.txt), which the gate does not install.

The ``fidelity`` attribute is the contract of the model as deployed (spec 05-fidelity FID-002): the CSTR balances of
``model_classes.py:46-63`` integrated at ``dt = tsim / N`` (``pcgym.py:104``).  Every fact cites a line of the clone at
the pinned commit (fbfb36bf84b494cd157cff88292e1fd1b864cee5).  This package is model-authored and unreviewed: it is
checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

PCGYM = "src/pcgym/pcgym.py"
MODELS = "src/pcgym/model_classes.py"
DOCS_CSTR = "docs/env/cstr.md"


def _quickstart_env_params():
    """The ``env_params`` of the README quick start (README.md:23-45), in the arrays ``make_env`` expects."""
    import numpy as np

    nsteps, tsim = 100, 25
    return {
        "N": nsteps,
        "tsim": tsim,
        "SP": {"Ca": [0.85 for _ in range(int(nsteps / 2))] + [0.9 for _ in range(int(nsteps / 2))]},
        "o_space": {"low": np.array([0.7, 300, 0.8]), "high": np.array([1, 350, 0.9])},
        "a_space": {"low": np.array([295]), "high": np.array([302])},
        "x0": np.array([0.8, 330, 0.8]),
        "model": "cstr",
    }


class PcGymCSTR(GymnasiumDriver):
    device_id = "pcgym-cstr"
    native = "pcgym.pcgym:make_env"
    backends = {"fake": ".fake:FakePcGymEnv"}
    action_space_ref = f"{PCGYM}:72"
    display_name = "pc-gym CSTR process-control environment"
    vendor, model = "maximilianb2", "pc-gym (cstr)"
    tags = ["cstr", "process-control", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("make_env is a Gymnasium environment class: the module imports gymnasium as gym and gymnasium's "
             "spaces, and the class subclasses gym.Env", source="upstream_code", ref=f"{PCGYM}:3-5"),
        Fact("Users create the environment with make_env(env_params), where env_params is a dictionary",
             source="upstream_code", ref=f"{PCGYM}:32"),
        Fact("env_params['model'] selects the process model by name, and the mapping binds 'cstr' to the cstr "
             "class", source="upstream_code", ref=f"{PCGYM}:146-147"),
        Fact("The cstr model's states are Ca and T and its single input is Tc", source="upstream_code",
             ref=f"{MODELS}:41-44"),
        Fact("The CSTR balances are dcadt = q/V * (Caf - ca) - k0 * exp(-EA/R/T) * ca and dTdt = q/V * (Ti - T) - "
             "deltaHr * rA / (rho * C) + UA * (Tc - T) / (rho * C * V)", source="upstream_code",
             ref=f"{MODELS}:46-63"),
        Fact("The cstr default parameters are q=100, V=100, rho=1000, C=0.239, deltaHr=-5e4, EA_over_R=8750, "
             "k0=7.2e10, UA=5e4, Ti=350 and Caf=1", source="upstream_code", ref=f"{MODELS}:25-34"),
        Fact("normalise_a and normalise_o default to True", source="upstream_code", ref=f"{PCGYM}:61-62"),
        Fact("With normalisation the action space is Box(low=-1, high=1) with a dimension per a_space input (one "
             "for the CSTR)", source="upstream_code", ref=f"{PCGYM}:70-72"),
        Fact("With normalisation the observation space is Box(low=-1, high=1) with a dimension per o_space bound "
             "(three in the README configuration)", source="upstream_code", ref=f"{PCGYM}:82-84"),
        Fact("The simulation timestep is dt = tsim / N", source="upstream_code", ref=f"{PCGYM}:104"),
        Fact("The README quick-start configuration sets nsteps=100 time steps over T=25 simulation seconds, a "
             "jacket-temperature action range of 295 to 302, observation bounds [0.7, 300, 0.8] to [1, 350, 0.9], "
             "initial state [0.8, 330, 0.8] and model 'cstr'", source="vendor_doc", ref="README.md:23-45"),
        Fact("The README quick-start setpoint is 0.85 for the first 50 steps and 0.9 for the last 50",
             source="vendor_doc", ref="README.md:26-27"),
        Fact("step denormalises the action to the a_space range as (action + 1) * (high - low) / 2 + low",
             source="upstream_code", ref=f"{PCGYM}:382-385"),
        Fact("step advances the model's ODE with the integration engine: casadi_step when integration_method is "
             "casadi and jax_step when it is jax", source="upstream_code", ref=f"{PCGYM}:436-440"),
        Fact("step writes the setpoint value for each SP key at index t into the state after each transition",
             source="upstream_code", ref=f"{PCGYM}:442-449"),
        Fact("step sets done when t reaches N-1", source="upstream_code", ref=f"{PCGYM}:459-460"),
        Fact("step returns (observation, reward, done, False, info)", source="upstream_code", ref=f"{PCGYM}:508"),
        Fact("With SP set and no custom reward the reward is -sum over the SP states of (state - setpoint)^2 "
             "scaled by r_scale", source="upstream_code", ref=f"{PCGYM}:544-560"),
        Fact("The CSTR documentation gives the observation space bounds as [[0.7,1],[300,350],[0.8,0.9]]",
             source="vendor_doc", ref=f"{DOCS_CSTR}:40-42"),
        Fact("The CSTR documentation describes the action as a ContinuousBox of [290,302], the jacket temperature "
             "in kelvin", source="vendor_doc", ref=f"{DOCS_CSTR}:49-50"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "pcgym:cstr",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the served CSTR configuration is deterministic: reset restores the fixed x0 of the quick "
                     "start and every trajectory follows the same ODE balances, so the same actions give the same "
                     "state hashes; reset accepts a seed and the bridge echoes it, but the configured CSTR has no "
                     "random initial state, noise or uncertainty, so the seed does not change the trajectory",
        },
        "timestep_ms": 250.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "a lumped continuous-stirred-tank model (two ODE balances for Ca and T) with an idealised cooling "
            "jacket; no contacts, no actuator dynamics, no sensor model and no noise model, and the reaction "
            "parameters are the class defaults of model_classes.py:25-34",
            "the served configuration is only the README quick start: N=100 steps over tsim=25 s gives the 0.25 s "
            "timestep, the 295-302 K jacket range is denormalised from the action space and the observation "
            "bounds are the README o_space; another model, plant or step count is a different configuration",
            "the fake backend integrates one explicit RK4 step with 0.01 s substeps per environment step; upstream "
            "uses casadi (or jax) through its integration engine, so trajectories and the reward stream differ from "
            "a real pc-gym run, and pc-gym was not importable where the gate ran",
            "the fake returns Python floats and lists; upstream returns numpy arrays",
            "snapshot and restore are not offered: make_env exposes no get_state or set_state",
        ],
    }

    def make_bridge(self, native):
        """Build the family bridge; pc-gym registers no id, so the sim path uses a make_env factory."""
        from mhs.bridge.gymnasium import GymnasiumBridge

        cls = type(self)
        spec = origin = None
        if native is None:
            spec = {"module": "pcgym.pcgym", "attr": "make_env",
                    "kwargs": {"env_params": _quickstart_env_params()}}
        else:
            origin = f"the {self.backend} backend {dict(cls.backends).get(self.backend)}"
        return GymnasiumBridge(env=native, env_id=None, env_spec=spec, seed=cls.seed,
                               device_id=self.device_id, autoreset=cls.autoreset, max_ticks=cls.max_ticks,
                               env_origin=origin, action_space_ref=cls.action_space_ref)
