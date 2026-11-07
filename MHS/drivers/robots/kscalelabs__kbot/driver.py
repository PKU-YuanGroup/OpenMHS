"""OpenMHS driver for gh.kscalelabs/kbot: the K-Bot V2 feet MJCF scene (a MuJoCo family driver).

A ``MujocoDriver`` is configuration only: ``model_path`` names the card's first model,
``ksim-kbot/ksim_kbot/kscale-assets/kbot-v2-feet/scene.mjcf``, and the bridge derives the contract from the model it
loads.  The scene includes ``robot.mjcf``, which carries the floating base, the arm and leg joints and the motor
actuators.  ``cap.world.step.v1`` takes ``{ticks, action: {ctrl: [...]}}``; each ``ctrl`` element is checked against
the model's ``actuator_ctrlrange`` before it is written to ``data.ctrl``, then ``mj_step`` runs ``ticks`` times.
``cap.world.reset.v1`` restores the model defaults with ``mj_resetData`` + ``mj_forward``.  The world state is the
bridge's integration state (``time_ms``, ``qpos``, ``qvel``, ``ctrl``, ``tick``, ``timestep_ms``, ``seed``).

The device is simulated (R0): the upstream is a MuJoCo training stack for a humanoid robot, not a hardware
interface, and this package exposes only the MJCF model.  There is no hardware backend, no e-stop path to a machine
and no operator-required limit; the model file is the system of record for the control envelope.

MuJoCo is not installed and cannot be installed where the acceptance gate runs (no network, no pip), so
``backends["fake"]`` is this package's stand-in ``mujoco`` module (fake.py).  It parses the same MJCF text with its
includes expanded and takes the actuator count, the per-actuator control ranges and the joint dimensions from that
tree, but its integration is a placeholder, not MuJoCo's physics; the fidelity ``gaps`` state every difference.  A
backend name that ``backends`` does not list (``sim``) imports the real ``mujoco`` module and loads the same file;
that path was not run here.

The model files are read from the read-only upstream clone at the pinned commit (they are never copied into this
package and never imported).  The card's model files are inside the ``ksim-kbot`` git submodule, which the pinned
superproject commit records as a gitlink, so G4 cannot read a line inside the submodule and no Fact cites one; the
facts below cite the superproject files only.  This package is model-authored and unreviewed: it is checked on the
fake backend only, and nothing here ran the MuJoCo engine or a physical K-Bot.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

MODEL = "ksim-kbot/ksim_kbot/kscale-assets/kbot-v2-feet/scene.mjcf"
#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/kscalelabs/kbot/" + MODEL


class Kbot(MujocoDriver):
    device_id = "kbot-v2"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "K-Bot V2 feet (MuJoCo simulation)"
    vendor, model = "K-Scale Labs", "K-Bot V2 (kbot-v2-feet)"
    tags = ["humanoid", "k-scale", "kbot", "mujoco", "robot", "simulation"]
    facts = [
        Fact("K-Bot is an open-source humanoid robot from K-Scale Labs", source="vendor_doc", ref="README.md:3"),
        Fact("The project is in public alpha and the README warns that breaking changes are expected",
             source="vendor_doc", ref="README.md:15"),
        Fact("The repository tracks ksim-kbot as a git submodule at path ksim-kbot with URL "
             "git@github.com:kscalelabs/ksim-kbot.git", source="upstream_code", ref=".gitmodules:5-8"),
        Fact("The mechanical design notes say the hands can be swapped through a lens mount interface and use the "
             "same 48 volt power and CAN bus lines as the arm actuators", source="vendor_doc",
             ref="mechanical/README.md:11"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the time step and the lockstep clock from the model; the values below are this package's.
    fidelity = {
        "engine": "mujoco:k-bot_v2_feet",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "MuJoCo integrates the MJCF deterministically from the reset state and one ctrl sequence, so "
                     "a trajectory repeats on the same engine; the model declares sensor noise elements, but this "
                     "driver reads only the integration state and never reads a sensor. The bridge takes no seed "
                     "input and a reset restores the model defaults, so no seed selects a different one. The "
                     "package's fake backend is deterministic too, but its placeholder motion is not the engine's "
                     "physics.",
        },
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses the served scene.mjcf "
            "with its robot.mjcf include, takes the actuator control ranges and the joint dimensions from that "
            "tree, then advances each actuated hinge by a placeholder velocity proportional to its control value; "
            "it computes no inertia, torque, contact, equality, tendon or actuator dynamics, so no trajectory here "
            "is a MuJoCo result",
            "the stand-in loads no mesh, texture or heightfield and resolves no contact or friction: the scene's "
            "heightfield floor and the robot's collision geoms are not simulated",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared "
            "with the real engine",
            "snapshots copy time, qpos, qvel, act and ctrl (the bridge's fallback) because the stand-in offers no "
            "mj_getState/mj_setState/mj_stateSize; a restore is not the full integration state of MuJoCo",
            "no physical K-Bot is modelled and nothing was validated against the K-Scale hardware",
        ],
    }
