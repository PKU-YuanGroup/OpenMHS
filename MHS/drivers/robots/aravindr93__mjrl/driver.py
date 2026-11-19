"""OpenMHS driver for gh.aravindr93/mjrl: the swimmer MJCF model (a MuJoCo family driver).

A ``MujocoDriver`` is configuration only: ``model_path`` names the model the card's entry environment loads and the
bridge derives the whole contract from it.  ``cap.world.step.v1`` takes ``{ticks, action: {ctrl: [...]}}``; each of
the four ``ctrl`` elements is checked against ``model.actuator_ctrlrange`` before it is written to ``data.ctrl``,
then ``mj_step`` runs ``ticks`` times.  ``cap.world.reset.v1`` restores the model defaults with ``mj_resetData`` +
``mj_forward``.  The world state is the bridge's integration state (``time_ms``, ``qpos``, ``qvel``, ``ctrl``,
``tick``, ``timestep_ms``, ``seed``, ``native_checkpoint``).  The device is simulated (R0): there is no hardware
backend and no operator-required limit.

The served model is ``mjrl/envs/assets/swimmer.xml``, the file the card's entry symbol
``mjrl.envs.swimmer:SwimmerEnv`` loads (``swimmer.py:8``), read from the read-only clone in place and never copied
into this package or imported.  The model declares a global default class with ``motor ctrllimited="true"
ctrlrange="-1 1"``; its four motors state no range of their own, so they inherit that interval and the bridge
derives ``action.ctrl`` from it.  ``<option timestep="0.005">`` gives a 5 ms lockstep step.

MuJoCo is not installed and cannot be installed where the gate runs (no network, no pip), so ``backends["fake"]``
is this package's stand-in ``mujoco`` module (fake.py).  It reads the same MJCF file for the joint layout, the
actuator count, the inherited control ranges and the option time step, but integrates a placeholder motion instead
of MuJoCo's physics; the fidelity ``gaps`` list every difference.  A backend name that ``backends`` does not list
(``sim``) imports the real ``mujoco`` module and loads the same file; that path was not run here.  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

MODEL = "mjrl/envs/assets/swimmer.xml"
SWIMMER = "mjrl/envs/swimmer.py"
ENV = "mjrl/envs/mujoco_env.py"
INIT = "mjrl/envs/__init__.py"
README = "README.md"
#: The card's entry environment model, relative to this package directory: the read-only clone at the pin.
MODEL_PATH = "../../../../robots/aravindr93/mjrl/" + MODEL


class MjrlSwimmer(MujocoDriver):
    device_id = "mjrl-swimmer"
    model_path = MODEL_PATH
    native = "mjrl.envs.swimmer:SwimmerEnv"
    backends = {"fake": FakeMujoco}
    display_name = "MJRL swimmer (MuJoCo model)"
    vendor, model = "Aravind Rajeswaran (mjrl)", "swimmer"
    tags = ["continuous-control", "gym", "mujoco", "reinforcement-learning", "simulation", "swimmer"]
    facts = [
        Fact("The README describes the package as implementations of various RL algorithms for continuous control "
             "tasks simulated with MuJoCo", source="vendor_doc", ref=f"{README}:3"),
        Fact("The README lists MuJoCo, python=3.7, gym>=0.13, mujoco-py>=2.0 and pytorch>=1.0 as the main "
             "dependencies", source="vendor_doc", ref=f"{README}:6"),
        Fact("setup.py describes the package as 'RL algorithms for environments in MuJoCo'", source="upstream_code",
             ref="setup.py:18"),
        Fact("mjrl_swimmer-v0 is registered with entry_point mjrl.envs:SwimmerEnv and max_episode_steps 500",
             source="upstream_code", ref=f"{INIT}:13-17"),
        Fact("SwimmerEnv subclasses mujoco_env.MujocoEnv and utils.EzPickle", source="upstream_code",
             ref=f"{SWIMMER}:6"),
        Fact("SwimmerEnv constructs MujocoEnv with the model name 'swimmer.xml' and frame_skip 5", source="upstream_code",
             ref=f"{SWIMMER}:8"),
        Fact("mujoco_env resolves a relative model path under its own assets directory and loads it with "
             "load_model_from_path, wrapped in MjSim", source="upstream_code", ref=f"{ENV}:17-25"),
        Fact("The action space is a Box whose low and high are the columns of model.actuator_ctrlrange",
             source="upstream_code", ref=f"{ENV}:56-59"),
        Fact("The environment step time is model.opt.timestep times frame_skip", source="upstream_code",
             ref=f"{ENV}:116-118"),
        Fact("do_simulation writes ctrl for every actuator and calls sim.step frame_skip times", source="upstream_code",
             ref=f"{ENV}:120-124"),
        Fact("SwimmerEnv.step returns reward -10.0 times the change of qpos[0] and done False", source="upstream_code",
             ref=f"{SWIMMER}:11-22"),
        Fact("SwimmerEnv.get_obs concatenates qpos[2:] and the whole qvel", source="upstream_code",
             ref=f"{SWIMMER}:24-28"),
        Fact("SwimmerEnv.reset_model draws qpos[2] uniformly from -pi to pi and keeps the other initial values",
             source="upstream_code", ref=f"{SWIMMER}:30-35"),
        Fact("The model root element is '<mujoco model=\"swimmer\">' and its compiler sets inertiafromgeom true and "
             "angle radian", source="upstream_code", ref=f"{MODEL}:4-5"),
        Fact("The global default class declares limited=true range -1.5 1.5 for joints and ctrllimited=true "
             "ctrlrange -1 1 for motors", source="upstream_code", ref=f"{MODEL}:6-8"),
        Fact("The option element sets timestep 0.005 s, viscosity 0.000894 and density 1000", source="upstream_code",
             ref=f"{MODEL}:16"),
        Fact("The torso body carries two slide joints and one hinge joint, and the tail is a chain of the hinge "
             "joints j1, j2, j3 and j4", source="upstream_code", ref=f"{MODEL}:29-52"),
        Fact("The actuator section declares four motor actuators, on joints j1 to j4 with gear 20, and states no "
             "ctrlrange on any of them", source="upstream_code", ref=f"{MODEL}:59-63"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch, and the integration state is kept and stays readable")
    #: The real MuJoCo engine contract, used by the implicit ``sim`` backend.  The bridge derives the timestep from
    #: the model and the lockstep clock; the values below are this package's.
    fidelity = {
        "engine": "mujoco:swimmer",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "none",
            "seed_control": "none",
            "notes": "The bridge reports determinism none: cap.world.reset.v1 restores the model defaults with "
                     "mj_resetData and takes no seed, and a native checkpoint does not establish hidden-state, "
                     "contact, plugin or RNG completeness.",
        },
        "timestep_ms": 5.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the upstream swimmer task layer is NOT COVERED: its step returns -10 times the change of qpos[0] plus "
            "a 12-value observation and done False (swimmer.py:11-28), its reset_model draws qpos[2] from -pi to pi "
            "(swimmer.py:30-35), and the gym registration adds max_episode_steps 500 (__init__.py:13-17); the "
            "MuJoCo bridge serves the model's control, integration state and reset instead of that task interface",
            "the model is a simulated swimming snake: the stand-in and the served contract have no water model "
            "beyond the option's viscosity and density, and no trajectory here was compared with the real engine",
            "no camera, rendering or sensor array is exposed: the bridge serves time, qpos, qvel, ctrl and the "
            "native checkpoint only",
            "MuJoCo itself was not importable where the gate ran, so the sim backend that imports mujoco was not "
            "run and no trajectory of this package was compared with it",
            "no physical device is modelled and nothing was validated against hardware",
        ],
    }
    #: The fake backend is this package's stand-in mujoco module, not MuJoCo: F0, no physics.
    fidelity_by_backend = {
        "fake": {
            "engine": "analytic:stand-in mujoco module (no physics)",
            "fidelity_level": "F0",
            "determinism": {
                "kind": "none",
                "seed_control": "none",
                "notes": "The stand-in integrates each motor's gear-scaled effort against a placeholder unit "
                         "inertia from the zero reset state; it has no seed input and is not MuJoCo physics.",
            },
            "gaps": [
                "the fake backend is a stand-in for the mujoco library, not MuJoCo: it reads the pinned MJCF for "
                "the joint layout, the actuator count, the inherited control ranges and the option time step, then "
                "integrates each actuated one-DOF joint's gear-scaled effort against a placeholder unit inertia; "
                "it computes no body inertia, constraint, contact, water or actuator dynamics, so no trajectory is a "
                "MuJoCo result",
                "the model's four motor actuators (gear 20) supply effort, not position targets; the stand-in "
                "uses that gear but omits fluid drag, coupling and joint-limit forces, so its motion differs "
                "from MuJoCo",
                "the stand-in loads no mesh, texture, camera or sensor and resolves no ground contact, even though "
                "the model declares a plane floor and a capsule body chain",
                "the stand-in has no mj_getState/mj_setState/mj_stateSize, so the bridge uses its basic checkpoint "
                "profile: time, qpos, qvel and ctrl are restored, not MuJoCo's full integration state",
                "MuJoCo itself was not importable where the gate ran, so the stand-in was not compared with the "
                "real engine and the sim backend that imports mujoco was not run",
                "the upstream swimmer task layer is NOT COVERED: the reward, the 12-value observation, the random "
                "qpos[2] reset and the 500-step time limit are not served; the driver serves the model step and "
                "reset only",
                "no physical device is modelled and nothing was validated against hardware",
            ],
        },
    }
