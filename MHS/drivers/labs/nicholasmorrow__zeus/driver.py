"""OpenMHS driver for gh.nicholasmorrow/zeus: one ZEUS liquid-handling module over SocketCAN.

A direct Driver (decorated methods) over the upstream device class ``zeus:ZeusModule``.  The upstream class builds
text commands from a command letter and parameters, splits them into seven-byte CAN frames and sends them through
python-can on the hard-coded ``socketcan_ctypes``/``can0`` bus (``zeus.py:481-511``); the driver therefore calls the
upstream object rather than reproducing the wire syntax.

The driver exposes the native operations that return a value or an acknowledgement:
the z-drive (initialize and move), the dosing drive (aspirate and dispense), tip pick-up and discard, and the
emergency stop.  The only state value the upstream class keeps and returns is ``pos``, the last z-drive position.

No text file of the clone states a physical range for the z position, a volume, a table index or a liquid class, so
each of those inputs is ``Limit.operator_required``: every call is refused ``MHS.SAFETY.LIMITS_UNSET`` until the site
supplies the range of its unit (``site-limits.example.json`` shows the overlay).  The z-drive speed words are the two
values the upstream method accepts (``zeus.py:535-543``).

Every Fact cites a line of the clone at the pinned commit (d2f5dbc1bc4fa80e930af49b3701ba5a1e0ed5fc).  This package
is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read


_POSITION_REASON = (
    "the clone states no physical range for the z-drive position; moveZDrive validates against the constructor "
    "attributes minZPosition/maxZPosition (zeus.py:348-349), not against a device bound")
_VOLUME_REASON = (
    "the clone states no volume range or unit; the ai/di fields have a fixed width and the error table names a "
    "maximum tip volume, but neither states the bound of this unit")
_TABLE_REASON = (
    "the clone states no range for a geometry or liquid-class table index; the operator supplies the indices "
    "configured on the unit")


class Zeus(Driver):
    device_id = "zeus"
    device_kind = "lab.liquid_handler"
    mode = "hardware"
    risk = "R2"
    native = "zeus:ZeusModule"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeZeusModule"}
    vendor, model = "nicholasmorrow", "ZEUS module (ZeusModule)"
    display_name = "ZEUS liquid-handling module (zeus.ZeusModule)"
    tags = ["liquid-handling", "pipetting", "can", "socketcan", "zeus"]
    facts = [
        Fact("ZeusModule is the user-facing driver class for one ZEUS module", source="upstream_code",
             ref="zeus.py:287"),
        Fact("The constructor accepts a module id in the range 1 to 31 and opens the CAN bus before initializing the "
             "Z-drive and the dosing drive", source="upstream_code", ref="zeus.py:334-356"),
        Fact("initCANBus selects the socketcan_ctypes interface on channel can0", source="upstream_code",
             ref="zeus.py:506-511"),
        Fact("The README initializes can_bus through an 8-devices USB2CAN interface with ./init_can.sh",
             source="vendor_doc", ref="README:1"),
        Fact("sendCommand splits a command into 7-byte chunks and sends each chunk with sendDataObject",
             source="upstream_code", ref="zeus.py:481-495"),
        Fact("The constructor sets pos to 0, minZPosition to 0 and maxZPosition to 1800", source="upstream_code",
             ref="zeus.py:347-349"),
        Fact("initZDrive sets pos to maxZPosition before sending the ZI command", source="upstream_code",
             ref="zeus.py:521-526"),
        Fact("moveZDrive builds a GZ command with the four-digit gy position and the gw speed code, and accepts only "
             "slow or fast", source="upstream_code", ref="zeus.py:528-549"),
        Fact("pickUpTip builds a GT command with tt and go, and discardTip builds a GU command with go",
             source="upstream_code", ref="zeus.py:551-561"),
        Fact("aspiration builds a GA command with the five-digit ai volume, ge, go and lq table indices and the "
             "optional mixing fields", source="upstream_code", ref="zeus.py:567-583"),
        Fact("dispensing builds a GD command with the four-digit di volume, ge, go, lq and zm fields and the "
             "optional mixing fields", source="upstream_code", ref="zeus.py:585-602"),
        Fact("switchOff sends the AV command", source="upstream_code", ref="zeus.py:604-606"),
        Fact("setEmergencyStop builds the AB command for an on state; the off branch references the undefined name "
             "seld, so this driver never sends the off command", source="upstream_code", ref="zeus.py:682-687"),
        Fact("Error code 36 means 'Emergency stop is active or was sent during action'", source="upstream_code",
             ref="zeus.py:297"),
        Fact("Error codes 53, 54 and 55 report a maximum tip volume, a maximum pipetting-drive volume and a failed "
             "volume check", source="upstream_code", ref="zeus.py:304-306"),
        Fact("The clone's demo constructs ZeusModule(1)", source="upstream_code", ref="tests/demo.py:5"),
    ]
    safe_state = "native emergency stop engaged (AB command)"

    # -- reads ------------------------------------------------------------------------------------------------
    @read("z_position", type="integer",
          description="Last commanded Z-drive position read from the native pos attribute (the clone states no unit)")
    def z_position(self):
        return self.native.pos

    # -- actions ----------------------------------------------------------------------------------------------
    @action(name="x-cap.nicholasmorrow.initialize.v1",
            description="Initialize the Z-drive and the dosing drive (native initZDrive and initDosingDrive)",
            output={"initialized": Field("boolean", description="True once the native initialization methods ran")})
    def initialize(self):
        self.native.initZDrive()
        self.native.initDosingDrive()
        return {"initialized": True}

    @action(name="x-cap.nicholasmorrow.move_z.v1",
            description="Command the Z-drive to a position at slow or fast speed (native GZ command)",
            input={
                "position": Field("integer", unit="1",
                                  description="Native Z-drive position; the clone states no unit or physical range",
                                  limit=Limit.operator_required(_POSITION_REASON)),
                "speed": Field("string", enum=["slow", "fast"],
                               description="Native speed word: slow or fast, the only values moveZDrive accepts "
                                           "(zeus.py:535-543)"),
            },
            output={
                "z_position": Field("integer",
                                    description="Last commanded Z-drive position read from the native pos attribute"),
                "speed": Field("string", description="Speed word the GZ command carried"),
            })
    def move_z(self, position, speed):
        self.native.moveZDrive(position, speed)
        return {"z_position": self.native.pos, "speed": speed}

    @action(name="x-cap.nicholasmorrow.pick_tip.v1",
            description="Pick up a tip from a tip type and deck geometry table entry (native GT command)",
            input={
                "tip_type": Field("integer", unit="1", description="Native tip type table index (tt)",
                                  limit=Limit.operator_required(_TABLE_REASON)),
                "deck_geometry": Field("integer", unit="1", description="Native deck geometry table index (go)",
                                       limit=Limit.operator_required(_TABLE_REASON)),
            },
            output={
                "tip_type": Field("integer", description="Tip type table index the GT command carried"),
                "deck_geometry": Field("integer", description="Deck geometry table index the GT command carried"),
            })
    def pick_tip(self, tip_type, deck_geometry):
        self.native.pickUpTip(tipTypeTableIndex=tip_type, deckGeometryTableIndex=deck_geometry)
        return {"tip_type": tip_type, "deck_geometry": deck_geometry}

    @action(name="x-cap.nicholasmorrow.discard_tip.v1",
            description="Discard the tip at a deck geometry table entry (native GU command)",
            input={
                "deck_geometry": Field("integer", unit="1", description="Native deck geometry table index (go)",
                                       limit=Limit.operator_required(_TABLE_REASON)),
            },
            output={"deck_geometry": Field("integer",
                                           description="Deck geometry table index the GU command carried")})
    def discard_tip(self, deck_geometry):
        self.native.discardTip(deckGeometryTableIndex=deck_geometry)
        return {"deck_geometry": deck_geometry}

    @action(name="x-cap.nicholasmorrow.aspirate.v1",
            description="Aspirate a volume with the dosing drive (native GA command)",
            input={
                "volume": Field("integer", unit="1",
                                description="Native aspiration volume (ai); the clone states no unit",
                                limit=Limit.operator_required(_VOLUME_REASON)),
                "container_geometry": Field("integer", unit="1",
                                            description="Native container geometry table index (ge)",
                                            limit=Limit.operator_required(_TABLE_REASON)),
                "deck_geometry": Field("integer", unit="1", description="Native deck geometry table index (go)",
                                       limit=Limit.operator_required(_TABLE_REASON)),
                "liquid_class": Field("integer", unit="1", description="Native liquid class table index (lq)",
                                      limit=Limit.operator_required(_TABLE_REASON)),
            },
            output={
                "commanded_volume": Field("integer",
                                          description="Native aspiration volume the GA command carried"),
                "container_geometry": Field("integer",
                                            description="Container geometry table index the GA command carried"),
                "deck_geometry": Field("integer", description="Deck geometry table index the GA command carried"),
                "liquid_class": Field("integer", description="Liquid class table index the GA command carried"),
            })
    def aspirate(self, volume, container_geometry, deck_geometry, liquid_class):
        self.native.aspiration(aspirationVolume=volume, containerGeometryTableIndex=container_geometry,
                               deckGeometryTableIndex=deck_geometry, liquidClassTableIndex=liquid_class)
        return {"commanded_volume": volume, "container_geometry": container_geometry,
                "deck_geometry": deck_geometry, "liquid_class": liquid_class}

    @action(name="x-cap.nicholasmorrow.dispense.v1",
            description="Dispense a volume with the dosing drive (native GD command)",
            input={
                "volume": Field("integer", unit="1",
                                description="Native dispensing volume (di); the clone states no unit",
                                limit=Limit.operator_required(_VOLUME_REASON)),
                "container_geometry": Field("integer", unit="1",
                                            description="Native container geometry table index (ge)",
                                            limit=Limit.operator_required(_TABLE_REASON)),
                "deck_geometry": Field("integer", unit="1", description="Native deck geometry table index (go)",
                                       limit=Limit.operator_required(_TABLE_REASON)),
                "liquid_class": Field("integer", unit="1", description="Native liquid class table index (lq)",
                                      limit=Limit.operator_required(_TABLE_REASON)),
            },
            output={
                "commanded_volume": Field("integer",
                                          description="Native dispensing volume the GD command carried"),
                "container_geometry": Field("integer",
                                            description="Container geometry table index the GD command carried"),
                "deck_geometry": Field("integer", description="Deck geometry table index the GD command carried"),
                "liquid_class": Field("integer", description="Liquid class table index the GD command carried"),
            })
    def dispense(self, volume, container_geometry, deck_geometry, liquid_class):
        self.native.dispensing(dispensingVolume=volume, containerGeometryTableIndex=container_geometry,
                               deckGeometryTableIndex=deck_geometry, liquidClassTableIndex=liquid_class)
        return {"commanded_volume": volume, "container_geometry": container_geometry,
                "deck_geometry": deck_geometry, "liquid_class": liquid_class}

    # -- safety ------------------------------------------------------------------------------------------------
    @action(name="x-cap.nicholasmorrow.emergency_stop.v1", safe_state=True,
            description="Engage the native emergency stop (AB); it takes no input",
            output={"emergency_stop": Field("boolean",
                                            description="True once the native AB command was sent")})
    def emergency_stop(self):
        self.native.setEmergencyStop(1)
        return {"emergency_stop": True}

    @estop(native="setEmergencyStop")
    def stop(self):
        """The native emergency stop: the runtime latches first, then sends AB."""
        self.native.setEmergencyStop(1)
