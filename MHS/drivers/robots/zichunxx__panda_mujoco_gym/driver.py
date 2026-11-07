"""OpenMHS driver for gh.zichunxx/panda_mujoco_gym: the Franka Panda pick-and-place MuJoCo scene as a simulated world.

A MujocoDriver (configuration only) over the scene the pick-and-place environment loads,
``panda_mujoco_gym/assets/pick_and_place.xml`` (panda_mujoco_gym/envs/pick_and_place.py:4), which includes the Panda
robot model ``panda_mocap.xml`` (model.xml:8).  The package carries both files: ``model.xml`` is a copy of the scene
and ``panda_mocap.xml`` the robot file its include names, so a MuJoCo load of ``model.xml`` finds it beside it.

The bridge serves ``cap.world.step.v1`` and ``cap.world.reset.v1`` on the model.  A step takes ``ticks`` and
``action.ctrl``, one value per actuator, bounded per actuator by the model's ``actuator_ctrlrange`` -- the control range
the environment itself reads (panda_mujoco_gym/envs/panda_env.py:83-84).  The model has 9 actuators, 16 generalized
coordinates and 15 degrees of freedom (panda_mujoco_gym/envs/panda_env.py:75-81).

The card names the upstream simulator as the mock path.  The MuJoCo engine is not installed where the gate runs, so the
fake backend is a stand-in ``mujoco`` module (``fake.py``): it reads the integration step, the dimension counts and the
actuator ctrlranges of the carried model and advances a minimal state.  It does not reproduce the engine's dynamics,
and the fidelity ``gaps`` below state every difference, including that the meshes the model references are not carried.

Every Fact cites a line of the clone at the pinned commit (e9881d993234875ee1d55d717176bf7999bdb583).  This package is
model-authored and unreviewed: it is checked on the fake backend only, and nothing here ran the MuJoCo engine.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import fake_mujoco


class FrankaPanda(MujocoDriver):
    device_id = "franka-panda"
    model_path = "model.xml"
    backends = {"fake": fake_mujoco}
    display_name = "Franka Panda pick-and-place scene (panda_mujoco_gym)"
    vendor, model = "zichunxx", "Franka Panda pick-and-place MuJoCo scene (pick_and_place.xml)"
    tags = ["mujoco", "franka", "panda", "manipulation", "pick-and-place", "simulation"]
    facts = [
        Fact("The repository provides three manipulation tasks - push, slide and pick-and-place - for the Franka "
             "Emika Panda arm, implemented on the MuJoCo physics engine", source="vendor_doc", ref="README.md:3"),
        Fact("The pick-and-place environment loads its scene from assets/pick_and_place.xml", source="upstream_code",
             ref="panda_mujoco_gym/envs/pick_and_place.py:4"),
        Fact("The scene includes the robot model panda_mocap.xml from the same directory", source="upstream_code", ref="panda_mujoco_gym/assets/pick_and_place.xml:8"),
        Fact("The scene sets the integrator to Euler, noslip_iterations to 3, the timestep to 0.002 s and the cone "
             "to pyramidal", source="upstream_code", ref="panda_mujoco_gym/assets/pick_and_place.xml:4"),
        Fact("The scene compiles with the radian angle unit, the ./meshes/ mesh directory and automatic limits",
             source="upstream_code", ref="panda_mujoco_gym/assets/pick_and_place.xml:2"),
        Fact("The scene adds a free object body at (0.4, 0, 0.2) whose box geom has mass 0.1 and size 0.02 m, and a "
             "target site at the same position", source="upstream_code", ref="panda_mujoco_gym/assets/pick_and_place.xml:30-38"),
        Fact("The robot model declares the seven arm joints joint1 to joint7", source="upstream_code",
             ref="panda_mujoco_gym/assets/panda_mocap.xml:142-204"),
        Fact("The default class panda gives every arm joint armature 0.1, damping 1, axis 0 0 1 and the range -2.8973 "
             "to 2.8973 rad, and its actuators the ctrlrange -2.8973 to 2.8973 and forcerange -87 to 87",
             source="upstream_code", ref="panda_mujoco_gym/assets/panda_mocap.xml:5-8"),
        Fact("The default class finger gives the gripper finger joints a slide joint on axis 0 1 0 with the range 0 to "
             "0.04 m", source="upstream_code", ref="panda_mujoco_gym/assets/panda_mocap.xml:7-9"),
        Fact("The two actuator sections declare seven general actuators for the arm joints and two for the gripper "
             "fingers, and the finger actuators have the ctrlrange 0 to 0.04", source="upstream_code",
             ref="panda_mujoco_gym/assets/panda_mocap.xml:269-283"),
        Fact("The robot model welds the mocap body panda_mocap to the end-effector body ee_center_body, so the end "
             "effector is driven by a mocap pose and not by joint position commands", source="upstream_code",
             ref="panda_mujoco_gym/assets/panda_mocap.xml:266"),
        Fact("The environment states that the model has 9 actuators (7 arm and 2 gripper joints), 16 generalized "
             "coordinates (9 arm and gripper plus the 7 of the object's free joint) and 15 degrees of freedom",
             source="upstream_code", ref="panda_mujoco_gym/envs/panda_env.py:75-81"),
        Fact("The environment takes its control range from the model's actuator_ctrlrange", source="upstream_code",
             ref="panda_mujoco_gym/envs/panda_env.py:83-84"),
        Fact("The environment action is three Cartesian displacements plus a gripper command unless the gripper is "
             "blocked", source="upstream_code", ref="panda_mujoco_gym/envs/panda_env.py:35-37"),
        Fact("The pick-and-place environment runs 25 physics substeps per step, uses the distance threshold 0.05 and "
             "samples the object and the goal in a 0.3 m range with a 0.2 m height range", source="upstream_code",
             ref="panda_mujoco_gym/envs/pick_and_place.py:13-23"),
        Fact("The package registers the three tasks, each with a sparse and a dense reward, with 50 steps per "
             "episode", source="upstream_code", ref="panda_mujoco_gym/__init__.py:6-16"),
        Fact("A step clips the action to the action-space bounds and runs ten physics steps of n_substeps each",
             source="upstream_code", ref="panda_mujoco_gym/envs/panda_env.py:121-133"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop no step or reset is accepted until "
                  "mhs.safety.reset clears the latch, and the world state stays readable")
    #: The fidelity contract as deployed on the fake backend.  It states every difference from the MuJoCo engine and
    #: from the upstream environment rather than hiding them behind the derived defaults.
    fidelity = {
        "engine": "mujoco",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "the carried model and a fixed control sequence are deterministic in the MuJoCo engine, but a "
                     "real engine run was never made here and the bridge's seed is only recorded; the stand-in state "
                     "is deterministic",
        },
        "timestep_ms": 2.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the fake backend is a stand-in mujoco module, not the MuJoCo engine: it parses the integration step, "
            "the joint counts and the actuator ctrlranges of model.xml and panda_mocap.xml and advances time (every "
            "qpos follows its qvel, which stays zero); it computes no equations of motion, contacts, mocap welds or "
            "actuator dynamics, so a ctrl vector changes nothing but data.ctrl",
            "the package carries the two XML files only (model.xml and panda_mocap.xml); the 33 MB of meshes the "
            "scene references through meshdir ./meshes/ are not carried, so a real MuJoCo load needs that assets "
            "directory beside model.xml",
            "the clone's environments are MuJoCoRobotEnv subclasses of a reinforcement-learning library with "
            "observations, rewards, a mocap-driven end effector and goal sampling (panda_mujoco_gym/envs/panda_env.py); "
            "this package serves the raw model, not those environments, and that library is not carried",
            "the model drives the end effector through the mocap weld; a ctrl vector moves the arm joints, which "
            "the environment's own action mode does not use",
            "snapshot and restore use the bridge's copied time/qpos/qvel/ctrl fallback, not mjSTATE_INTEGRATION",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by the model's timestep only",
            "the model was never validated against a physical Franka arm",
        ],
    }
