"""OpenMHS driver for gh.zhouyikaiii/ddc: the Unitree G1 29-DoF MuJoCo plant as a MuJoCo world.

A ``MujocoDriver`` is configuration only: the card's model (``robot/g1_29dof/g1_29dof.xml``) is loaded as a MuJoCo
world and the bridge derives the whole contract from it.  ``cap.world.step.v1`` takes
``{ticks, action: {ctrl: [...]}}``; each of the 29 ``ctrl`` elements is checked against the model's
``actuator_ctrlrange`` before it is written to ``data.ctrl``, then ``mj_step`` runs ``ticks`` times.
``cap.world.reset.v1`` restores the model defaults with ``mj_resetData`` + ``mj_forward``.  The world state is the
bridge's integration state (``time_ms``, ``qpos``, ``qvel``, ``ctrl``, ``tick``, ``timestep_ms``, ``seed``).  The
device is simulated (R0): there is no hardware backend and no operator-required limit; the control envelope is the
model's own.

The upstream is the benchmark released with the DDC paper: ``eval/`` is its self-contained MuJoCo sim2sim harness
(README.md:45) and ``robot/g1_29dof/`` is the exact Unitree G1 29-DoF plant the policy was validated on
(README.md:47).  The model references a ``floor`` geom that it does not define and it uses a relative mesh
directory; the upstream's ``_load_deploy_model`` patches both by dropping the ``<contact>`` pair block, injecting
the floor plane and writing an absolute mesh directory (eval/wbt_rollout.py:159-178).  This driver applies the same
text patch (never writing into the read-only clone) and sets the physics timestep that ``G1Sim`` applies at
eval/wbt_rollout.py:206.  The card's entry symbol ``eval.wbt_rollout:G1Sim`` was confirmed at line 199: it is the
MuJoCo G1 simulation class that wraps this model, whose ``step`` calls ``mujoco.mj_step``
(eval/wbt_rollout.py:415-416).  The upstream runtime on the physical robot (Holosoma + the Unitree SDK) is not
bundled in this repository (DEPLOYMENT.md:7-10), so this package is simulation-only.

MuJoCo is not installed and cannot be installed where the gate runs (no network, no pip), so ``backends["fake"]``
is this package's stand-in ``mujoco`` module (fake.py).  It parses the same patched model XML for the dimensions and
the per-actuator control ranges, but its integration is a placeholder, not MuJoCo's physics; the fidelity ``gaps``
list every difference.  A backend name that ``backends`` does not list (``sim``) imports the real ``mujoco`` module
and loads the same patched XML; that path was not run here.  This package is model-authored and unreviewed: it is
checked on the fake backend only.
"""

import re
from pathlib import Path

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

MODEL = "robot/g1_29dof/g1_29dof.xml"
#: The card's models[0] in the read-only clone at the pinned commit (never copied into this package).
CLONE_MODEL = Path(__file__).resolve().parents[4] / "robots/zhouyikaiii/ddc" / MODEL


def _deploy_model_xml() -> str:
    """The deploy scene the upstream builds from the robot XML (eval/wbt_rollout.py:159-178).

    The robot XML names a ``floor`` geom it does not define and a relative ``meshdir``.  The upstream drops the
    explicit foot<->floor ``<contact>`` pairs (they break under the deploy scene's attach prefix), injects the
    floor plane with the deploy scene parameters and rewrites ``meshdir`` to an absolute directory.  ``G1Sim`` then
    sets ``m.opt.timestep = SIM_DT`` with ``SIM_DT = 0.0005`` (eval/wbt_rollout.py:39, :206); the XML itself sets
    no ``<option timestep>``, so the same override is written here.  The clone is read only; nothing is written to
    it.
    """
    text = CLONE_MODEL.read_text(encoding="utf-8")
    meshes = str((CLONE_MODEL.parent / "meshes").resolve()) + "/"
    text = text.replace(
        '<compiler angle="radian" meshdir="./meshes/"/>',
        f'<compiler angle="radian" meshdir="{meshes}"/>\n    <option timestep="0.0005"/>',
        1,
    )
    text = re.sub(r"<contact>.*?</contact>", "", text, flags=re.DOTALL)
    floor = ('<geom name="floor" type="plane" size="0 0 0.05" pos="0 0 0" contype="1" conaffinity="1" '
             'friction="0.7 0.005 0.001" solref="0.001 1" solimp="0.99 0.99 0.01 0.5 2"/>\n</worldbody>')
    return text.replace("</worldbody>", floor, 1)


