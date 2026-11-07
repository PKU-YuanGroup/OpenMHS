"""Fake backend of the ZEUS driver: an in-memory stand-in for ``zeus:ZeusModule``.

Gate G7: every public method defined here exists on ``zeus.ZeusModule`` in the clone (``zeus.py``), and the one
attribute the driver reads, ``pos``, is set by the upstream constructor and by ``initZDrive``/``moveZDrive``
(``zeus.py:347``, ``zeus.py:525``, ``zeus.py:548``).  The methods keep the upstream signatures and the upstream
validation of the z-drive speed.  The values below are test data only; each is marked ``# placeholder``.

The fake does not assemble CAN frames and does not emulate replies: it records the effect of the native command
methods.  Nothing here talks to a CAN interface.
"""


class FakeZeusModule:
    """In-memory ZEUS module; one object per device endpoint."""

    def __init__(self, **_options):
        self.pos = 0                    # placeholder: the upstream constructor initializes pos to 0 (zeus.py:347)
        self.minZPosition = 0           # placeholder: constructor default (zeus.py:348)
        self.maxZPosition = 1800        # placeholder: constructor default (zeus.py:349)
        self.emergency_stop_active = False
        self.initialized = False
        self.aspirated_volume = 0       # placeholder: last commanded aspiration volume
        self.dispensed_volume = 0       # placeholder: last commanded dispensing volume
        self.tip_type = None
        self.deck_geometry = None

    # -- the native class's public surface ---------------------------------------------------------------
    def initZDrive(self):
        self.pos = self.maxZPosition
        self.initialized = True

    def initDosingDrive(self):
        self.initialized = True

    def moveZDrive(self, pos, speed):
        if pos > self.maxZPosition or pos < self.minZPosition:
            raise ValueError(
                "requested z-position out of range. Valid range for z-position is between {} and {}".format(
                    self.minZPosition, self.maxZPosition))
        if speed not in ("slow", "fast"):
            raise ValueError(
                "invalid z-axis drive speed specified. Accepted values for z-axis drive speed are 'slow' and 'fast'.")
        self.pos = pos

    def pickUpTip(self, tipTypeTableIndex, deckGeometryTableIndex):
        self.tip_type = tipTypeTableIndex
        self.deck_geometry = deckGeometryTableIndex

    def discardTip(self, deckGeometryTableIndex):
        self.tip_type = None
        self.deck_geometry = deckGeometryTableIndex

    def aspiration(self, aspirationVolume=0, containerGeometryTableIndex=0,
                   deckGeometryTableIndex=0, liquidClassTableIndex=0, qpm=0,
                   lld=0, lldSearchPosition=0, liquidSurface=0, mixVolume=0,
                   mixFlowRate=0, mixCycles=0):
        self.aspirated_volume = aspirationVolume
        self.deck_geometry = deckGeometryTableIndex

    def dispensing(self, dispensingVolume=0, containerGeometryTableIndex=0,
                   deckGeometryTableIndex=0, qpm=0, liquidClassTableIndex=0,
                   lld=0, lldSearchPosition=0, liquidSurface=0,
                   searchBottomMode=0, mixVolume=0, mixFlowRate=0, mixCycles=0):
        self.dispensed_volume = dispensingVolume
        self.deck_geometry = deckGeometryTableIndex

    def setEmergencyStop(self, state):
        if state in set([1, "on", "ON", "True", "true"]):
            self.emergency_stop_active = True
        elif state in set([0, "off", "OFF", "False", "false"]):
            self.emergency_stop_active = False
        else:
            raise ValueError("state must be an on/off value")
