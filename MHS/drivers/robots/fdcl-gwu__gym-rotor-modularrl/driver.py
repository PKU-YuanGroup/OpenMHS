"""OpenMHS driver for gh.fdcl-gwu/gym-rotor-modularrl: the Quad-v0 quadrotor environment.

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives the
``cap.world.*`` contract from the environment's action and observation spaces.  ``cap.world.step.v1`` takes
``{ticks, action}`` with ``action.values`` the four normalized motor commands bounded by the ``Box(-1, 1, (4,))``
action space, ``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is a
simulation (R0): there is no hardware backend, no e-stop path to a machine and no operator-required limit.

The gate does not install or import gymnasium, numpy, scipy or the clone, so the ``fake`` backend is this package's
own pure Python implementation of the 18-element rigid-body model (fake.py).  A backend name that ``backends`` does
not list (``sim``) is served by ``gymnasium.make(env_id)`` (``GymnasiumDriver.open_native``); that path needs the
upstream package installed and imported so that ``gym_rotor/__init__.py:3-6`` has registered ``Quad-v0``, and it was
not run here.

The ``fidelity`` attribute is the contract of the model as deployed.  It is F1 because the fake integrates the
upstream's rigid-body equations of motion, without contacts, aerodynamics, actuator lag, sensor or noise models.
Every constant and rule cites a line of the clone at the pinned commit
3d70dfbe4ccee71bf30953cba3a1a810f2084494.  This package is model-authored and unreviewed: it is checked on the fake
backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

QUAD = "gym_rotor/envs/quad.py"
UTILS = "gym_rotor/envs/quad_utils.py"
REGISTER = "gym_rotor/__init__.py"
ARGS = "args_parse.py"


class QuadRotor(GymnasiumDriver):
    device_id = "gym-rotor-quad"
    env_id = "Quad-v0"
    native = "gym_rotor.envs:QuadEnv"
    backends = {"fake": ".fake:FakeQuadEnv"}
    action_space_ref = f"{QUAD}:127-132"
    display_name = "gym-rotor-modularrl Quad-v0 (quadrotor simulation)"
    vendor, model = "FDCL-GWU", "Quad-v0"
    device_kind, mode, risk = "world.sim", "simulated", "R0"
    max_ticks = 10000
    tags = ["quadrotor", "uav", "flight-dynamics", "reinforcement-learning", "simulation", "gymnasium"]
    fidelity_level = "F1"
    facts = [
        Fact("Quad-v0 is registered with entry point gym_rotor.envs:QuadEnv and max_episode_steps 10000",
             source="upstream_code", ref=f"{REGISTER}:3-6"),
        Fact("The state vector is 18 numbers: position (3), velocity (3), the rotation matrix in column-major "
             "order (9) and body angular velocity (3)", source="upstream_code", ref=f"{QUAD}:146"),
        Fact("The action space is Box(-1.0, 1.0, shape=(4,)): four normalized motor commands",
             source="upstream_code", ref=f"{QUAD}:126-132"),
        Fact("The observation space bounds position at +-1 m, velocity at +-4 m/s, the nine rotation-matrix "
             "elements at +-1 and angular velocity at +-2*pi rad/s", source="upstream_code",
             ref=f"{QUAD}:103-117"),
        Fact("The nominal quadrotor parameters are mass 2.15 kg, arm length 0.23 m, inertia "
             "diag(0.022, 0.022, 0.035) kg m2, torque-to-thrust coefficient 0.0135, thrust-to-weight coefficient "
             "2.2 and gravity 9.81", source="upstream_code", ref=f"{QUAD}:27-33"),
        Fact("The hover thrust of each motor is m*g/4, the minimum thrust is 0.5 N and the maximum is c_tw times "
             "the hover thrust", source="upstream_code", ref=f"{QUAD}:36-42"),
        Fact("A normalized action is scaled linearly from [-1, 1] to [min_force, max_force] and clipped to that "
             "range", source="upstream_code", ref=f"{QUAD}:225-229"),
        Fact("The simulation advances at 200 Hz, so one step is 0.005 s", source="upstream_code",
             ref=f"{QUAD}:59-61"),
        Fact("The equations of motion are x_dot = v, v_dot = g*e3 - f*R*e3/m, "
             "R_vec_dot = (R*hat(W)) in column-major order and W_dot = J^-1(-hat(W)*J*W + M)",
             source="upstream_code", ref=f"{QUAD}:323-337"),
        Fact("The default ODE integrator is solve_ivp with the DOP853 method", source="upstream_code",
             ref=f"{QUAD}:262-266"),
        Fact("A reset draws yaw uniformly in [-pi, pi]; in 80 percent of training resets the initial position, "
             "velocity, attitude and angular-velocity bounds are 0.6 m, 2.0 m/s, 50 degrees and pi rad/s, and in "
             "the other 20 percent they are zero", source="upstream_code", ref=f"{QUAD}:340-353"),
        Fact("The state limits are position 1.0 m, velocity 4.0 m/s, angular velocity 2*pi rad/s and Euler "
             "angle 85 degrees", source="upstream_code", ref=f"{QUAD}:103-107"),
        Fact("The episode terminates when any position, velocity or angular-velocity component reaches its limit, "
             "or when |roll| or |pitch| reaches 85 degrees", source="upstream_code", ref=f"{QUAD}:311-318"),
        Fact("The scalar reward is -Cx*||x-xd||^2 - Cv*||v-vd||^2 - Cb1*|e_b1| - CW*||W||^2 plus reward_alive",
             source="upstream_code", ref=f"{QUAD}:291-300"),
        Fact("The default reward coefficients are Cx 6.0, CIx 0.1, Cv 0.4, Cb1 6.0, CIb1 0.1 and Cw12 (used as "
             "CW) 0.6", source="upstream_code", ref=f"{ARGS}:21-29"),
        Fact("QuadEnv.step indexes the scalar returned by reward_wrapper and the boolean returned by done_wrapper, "
             "so it raises TypeError before returning under any framework value", source="upstream_code",
             ref=f"{QUAD}:153-168"),
        Fact("QuadEnv.reset returns the observation array alone, not an (observation, info) tuple",
             source="upstream_code", ref=f"{QUAD}:222"),
        Fact("The rotation matrix is stored in column-major order and state_decomposition reshapes it with "
             "order='F', re-orthonormalizing it when it is not in SO(3)", source="upstream_code",
             ref=f"{UTILS}:12-16"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    fidelity = {
        "engine": "gym_rotor:Quad-v0",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "cap.world.reset.v1 with a seed, or a seed set by cap.world.seed.v1, makes the fake repeat a "
                     "trajectory for the same actions; the fake draws with Python's random.Random and upstream "
                     "with numpy's global generator, so one seed gives different trajectories on the two",
        },
        "timestep_ms": 5.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "rigid-body equations of motion of a quadrotor with ideal motor forces: no contacts, aerodynamics, "
            "actuator lag, sensor or noise model, and the physical parameters are randomized only through the "
            "upstream's uniform domain randomization",
            "the fake integrates with explicit Euler at the 200 Hz step while the upstream default is "
            "scipy.integrate.solve_ivp with DOP853 (quad.py:62, :263-266), and re-orthonormalizes the stored "
            "attitude every step while upstream re-orthonormalizes only inside state_decomposition "
            "(quad_utils.py:123-142): trajectories can differ",
            "the fake draws initial states and domain-randomized parameters with Python's random.Random; "
            "upstream uses numpy's global generator, so a seed does not reproduce the upstream trajectory",
            "the upstream step indexes a scalar reward and a boolean done (quad.py:153-168), so it raises "
            "TypeError; the fake implements the intended five-value API and returns the scalar reward of "
            "reward_wrapper, not the CMP/DMP/NMP normalization that the upstream step attempts",
            "the modular wrappers (CoupledWrapper, DecoupledWrapper) are not served: this driver is the base "
            "Quad-v0 environment whose action is four motor thrusts",
            "the registered 10000-step TimeLimit is applied directly by the fake; the gymnasium wrapper is not "
            "present when the fake object is served, and there is no rendering",
            "no wall-clock pacing: realtime_factor 0 and clock lockstep, so only step calls advance simulated "
            "time by the 5 ms integration step",
            "snapshot and restore are not offered: the environment exposes get_current_state but no set_state",
        ],
    }