class UnitreeG1(MujocoDriver):
    device_id = "unitree-g1-29dof"
    model_xml = _deploy_model_xml()
    backends = {"fake": FakeMujoco}
    display_name = "Unitree G1 29-DoF MuJoCo plant (DDC benchmark)"
    vendor, model = "zhouyikaiii", "g1_29dof"
    tags = ["unitree", "g1", "humanoid", "mujoco", "simulation", "ddc", "single-leg-balance"]
    facts = [
        Fact("The repository releases a benchmark whose eval/ directory is a self-contained MuJoCo sim2sim harness "
             "built on numpy, mujoco and torch", source="vendor_doc", ref="README.md:45"),
        Fact("The robot/g1_29dof/ directory is the exact Unitree G1 29-DoF MuJoCo plant the policy was validated on",
             source="vendor_doc", ref="README.md:47"),
        Fact("The physical-robot runtime is the Holosoma two-process stack, and that framework and the Unitree SDK "
             "are not bundled in this repository", source="vendor_doc", ref="DEPLOYMENT.md:7-10"),
        Fact("The rollout module imports mujoco directly and is a self-contained MuJoCo rollout",
             source="upstream_code", ref="eval/wbt_rollout.py:1-17"),
        Fact("The default robot XML is robot/g1_29dof/g1_29dof.xml", source="upstream_code",
             ref="eval/wbt_rollout.py:34-35"),
        Fact("The model file is the MJCF document named g1_29dof, compiled in radians with its meshes under "
             "./meshes/", source="upstream_code", ref="robot/g1_29dof/g1_29dof.xml:12-13"),
        Fact("The deploy loader drops the contact pair block, injects a floor plane and rewrites the mesh "
             "directory before compiling the model",
             source="upstream_code", ref="eval/wbt_rollout.py:159-178"),
        Fact("The physics timestep is SIM_DT = 0.0005 s (2000 Hz)", source="upstream_code",
             ref="eval/wbt_rollout.py:39"),
        Fact("G1Sim assigns model.opt.timestep = SIM_DT after loading the deploy model", source="upstream_code",
             ref="eval/wbt_rollout.py:206"),
        Fact("The plant has one free base joint and the 29 policy joints, and G1Sim skips the first 7 qpos and 6 "
             "qvel entries of the free joint", source="upstream_code", ref="eval/wbt_rollout.py:213-214"),
        Fact("G1Sim.step advances the physics with mujoco.mj_step(self.model, self.data)", source="upstream_code",
             ref="eval/wbt_rollout.py:415-416"),
        Fact("The pelvis body carries the freejoint named floating_base_joint inside the body with childclass "
             "g1_29dof", source="upstream_code", ref="robot/g1_29dof/g1_29dof.xml:145-147"),
        Fact("The 29 motor actuators are named after the 29 joints; hip pitch/roll/yaw and waist yaw use +-88, "
             "knee +-139, ankle pitch/roll and waist roll/pitch +-50, shoulder, elbow and wrist roll +-25, and wrist "
             "pitch/yaw +-5, all as actuator ctrlrange", source="upstream_code",
             ref="robot/g1_29dof/g1_29dof.xml:442-476"),
        Fact("The model declares a contact block of 14 foot<->floor pairs whose second geom is named floor",
             source="upstream_code", ref="robot/g1_29dof/g1_29dof.xml:388-405"),
        Fact("The sensor block declares pelvis frame quaternion, gyro and accelerometer sensors, and mid360 "
             "frame quaternion and position sensors",
             source="upstream_code", ref="robot/g1_29dof/g1_29dof.xml:478-485"),
        Fact("The bundled G1 model and meshes derive from Unitree's BSD-3-Clause model; the notice attributes "
             "the actuator and visual-group modifications to Apache-2.0 Holosoma",
             source="vendor_doc", ref="robot/g1_29dof/NOTICE:4-17"),
    ]
    safe_state = ("this endpoint's lockstep world stops advancing: no step or world reset is accepted until "
                  "mhs.safety.reset clears the latch; qpos, qvel and ctrl are retained and readable, and clearing "
                  "the latch alone integrates no physics")
    #: The fidelity contract of the model as deployed.  The bridge derives the engine, the determinism kind, the
    #: lockstep clock and the timestep from the loaded model; the values are written out so the whole contract reads
    #: in one place.  The fake is a stand-in, not MuJoCo; every difference is a gap below.
    fidelity = {
        "engine": "mujoco:g1_29dof",
        "fidelity_level": "F1",
        "determinism": {"kind": "none", "seed_control": "none"},
        "timestep_ms": 0.5,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it reads the model XML for the "
            "qpos/qvel dimensions, the 29 actuator control ranges and the option timestep, but integrates a "
            "placeholder effort-driven acceleration using unit inverse inertia, rather than a position servo",
            "no mesh, texture, inertia, contact, friction, tendon, equality or actuator constraint is resolved; "
            "the foot<->floor contact pairs the upstream drops are not modelled and the free base is not integrated",
            "the stand-in reports the initial free-base position and identity orientation and never moves the base, "
            "so balance and contact trajectories are not the engine's",
            "the snapshot uses the bridge's basic profile (time and actuator activation) because the stand-in does "
            "not provide mj_getState, mj_setState, mj_stateSize or mjtState; the real engine offers the full "
            "integration-state profile",
            "MuJoCo was not importable where the gate ran, so no trajectory of this package was compared with the "
            "real engine, and the real sim backend was not run",
            "the raw model file sets no timestep and references an undefined floor geom; the driver applies the "
            "upstream deploy-scene patch at load time (drop the contact block, inject the floor plane, absolute "
            "meshdir) and writes the upstream SIM_DT of 0.0005 s, but that patched scene was not compiled here",
            "the package serves the model's raw torque channels; the upstream G1Sim's PD controller, its 29-joint "
            "q_target interface, its observation builder and the DDC policy are not part of this driver",
            "no physical Unitree G1 is modelled or controlled and nothing was validated against hardware: the "
            "repository's on-robot runtime and Unitree SDK are not bundled (DEPLOYMENT.md:7-10)",
            "rendering and the sensor block are not exposed; the package serves only cap.world.step.v1 and "
            "cap.world.reset.v1",
        ],
    }
    fidelity_by_backend = {
        "fake": {"engine": "analytic:g1-29dof-effort-fake", "fidelity_level": "F0"},
    }
