"""OpenMHS driver for gh.steiva/opentrons-ot2-http-python-wrapper: an Opentrons OT-2 over its HTTP API.

A direct Driver over the upstream class ``ot2_api:OpentronsAPI``.  The upstream object is a synchronous HTTP client:
each method builds a command dictionary and posts it to the robot server, waiting for the command to complete
(``waitUntilComplete``).  This package is model-authored and unreviewed, so it runs on the fake backend only.

* reads: the robot model from ``health()`` (the only request that needs no run) and the number of runs returned by
  ``get_run_info()``;
* fluid actions: ``cap.fluid.aspirate.v1`` and ``cap.fluid.dispense.v1`` over the wrapper's ``aspirate()`` and
  ``dispense()``; the catalogue class supplies the 0 to 1000 uL envelope (the wrapper does not state a range of its
  own, and the installed pipette is a configuration choice);
* setup and run actions as ``x-cap.steiva.*`` extensions: create a run, load the pipette, load labware, home the
  gantry and control the run;
* the native stop is the run action ``stop`` through ``control_run("stop")``.  It is both the ``@estop`` method and
  the ``safe_state=True`` action ``x-cap.steiva.stop_run.v1``; the clone documents no separate hardware stop.

Every Fact cites a line of the clone at the pinned commit 6bf929c11fe94a03c8b444c70e13be273933f365.  The hardware
factory is ``native.py`` and the gate never imports it; the acceptance gate runs the fake backend only.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read

SLOT_LIMIT = Limit(min=1, max=11, unit="1", source="upstream_code", ref="ot2_api.py:537")


class OpentronsOT2(Driver):
    device_id = "opentrons-ot2"
    device_kind = "lab.liquid_handler"
    mode = "hardware"
    risk = "R2"
    native = "ot2_api:OpentronsAPI"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeOpentronsAPI"}
    vendor, model = "Opentrons", "OT-2"
    display_name = "Opentrons OT-2 (HTTP wrapper)"
    tags = ["liquid-handler", "pipette", "robot", "http"]
    facts = [
        Fact("The wrapper's default robot address is 169.254.241.245:31950; OT2_HOST overrides the host",
             source="upstream_code", ref="ot2_api.py:11-13"),
        Fact("health() sends GET /health and returns the robot server's name, api_version and robot_model without a run",
             source="upstream_code", ref="ot2_api.py:149-159"),
        Fact("create_run() must be called before movement or aspiration; toggling the lights and homing do not need a "
             "run", source="upstream_code", ref="ot2_api.py:187-189"),
        Fact("create_run() stores the run id from the server's data and fills the run command and action endpoints",
             source="upstream_code", ref="ot2_api.py:208-212"),
        Fact("get_run_info() reads the run list, adopts the current run's id, pipette and labware, and returns the run "
             "data", source="upstream_code", ref="ot2_api.py:226-259"),
        Fact("home_robot() posts target robot to the home endpoint", source="upstream_code",
             ref="ot2_api.py:261-269"),
        Fact("load_pipette() requires a run id, sends the configured PIPETTE name, and stores the returned pipette id",
             source="upstream_code", ref="ot2_api.py:298-324"),
        Fact("load_labware() requires a run id, accepts a slot in range(1, 12), and stores the returned labware id "
             "under the slot name", source="upstream_code", ref="ot2_api.py:521-572"),
        Fact("control_run() accepts play, pause, stop and resume-from-recovery and posts the action to the run actions "
             "endpoint", source="upstream_code", ref="ot2_api.py:360-367"),
        Fact("aspirate() requires a run id and a pipette id", source="upstream_code", ref="ot2_api.py:758"),
        Fact("aspirate() takes volume in uL and flow rate in uL/s", source="upstream_code",
             ref="ot2_api.py:773-774"),
        Fact("dispense() requires a run id and a pipette id", source="upstream_code", ref="ot2_api.py:841"),
        Fact("dispense() takes volume in uL and flow rate in uL/s", source="upstream_code",
             ref="ot2_api.py:857-858"),
        Fact("The default pipette name is p300_single_gen2 and the caller may change the instance's PIPETTE",
             source="vendor_doc", ref="README.md:88"),
    ]
    safe_state = "the current run is stopped with the run action stop"

    # -- reads -------------------------------------------------------------------------------------------------
    @read("robot_model", type="string", description="Robot model reported by GET /health")
    def robot_model(self):
        return self.native.health()["robot_model"]

    @read("run_count", type="integer", description="Number of runs returned by the robot's run list")
    def run_count(self):
        return len(self.native.get_run_info())

    # -- fluid actions -----------------------------------------------------------------------------------------
    @action(cap="cap.fluid.aspirate.v1", description="Aspirate liquid from a well with the loaded pipette",
            input={
                "volume": Field("number", unit="uL", description="Volume to aspirate in microlitres"),
                "source": Field("object", description="Source labware and well",
                                properties={
                                    "labware": Field("string", max_length=128,
                                                     description="Labware identifier returned by load_labware"),
                                    "well": Field("string", max_length=32, description="Well name, for example A1"),
                                }),
            })
    def aspirate(self, volume, source):
        self.native.aspirate(source["labware"], source["well"], volume=volume)
        return {"aspirated_volume": volume}

    @action(cap="cap.fluid.dispense.v1", description="Dispense liquid into a well with the loaded pipette",
            input={
                "volume": Field("number", unit="uL", description="Volume to dispense in microlitres"),
                "target": Field("object", description="Target labware and well",
                                properties={
                                    "labware": Field("string", max_length=128,
                                                     description="Labware identifier returned by load_labware"),
                                    "well": Field("string", max_length=32, description="Well name, for example A1"),
                                }),
            })
    def dispense(self, volume, target):
        self.native.dispense(target["labware"], target["well"], volume=volume)
        return {"dispensed_volume": volume}

    # -- setup and run actions ---------------------------------------------------------------------------------
    @action(name="x-cap.steiva.create_run.v1", description="Create a run on the robot; needed before pipette, "
            "labware, movement and fluid commands",
            output={"run_id": Field("string", description="Identifier of the run created by the robot server")})
    def create_run(self):
        self.native.create_run()
        run_id = self.native.run_id
        if not run_id:
            raise DriverFailed("MHS.DEVICE.FAULTED", "create_run returned no run id")
        return {"run_id": run_id}

    @action(name="x-cap.steiva.load_pipette.v1", description="Load the configured pipette on a mount",
            input={"mount": Field("string", enum=["left", "right"],
                                  description="Pipette mount: left or right")},
            output={"pipette_id": Field("string", description="Pipette identifier assigned by the robot server")})
    def load_pipette(self, mount):
        self.native.load_pipette(mount)
        pipette_id = self.native.pipette_id
        if not pipette_id:
            raise DriverFailed("MHS.DEVICE.FAULTED", "load_pipette returned no pipette id")
        return {"pipette_id": pipette_id}

    @action(name="x-cap.steiva.load_labware.v1", description="Load labware into a deck slot",
            input={
                "labware_api_name": Field("string", max_length=128,
                                          description="Labware name from the Opentrons labware library"),
                "slot_name": Field("integer", unit="1", description="Deck slot (1 to 11)",
                                   limit=SLOT_LIMIT),
            },
            output={"labware_id": Field("string",
                                        description="Labware identifier assigned by the robot server")})
    def load_labware(self, labware_api_name, slot_name):
        self.native.load_labware(labware_api_name, slot_name)
        labware_id = self.native.labware_dct[str(slot_name)]
        if not labware_id:
            raise DriverFailed("MHS.DEVICE.FAULTED", "load_labware returned no labware id")
        return {"labware_id": labware_id}

    @action(name="x-cap.steiva.home.v1", description="Home the robot gantry",
            output={"homed": Field("boolean", description="True once the homing command has been posted")})
    def home(self):
        self.native.home_robot()
        return {"homed": True}

    @action(name="x-cap.steiva.control_run.v1", description="Play, pause, stop or recover the current run",
            input={"action": Field("string", enum=["play", "pause", "stop", "resume-from-recovery"],
                                   description="Run action to send")},
            output={"action": Field("string", description="Run action sent to the robot")})
    def control_run(self, action):
        self.native.control_run(action)
        return {"action": action}

    # -- safety ------------------------------------------------------------------------------------------------
    @action(name="x-cap.steiva.stop_run.v1", safe_state=True,
            description="Stop the current run (the safe-state action); it takes no input",
            output={"stopped": Field("boolean", description="True once the run stop action has been posted")})
    def stop_run(self):
        self.native.control_run("stop")
        return {"stopped": True}

    @estop
    def stop(self):
        """The native stop: the run action stop through ``control_run("stop")``."""
        self.native.control_run("stop")
