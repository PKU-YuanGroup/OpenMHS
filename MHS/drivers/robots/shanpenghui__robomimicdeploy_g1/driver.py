"""OpenMHS driver for gh.shanpenghui/robomimicdeploy_g1: the Unitree G1 29-DOF MJCF scene (a MuJoCo family driver).

A ``MujocoDriver`` is configuration only: ``model_path`` names the card's ``models[0]`` scene
(``g1_description/scene.xml``), which includes ``g1_29dof_rev_1_0.xml``, and the bridge derives the contract from the
model it loads.  ``cap.world.step.v1`` takes ``{ticks, action: {ctrl: [...]}}``; ``ctrl`` is written to ``data.ctrl`` and
``mj_step`` runs ``ticks`` times.  ``cap.world.reset.v1`` restores the model defaults with ``mj_resetData`` plus
``mj_forward``.  The world state is the bridge's integration state (``time_ms``, ``qpos``, ``qvel``, ``ctrl``,
``tick``, ``timestep_ms``, ``seed``).

The device is simulated (R0): there is no hardware backend and no e-stop path to a machine.  The model's motors
declare no ``ctrlrange`` (``g1_29dof_rev_1_0.xml:247-277``): the model states no per-actuator control
interval, so the bridge publishes ``action.ctrl`` as ``operator_required``: the endpoint refuses a step that sets
it (``MHS.SAFETY.LIMITS_UNSET``, before any native call) until the site's ``site-limits.json`` bounds it;
``site-limits.example.json`` is operator example data, not a bound of the model.  The driver declares no control limit of its own: the upstream application's ``tau_limit``
clip (``deploy_mujoco/config/mujoco.yaml:5-9``, ``deploy_mujoco/deploy_mujoco.py:86-87``) is a bound of that
joystick/policy loop, not of the MJCF model, and it is not presented here as a device bound.

The gate cannot install MuJoCo where it runs (there is no network and no pip), so ``backends["fake"]`` is this
package's stand-in ``mujoco`` module (fake.py).  It reads the scene and its include for the joint count, the actuator
count and the 0.002 s timestep, but its integration is a placeholder, not MuJoCo's physics; the fidelity ``gaps`` say
so.  A backend name that ``backends`` does not list (``sim``) imports the real ``mujoco`` module and loads the same
scene; that path was not run here.  This package is model-authored and unreviewed: it is checked on the fake backend
only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

SCENE = "g1_description/scene.xml"
MODEL = "g1_description/g1_29dof_rev_1_0.xml"
README = "README.md"
SIM = "deploy_mujoco/deploy_mujoco.py"
CONFIG = "deploy_mujoco/config/mujoco.yaml"
#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/shanpenghui/robomimicdeploy_g1/" + SCENE


class G1(MujocoDriver):
    device_id = "g1-29dof"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "Unitree G1 29-DOF (MuJoCo simulation)"
    vendor, model = "Unitree Robotics", "G1 29-DOF (g1_29dof_rev_1_0)"
    tags = ["g1", "humanoid", "mujoco", "robot", "simulation", "unitree"]
    facts = [
        Fact("The default MuJoCo configuration runs the scene g1_description/scene.xml", source="upstream_code",
             ref=f"{CONFIG}:1"),
        Fact("The scene includes the robot model g1_29dof_rev_1_0.xml", source="upstream_code", ref=f"{SCENE}:1-2"),
        Fact("The robot model uses radians and resolves its meshes from meshes/", source="upstream_code",
             ref=f"{MODEL}:2"),
        Fact("The robot model sets the integration step to 0.002 s and the implicit integrator", source="upstream_code",
             ref=f"{MODEL}:10-11"),
        Fact("The robot model declares a free floating-base joint named floating_base_joint", source="upstream_code",
             ref=f"{MODEL}:54"),
        Fact("The floating base starts at the pelvis body pose (0 0 0.793)", source="upstream_code",
             ref=f"{MODEL}:52"),
        Fact("The actuator block has 29 motor elements, one for each actuated joint, and none states a ctrlrange",
             source="upstream_code", ref=f"{MODEL}:247-277"),
        Fact("The left hip pitch joint has range -2.5307 to 2.8798 rad and actuatorfrcrange -88 to 88",
             source="upstream_code", ref=f"{MODEL}:61"),
        Fact("The left ankle roll joint has range -0.2618 to 0.2618 rad and actuatorfrcrange -50 to 50",
             source="upstream_code", ref=f"{MODEL}:86"),
        Fact("The left wrist pitch joint has range -1.61443 to 1.61443 rad and actuatorfrcrange -5 to 5",
             source="upstream_code", ref=f"{MODEL}:182"),
        Fact("The simulation loop loads the scene with mujoco.MjModel.from_xml_path and creates the MjData",
             source="upstream_code", ref=f"{SIM}:33-34"),
        Fact("The simulation loop overrides the model timestep with cfg.simulation_dt", source="upstream_code",
             ref=f"{SIM}:35"),
        Fact("The configuration sets simulation_dt to 0.003 s and control_decimation to 7", source="upstream_code",
             ref=f"{CONFIG}:3-4"),
        Fact("The configuration's tau_limit array lists the per-actuator torque magnitudes: 88, 139 and 50 for the "
             "leg motors, 88, 50 and 50 for the waist, 25 for the shoulder and elbow motors and 5 for the wrist "
             "motors", source="upstream_code", ref=f"{CONFIG}:5-9"),
        Fact("The simulation loop clips the computed torque with np.clip(tau, -tau_limit, tau_limit) before writing "
             "it to d.ctrl", source="upstream_code", ref=f"{SIM}:86-87"),
        Fact("The simulation loop calls mujoco.mj_step once per iteration", source="upstream_code", ref=f"{SIM}:88"),
        Fact("The simulation loop treats qpos[7:] as the 29 joint positions and qvel[6:] as the 29 joint velocities, "
             "so the first seven qpos and six qvel values are the floating base", source="upstream_code",
             ref=f"{SIM}:85"),
        Fact("The simulation loop runs the FSM when sim_counter is a multiple of control_decimation",
             source="upstream_code", ref=f"{SIM}:89-90"),
        Fact("The README documents running the MuJoCo simulation with python deploy_mujoco/deploy_mujoco.py",
             source="vendor_doc", ref=f"{README}:62"),
        Fact("The README documents the LieDown start model with the override "
             "xml_path=g1_description/g1_29dof_LieDown.xml", source="vendor_doc", ref=f"{README}:94"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind, the time step and the lockstep clock; the values below are written out so the whole
    #: contract reads in one place.  Every gap is a difference from MuJoCo or from the upstream deploy loop.
    fidelity = {
        "engine": "mujoco:g1_29dof_rev_1_0",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "exact",
            "notes": "MuJoCo integrates one model deterministically from one initial state; cap.world.reset.v1 "
                     "restores the model defaults (mj_resetData plus mj_forward) and takes no seed parameter, so no "
                     "seed selects a different state; this package's fake is a placeholder integrator and was not "
                     "compared with MuJoCo",
        },
        "timestep_ms": 2.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses scene.xml and its include "
            "for the joint and actuator counts, the free-base start pose and the 2 ms model timestep, but integrates "
            "a placeholder torque response and resolves no mesh, texture, contact, constraint, gravity, inertia or "
            "sensor",
            "MuJoCo was not installed and cannot be installed where the gate ran (no network, no pip), so no "
            "trajectory of this package was compared with the real engine; the sim path (a backend name backends "
            "does not list, which imports the real mujoco module) was not run",
            "the upstream deploy_mujoco.py loop overrides the model timestep with simulation_dt 0.003 s, runs the "
            "FSM every 7 steps and reads a joystick (deploy_mujoco/deploy_mujoco.py:35, :57-90; "
            "deploy_mujoco/config/mujoco.yaml:3-4); this driver loads the scene directly, keeps the model's 0.002 s "
            "step and exposes data.ctrl, so it is not the upstream joystick and policy application",
            "no policy, joystick, viewer or FSM is modelled; the package is a local MuJoCo world, not the upstream "
            "deploy_mujoco application and not a physical robot",
            "the fake's free-base reset starts at the pelvis body pose (0 0 0.793) and identity quaternion; it does "
            "not run MuJoCo's qpos0 or forward kinematics, and its step does not clamp joints to their model ranges",
            "the model's motors declare no ctrlrange, so the bridge publishes action.ctrl operator_required: a step that sets it is refused until the site's site-limits.json bounds it, and site-limits.example.json is operator example data, not a model bound; "
            "the upstream deploy_mujoco.py application clips tau to "
            "tau_limit (deploy_mujoco/config/mujoco.yaml:5-9, deploy_mujoco/deploy_mujoco.py:86-87), but this "
            "driver does not present that application clamp as a model bound",
        ],
    }
