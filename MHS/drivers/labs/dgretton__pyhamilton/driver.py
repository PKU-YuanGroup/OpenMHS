"""OpenMHS driver for gh.dgretton/pyhamilton: the Hamilton STAR/STARlet interface.

A direct Driver (decorated methods) over the upstream device class pyhamilton.interface:HamiltonInterface.  The
upstream class starts the Hamilton OEM process and a localhost HTTP server and sends JSON command dictionaries to
it (pyhamilton/interface.py:501-506, 578-585, 696-735); it is not a plain object with one getter per field, so this
package uses a direct Driver and a native.py adapter rather than a PythonObjectDriver configuration.

* reads: whether the interface is started and whether its local server thread has exited;
* actions: initialize, single-channel aspirate and dispense, a plate move by sequence (iSWAP) and a labware property
  write.  The aspirate and dispense actions carry the Hamilton liquid class, because aspirate refuses a command
  without one (pyhamilton/interface.py:909-911) and the catalogue fluid classes have no field for it;
* the native stop (HamiltonInterface.stop) is the e-stop and, as shutdown_interface, the safe-state action.  A
  safety reset only releases the latch: the driver has no ``@reset`` hook (SAFE-042).  Starting the interface again
  (HamiltonInterface.start, which relaunches the OEM process the stop terminated, pyhamilton/interface.py:578-611;
  the clone does not say whether that start moves the instrument) is the declared re-enable
  ``x-cap.dgretton.start_interface.v1`` (``reenable=True``, CORE-086), a command of its own that the latch refuses.

No text file of the clone states a volume, flow, force or travel envelope for a configured robot: the pipetting
capacity depends on the installed tip type and the liquid class (pyhamilton/liquid_class_db.py:306-333), so every
numeric action input is ``Limit.operator_required``.  Every call that sets one is refused
``MHS.SAFETY.LIMITS_UNSET`` until the operator writes the range of the unit into site-limits.json
(``site-limits.example.json`` is an example only, not a statement about any robot).

Every Fact cites a line of the clone at the pinned commit 65938d05cc8f5a5a0d3186648add560439ab1cdd.  This package is
model-authored and unreviewed: it is checked on the fake backend only, and the loader refuses its R2 hardware backend
until a human signs ``reviewed_by`` in driver.lock.json.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read

_VOLUME_LIMIT = Limit.operator_required(
    "no text of the clone states a volume range of a configured Hamilton robot; the usable volume depends on the "
    "installed tip type and the liquid class (pyhamilton/liquid_class_db.py:306-333), so the site supplies the range "
    "of its channels and tips")


class Pyhamilton(Driver):
    device_id = "pyhamilton"
    device_kind = "lab.liquid_handler"
    mode = "hardware"
    risk = "R2"
    native = "pyhamilton.interface:HamiltonInterface"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeHamiltonInterface"}
    vendor, model = "Hamilton", "STAR / STARlet (pyhamilton HamiltonInterface)"
    display_name = "Hamilton liquid handler (pyhamilton.HamiltonInterface)"
    tags = ["liquid-handler", "hamilton", "venus", "iswap", "pipetting"]
    facts = [
        Fact("HamiltonInterface is the main class that sets up and tears down the interface to a Hamilton robot and "
             "creates a Hamilton HSL background process plus a localhost connection",
             source="upstream_code", ref="pyhamilton/interface.py:501-506"),
        Fact("start() launches the pyhamilton interpreter/OEM application and the local HTTP server, and is_open() "
             "returns the active flag", source="upstream_code", ref="pyhamilton/interface.py:578-596"),
        Fact("stop() terminates the OEM process in normal mode, sets active to False and joins the server thread "
             "with a 1.0 s timeout", source="upstream_code", ref="pyhamilton/interface.py:619-666"),
        Fact("start() opens the OEM application with a window for simulation, only sets active in simulating mode, "
             "starts a 32-bit server process in server mode, and otherwise starts a new OEM process "
             "(run_hamilton_process)", source="upstream_code", ref="pyhamilton/interface.py:578-611"),
        Fact("is_open() returns True between start() and stop()", source="upstream_code",
             ref="pyhamilton/interface.py:692-694"),
        Fact("initialize() sends the INITIALIZE command and waits up to 300 s for its response",
             source="upstream_code", ref="pyhamilton/interface.py:868-884"),
        Fact("aspirate() refuses a command without a liquidClass and accepts at most 8 positions",
             source="upstream_code", ref="pyhamilton/interface.py:906-911"),
        Fact("dispense() accepts at most 8 positions and uses the upstream default liquid class when none is given",
             source="upstream_code", ref="pyhamilton/interface.py:962-967"),
        Fact("aspirate() and dispense() return AspirateResult or DispenseResult with liquidHeights and liquidVolumes",
             source="upstream_code", ref="pyhamilton/interface.py:930-944"),
        Fact("move_by_seq() sends ISWAP_GET for the source sequence and ISWAP_PLACE for the target sequence, each "
             "with a 120 s response timeout", source="upstream_code", ref="pyhamilton/interface.py:1350-1398"),
        Fact("set_labware_property() sends SET_LABWARE_PROPERTY with LabwareID, PropertyName and PropertyValue",
             source="upstream_code", ref="pyhamilton/interface.py:1241-1258"),
        Fact("HamiltonServerThread.has_exited reports whether the local server thread has left its run loop",
             source="upstream_code", ref="pyhamilton/interface.py:489-498"),
        Fact("The usable pipetting volume is derived from the installed tip type and the liquid class, not from a "
             "fixed robot bound", source="upstream_code", ref="pyhamilton/liquid_class_db.py:306-333"),
        Fact("The project is developed for Hamilton STAR and STARlet on Windows; VANTAGE is supported with a plugin",
             source="vendor_doc", ref="README.md:7"),
        Fact("The clone's tests mock HamiltonInterface.start and HamiltonInterface.stop; it ships no device "
             "simulator for these actions", source="upstream_code", ref="tests/interface_tests.py:277-280"),
        Fact("The simulating flag only logs commands and returns no response data instead of emulating the robot",
             source="upstream_code", ref="pyhamilton/interface.py:596-598"),
    ]
    safe_state = ("the Hamilton interface is stopped: the local server thread is signalled and the OEM process is "
                  "terminated by the native stop; a reset leaves it stopped until the declared re-enable "
                  "x-cap.dgretton.start_interface.v1 starts it again")

    # -- lifecycle ------------------------------------------------------------------------------------------------
    def setup(self):
        """Open the upstream interface (the equivalent of entering the upstream ``with`` block)."""
        self.native.start()

    def teardown(self):
        self.native.stop()

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("is_open", type="boolean", description="True while the Hamilton interface has been started and not stopped")
    def is_open(self):
        return self.native.is_open()

    @read("server_exited", type="boolean", description="True once the local Hamilton server thread has exited")
    def server_exited(self):
        return self.native.server_thread.has_exited()

    # -- actions --------------------------------------------------------------------------------------------------
    @action(name="x-cap.dgretton.initialize.v1",
            description="Initialize the Hamilton robot (the upstream INITIALIZE command) and wait for its response",
            output={"initialized": Field("boolean", description="True once INITIALIZE returned without an error")})
    def initialize(self):
        self.native.initialize()
        return {"initialized": True}

    @action(name="x-cap.dgretton.aspirate.v1",
            description="Aspirate a volume from one well with one pipetting channel and the named Hamilton liquid "
                        "class; it does not attach or eject a tip",
            input={
                "labware": Field("string", description="Layout name of the source labware in the active Hamilton "
                                                       "layout"),
                "well": Field("string", description="Well identifier of the source position, for example A1"),
                "volume": Field("number", unit="uL", description="Volume to aspirate",
                                limit=_VOLUME_LIMIT),
                "liquid_class": Field("string", description="Hamilton liquid class name used for the aspiration"),
            },
            output={
                "aspirated_volume": Field("number", unit="uL",
                                          description="Volume the upstream result reports as aspirated"),
                "labware": Field("string", description="Source labware the command named"),
                "well": Field("string", description="Source well the command named"),
                "liquid_class": Field("string", description="Liquid class the command used"),
            })
    def aspirate(self, labware, well, volume, liquid_class):
        result = self.native.aspirate([(labware, well)], [volume], liquidClass=liquid_class)
        return {"aspirated_volume": _reported_volume(result, volume),
                "labware": labware, "well": well, "liquid_class": liquid_class}

    @action(name="x-cap.dgretton.dispense.v1",
            description="Dispense a volume into one well with one pipetting channel and the named Hamilton liquid "
                        "class; it does not attach or eject a tip",
            input={
                "labware": Field("string", description="Layout name of the target labware in the active Hamilton "
                                                       "layout"),
                "well": Field("string", description="Well identifier of the target position, for example A1"),
                "volume": Field("number", unit="uL", description="Volume to dispense",
                                limit=_VOLUME_LIMIT),
                "liquid_class": Field("string", description="Hamilton liquid class name used for the dispense"),
            },
            output={
                "dispensed_volume": Field("number", unit="uL",
                                          description="Volume the upstream result reports as dispensed"),
                "labware": Field("string", description="Target labware the command named"),
                "well": Field("string", description="Target well the command named"),
                "liquid_class": Field("string", description="Liquid class the command used"),
            })
    def dispense(self, labware, well, volume, liquid_class):
        result = self.native.dispense([(labware, well)], [volume], liquidClass=liquid_class)
        return {"dispensed_volume": _reported_volume(result, volume),
                "labware": labware, "well": well, "liquid_class": liquid_class}

    @action(name="x-cap.dgretton.move_plate.v1",
            description="Move a plate from one Hamilton sequence to another with the iSWAP (ISWAP_GET then "
                        "ISWAP_PLACE)",
            input={
                "source_sequence": Field("string", description="Hamilton sequence name of the source plate"),
                "target_sequence": Field("string", description="Hamilton sequence name of the target position"),
            },
            output={
                "moved": Field("boolean", description="True once ISWAP_PLACE returned without an error"),
                "location": Field("string", description="Target sequence the plate was placed at"),
                "source_sequence": Field("string", description="Source sequence the plate was taken from"),
            })
    def move_plate(self, source_sequence, target_sequence):
        self.native.move_by_seq(source_sequence, target_sequence)
        return {"moved": True, "location": target_sequence, "source_sequence": source_sequence}

    @action(name="x-cap.dgretton.set_labware_property.v1",
            description="Set one property of one labware item in the Hamilton run (the upstream "
                        "SET_LABWARE_PROPERTY command)",
            input={
                "labware_id": Field("string", description="Hamilton identifier of the labware item"),
                "property_name": Field("string", description="Name of the property to set"),
                "property_value": Field("string", description="Value to write into the property"),
            },
            output={
                "labware_id": Field("string", description="Labware identifier the command named"),
                "property_name": Field("string", description="Property name the command set"),
                "property_value": Field("string", description="Value the command wrote"),
            })
    def set_labware_property(self, labware_id, property_name, property_value):
        self.native.set_labware_property(labware_id, property_name, property_value)
        return {"labware_id": labware_id, "property_name": property_name, "property_value": property_value}

    @action(name="x-cap.dgretton.shutdown_interface.v1", safe_state=True,
            description="Stop the Hamilton interface (the native stop): signal the server thread and terminate the "
                        "OEM process; it takes no input",
            output={"stopped": Field("boolean", description="True once the native stop returned")})
    def shutdown_interface(self):
        self.native.stop()
        return {"stopped": True}

    # -- safety ---------------------------------------------------------------------------------------------------
    @action(name="x-cap.dgretton.start_interface.v1", reenable=True,
            description="Start the Hamilton interface again after a safety reset (the declared re-enable): "
                        "HamiltonInterface.start() relaunches the OEM process (or the server or simulation process) "
                        "that the stop terminated; the clone does not say whether that start moves the instrument. "
                        "It takes no input, is refused while the e-stop is latched and is never run by the reset",
            output={"started": Field("boolean", description="True once HamiltonInterface.start() returned")})
    def start_interface(self):
        """The new start command after a reset (SAFE-042, CORE-086): pyhamilton/interface.py:578-611."""
        self.native.start()
        return {"started": True}

    @estop
    def stop(self):
        """The native stop: the runtime latches first, then HamiltonInterface.stop() is called."""
        self.native.stop()

    # No @reset hook: a reset only releases the latch (SAFE-042); start() may initialise the instrument, so
    # starting the interface again is the declared re-enable above (CORE-086).


def _reported_volume(result, requested):
    """The first volume of an upstream AspirateResult/DispenseResult, or the requested volume."""
    volumes = getattr(result, "liquidVolumes", None)
    if volumes:
        return float(volumes[0])
    return float(requested)
