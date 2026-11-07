"""OpenMHS driver for gh.oelemento/star-sim: the Hamilton STARlet digital twin over PyLabRobot (simulated).

A config-only ``PyLabRobotDriver`` (profile ``plr-liquid-handler-v1``) over the card's entry class
``star_sim.env:RobotEnv``.  RobotEnv holds a PyLabRobot ``LiquidHandler`` at ``lh`` (star_sim/env.py:60-63), built on
the ChatterBox backend unless ``use_hardware`` is true (star_sim/lab.py:40-49); this package is the simulated twin
only, so it never exposes ``use_hardware`` (its fake refuses it).

* three ``x-cap`` operations: ``transfer`` and ``mix`` are self-contained like the upstream primitives (pick up
  tips, aspirate, dispense, discard the tips; star_sim/primitives.py:1-13, 55-66, 128-140), and ``tracked_volumes``
  reads the PyLabRobot volume tracker the way RobotEnv.observe does (star_sim/env.py:113);
* labware is the upstream deck: ``tip_rack``, ``source_plate`` and ``dest_plate`` (star_sim/deck.py:47, 52, 53);
* the per-channel volume is 1 to 1000 uL for each operation, cited at the upstream agent tool that performs it
  (column_transfer, agent.py:53; mix_column, agent.py:96), and the mix cycles 1 to 10 (agent.py:97);
* one read: the upstream TipManager's count of full tip columns (star_sim/tip_manager.py:33-42).

There is no native stop: the device is simulated, and PyLabRobot's ``stop()`` is teardown.  An e-stop latches the
runtime, and no later PyLabRobot step of a running operation is sent; the step in progress is not interrupted.  Every Fact cites a line of the clone at the
pinned commit 5b5211a4c5414e5a9752b286515fbe87e769842d.  The package is model-authored and checked on the fake backend
only (README.md).
"""

from mhs.driver import Fact, Field, Limit, PlrLabware, PlrOperation, PlrProfile, PyLabRobotDriver


