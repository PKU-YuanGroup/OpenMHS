"""OpenMHS driver for gh.fdcl-gwu/gym-rotor: the Quad-v0 quadrotor environment (a Gymnasium family driver).

A GymnasiumDriver is configuration only: ``env_id`` names the environment and the bridge derives the contract from
the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action ``{"values": [four
normalized motor commands]}`` bounded by ``Box(-1.0, 1.0, shape=(4,))``; ``cap.world.reset.v1`` takes ``{seed,
options}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0): there is no hardware backend, no
e-stop path to a machine and no operator-required limit.

The gate neither installs nor imports the clone (``gym_rotor.envs:QuadEnv`` needs numpy, scipy and gymnasium, and
its module imports ``args_parse``), so the ``fake`` backend is the package's own pure Python quadrotor.  A backend
name that ``backends`` does not list (``sim``) would be served by ``gymnasium.make(env_id)`` (GymnasiumDriver
.open_native); that path needs the upstream package (Python, numpy, scipy, gymnasium, torch and vpython, setup.py:6-12)
and was not run here.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002):
every member of ``device.schema.json`` that applies to a simulator without a physical counterpart.  Every constant
and rule cites a line of the clone at the pinned commit 86a25517f401a5ca3a4f393e4f0c04104a04d3a1.  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

QUAD = "gym_rotor/envs/quad.py"
ARGS = "args_parse.py"


class QuadRotor(GymnasiumDriver):
    device_id = "quad"
    env_id = "Quad-v0"
    native = "gym_rotor.envs:QuadEnv"
    backends = {"fake": ".fake:FakeQuadEnv"}
    action_space_ref = f"{QUAD}:127-132"
    display_name = "FDCL-GWU gym-rotor Quad-v0 (quadrotor low-level control)"
    vendor, model = "FDCL-GWU", "Quad-v0"
    tags = ["quadrotor", "uav", "reinforcement-learning", "simulation", "gymnasium", "rotor"]
    facts = [
        Fact("Quad-v0 is registered with entry point gym_rotor.envs:QuadEnv and max_episode_steps=10000",
             source="upstream_code", ref="gym_rotor/__init__.py:3-7"),
        Fact("The action space is Box(-1.0, 1.0, shape=(4,)): four normalized motor commands",
             source="upstream_code", ref=f"{QUAD}:126-132"),
        Fact("A normalized action is linearly scaled from [-1, 1] to [min_force, max_force] and clipped to that "
             "range before it becomes the four motor thrusts", source="upstream_code", ref=f"{QUAD}:225-235"),
        Fact("The nominal quadrotor is mass 2.15 kg, arm length 0.23 m, inertia diag(0.022, 0.022, 0.035) kg m^2, "
             "torque-to-thrust coefficient 0.0135, thrust-to-weight coefficient 2.2 and standard gravity 9.81 m/s^2",
             source="upstream_code", ref=f"{QUAD}:27-33"),
        Fact("Each motor thrust is bounded by min_force 0.5 N and max_force = c_tw_nominal * hover_force, with "
             "hover_force = m * g / 4", source="upstream_code", ref=f"{QUAD}:36-42"),
        Fact("The simulation runs at 200 Hz, so one control step is dt = 1/200 s = 0.005 s",
             source="upstream_code", ref=f"{QUAD}:59-61"),
        Fact("The default integrator is solve_ivp",
             source="upstream_code", ref=f"{QUAD}:62"),
        Fact("The solve_ivp branch integrates over one dt per step with method DOP853",
             source="upstream_code", ref=f"{QUAD}:263-266"),
        Fact("The state limits are x_lim 1.0 m, v_lim 4.0 m/s, W_lim 2*pi rad/s and euler_lim 85 degrees",
             source="upstream_code", ref=f"{QUAD}:103-107"),
        Fact("The observation space is an 18-element Box: position x (3), velocity v (3), rotation matrix entries "
             "(9) and angular velocity W (3), with x bounded by +-x_lim, v by +-v_lim, the rotation entries by "
             "+-1 and W by +-W_lim", source="upstream_code", ref=f"{QUAD}:108-124"),
        Fact("The state vector is (x[0:3]; v[3:6]; R_vec[6:15]; W[15:18])",
             source="upstream_code", ref=f"{QUAD}:146"),
        Fact("QuadEnv.step returns (observation, reward, terminated, False, {})",
             source="upstream_code", ref=f"{QUAD}:168"),
        Fact("QuadEnv.reset takes env_type, seed and options",
             source="upstream_code", ref=f"{QUAD}:171-175"),
        Fact("A reset draws position, velocity and angular velocity uniformly within +-init_x, +-init_v and "
             "+-init_W and roll and pitch within +-init_R, with the attitude from rotation.from_euler('xyz')",
             source="upstream_code", ref=f"{QUAD}:184-204"),
        Fact("The initial yaw is sampled uniformly from [-pi, pi]",
             source="upstream_code", ref=f"{QUAD}:338-339"),
        Fact("For the default train env_type a reset uses init_x 0.6 m, init_v = v_lim*0.5 (2.0 m/s), init_R "
             "50 degrees and init_W = W_lim*0.5 (pi rad/s), except that 20% of resets use zero for all four",
             source="upstream_code", ref=f"{QUAD}:340-351"),
        Fact("The episode terminates when any position, velocity or angular velocity component reaches its limit, "
             "or the absolute roll or pitch reaches 85 degrees", source="upstream_code", ref=f"{QUAD}:301-318"),
        Fact("The equations of motion are x_dot = v, v_dot = g*e3 - f*R@e3/m, R_vec_dot = (R@hat(W)) flattened "
             "column-major and W_dot = J^-1 * (-hat(W)@J@W + M)", source="upstream_code", ref=f"{QUAD}:321-335"),
        Fact("The four motor thrusts map to total thrust and body moments through the matrix [1,1,1,1; "
             "0,-d,0,d; d,0,-d,0; -c_tf,c_tf,-c_tf,c_tf]", source="upstream_code", ref=f"{QUAD}:51-56"),
        Fact("The reward is reward_alive minus Cx*||x-xd||^2, Cv*||v-vd||^2, Cb1*|heading error| and "
             "CW*||W||^2", source="upstream_code", ref=f"{QUAD}:274-298"),
        Fact("The reward_alive bonus is 0 and the reward_crash penalty is -1",
             source="upstream_code", ref=f"{QUAD}:73-74"),
        Fact("The default reward coefficients are Cx 6.0, Cv 0.4, Cb1 6.0 and Cw12 0.6",
             source="upstream_code", ref=f"{ARGS}:23-31"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "gymnasium:Quad-v0",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake draws its initial state from random.Random(seed), so one seed and one action sequence "
                     "repeat a trajectory; upstream's reset uses numpy.random.uniform and random.random, which ignore "
                     "the seed passed to QuadEnv.reset, so the upstream environment does not repeat a trajectory for "
                     "a seed and the two do not agree",
        },
        "timestep_ms": 5.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake re-implements the rigid-body equations of motion in pure Python with a fixed-step RK4 "
            "integrator, not scipy solve_ivp/DOP853, and was never compared with the upstream environment: "
            "trajectories can differ",
            "no contact model: the quadrotor is a free rigid body and never lands, touches or collides with "
            "anything",
            "ideal actuator: the four motor thrusts follow the command instantly, with no motor lag, drag or noise; "
            "upstream's uniform domain randomization of mass, arm, inertia and coefficients is not modelled (the "
            "nominal parameters only)",
            "the fake uses Python floats and a local random.Random(seed); upstream uses numpy arrays, "
            "numpy.random.uniform and random.random, so the two do not repeat the same trajectory",
            "the MODUL/MONO reward interpolation and the integral/error observation terms of the wrappers are not "
            "modelled; the fake returns the raw scalar reward_wrapper value (upstream's step indexes that scalar "
            "for the default MODUL framework, which raises)",
            "no rendering (vpython) and no gymnasium wrapper: the fake does not add OrderEnforcing or TimeLimit, "
            "and it applies the registered 10000-step truncation itself",
            "the model was never validated against a physical quadrotor",
        ],
    }