class StarSim(PyLabRobotDriver):
    device_id = "star-sim"
    device_kind = "lab.liquid_handler"
    mode = "simulated"
    risk = "R2"
    native = "star_sim.env:RobotEnv"
    backends = {"fake": ".fake:FakeRobotEnv"}
    vendor, model = "oelemento", "star-sim Hamilton STARlet digital twin"
    display_name = "Hamilton STARlet digital twin (star_sim.RobotEnv, PyLabRobot ChatterBox)"
    tags = ["liquid-handler", "pylabrobot", "hamilton", "starlet", "digital-twin", "simulation"]
    safe_state = ("simulated only, no physical device: after an e-stop the runtime latch refuses new operations and "
                  "no further PyLabRobot step of a running operation is sent, but the step in progress is not "
                  "interrupted, so an e-stop during an operation is reported SAFE_STATE_UNREACHED; tips and liquid "
                  "stay where the last completed step left them")
    facts = [
        Fact("star-sim is a simulated Hamilton STARlet built on PyLabRobot; the same protocol runs against a "
             "simulated robot (ChatterBox backend) or the physical Hamilton STAR", source="vendor_doc",
             ref="README.md:3-5"),
        Fact("make_liquid_handler switches PyLabRobot tip tracking and volume tracking on before the deck is built",
             source="upstream_code", ref="star_sim/lab.py:34-36"),
        Fact("use_hardware=False selects LiquidHandlerChatterboxBackend(num_channels=num_channels); True selects the "
             "STAR backend", source="upstream_code", ref="star_sim/lab.py:40-47"),
        Fact("The deck is a STARLetDeck with one Hamilton 1000 uL filtered tip rack named tip_rack on a tip carrier",
             source="upstream_code", ref="star_sim/deck.py:43-48"),
        Fact("Two 96-well plates named source_plate and dest_plate sit on a plate carrier", source="upstream_code",
             ref="star_sim/deck.py:51-55"),
        Fact("RobotEnv defaults to the simulation (use_hardware False) with 8 channels", source="upstream_code",
             ref="star_sim/env.py:33"),
        Fact("RobotEnv.setup builds the liquid handler and deck, a TipManager and a PlateMap, then awaits lh.setup()",
             source="upstream_code", ref="star_sim/env.py:59-66"),
        Fact("RobotEnv.teardown awaits lh.stop()", source="upstream_code", ref="star_sim/env.py:68-69"),
        Fact("Each primitive acquires fresh tips, performs one liquid-handling action and drops the tips before it "
             "returns", source="upstream_code", ref="star_sim/primitives.py:3-5"),
        Fact("column_transfer picks up tips, aspirates, dispenses and discards the tips in a finally block",
             source="upstream_code", ref="star_sim/primitives.py:55-67"),
        Fact("_plate_state maps each non-empty well id to its tracked used volume in microlitres",
             source="upstream_code", ref="star_sim/env.py:101-116"),
        Fact("TipManager.remaining counts the tip columns from the cursor on that still hold every tip",
             source="upstream_code", ref="star_sim/tip_manager.py:33-42"),
        Fact("The column_transfer agent tool takes a volume of 1 to 1000 uL per channel", source="upstream_code",
             ref="agent.py:53"),
        Fact("The mix_column agent tool takes a volume of 1 to 1000 uL", source="upstream_code", ref="agent.py:96"),
        Fact("mix_column takes 1 to 10 repetitions", source="upstream_code", ref="agent.py:97"),
        Fact("propose_prime seeds the plate volume trackers with the declared volumes", source="upstream_code",
             ref="agent.py:825-833"),
        Fact("The project was tested with pylabrobot 0.2.1 and requires pylabrobot>=0.2.1", source="vendor_doc",
             ref="requirements.txt:2-3"),
    ]
    fidelity = {
        "engine": "custom:star-sim-pylabrobot-chatterbox",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "seed_control": "none",
            "notes": "the fake's tip and volume bookkeeping is deterministic, but the upstream twin exposes no seed or "
                     "state snapshot, so no replay claim is made",
        },
        "timestep_ms": 0.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "bookkeeping only: the fake models PyLabRobot's tip and volume tracking, not motion, timing, liquid "
            "classes, offsets, aspiration physics or a browser visualizer",
            "the fake's source plate starts with placeholder liquid in every well; the upstream deck starts empty "
            "and its agent seeds volumes with propose_prime, which this package does not expose",
            "well and tip capacities in the fake are placeholders, not the PyLabRobot resource definitions",
            "the fake was not compared with the upstream twin; PyLabRobot was not installed where the gate ran",
            "the upstream composite tools (column_transfer, multi_dispense, serial_transfer, propose_prime), the "
            "PlateMap compound records and RobotEnv.reset are not exposed",
            "no failure cleanup: the upstream primitives discard the tips in a finally block "
            "(star_sim/primitives.py:65-66); this package leaves them mounted after a failure or an e-stop, so the "
            "next operation fails channel_free until the endpoint is restarted",
            "own tip selection: tips are taken from PyLabRobot tip tracking (the first adjacent rows in one column), "
            "never through TipManager.next_column, so the TipManager cursor behind tips_remaining_columns is not "
            "advanced (the count still drops, because it checks every tip of each column)",
            "multi-channel layout: one call uses one column with strictly increasing rows and no repeated well, "
            "as a gantry head requires; the fake models no geometry, channel spacing or X motion",
            "no physical device is modelled; the physical STAR path of the upstream is never reached",
        ],
    }
    parameters = {
        "tips_remaining_columns": Field("integer", description="Tip columns that still hold every tip (TipManager)"),
    }
    reads = {"tips_remaining_columns": {"native": "tips.remaining", "invoke": "get"}}
    plr_profile = PlrProfile(
        handler="lh", handler_ref="star_sim/env.py:60",
        setup="setup", setup_ref="star_sim/env.py:59",
        close="teardown", close_ref="star_sim/env.py:68",
        channels=8, channels_ref="star_sim/env.py:33",
        tip_tracking_ref="star_sim/lab.py:35", volume_tracking_ref="star_sim/lab.py:36",
        labware=(PlrLabware("tip_rack", "tip_rack", "star_sim/deck.py:47"),
                 PlrLabware("source_plate", "plate", "star_sim/deck.py:52"),
                 PlrLabware("dest_plate", "plate", "star_sim/deck.py:53")),
        operations={
            "x-cap.oelemento.transfer.v1": PlrOperation(
                "transfer", "star_sim/primitives.py:55-66",
                volume_limit=Limit(min=1, max=1000, source="upstream_code", ref="agent.py:53")),
            "x-cap.oelemento.mix.v1": PlrOperation(
                "mix", "star_sim/primitives.py:128-140",
                volume_limit=Limit(min=1, max=1000, source="upstream_code", ref="agent.py:96")),
            "x-cap.oelemento.tracked_volumes.v1": PlrOperation("tracked_volumes", "star_sim/env.py:113"),
        },
        cycles_limit=Limit(min=1, max=10, source="upstream_code", ref="agent.py:97"),
        well_pattern="^[A-H](?:[1-9]|1[0-2])$",
    )
