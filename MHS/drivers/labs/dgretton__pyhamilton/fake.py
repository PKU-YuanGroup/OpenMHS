"""Fake backend of the pyhamilton driver: an in-memory stand-in for pyhamilton.interface:HamiltonInterface.

Gate G7: every public method defined here exists on ``pyhamilton.interface:HamiltonInterface`` -- ``start``,
``stop``, ``is_open``, ``initialize``, ``aspirate``, ``dispense``, ``move_by_seq`` and ``set_labware_property``
(pyhamilton/interface.py:578, 619, 692, 868, 886, 948, 1335, 1241).  The ``server_thread`` attribute is set by the
upstream ``__init__`` (pyhamilton/interface.py:536) and its real class has ``has_exited``
(pyhamilton/interface.py:489-498), which the driver reads.  Like the upstream methods, ``aspirate`` and ``dispense``
return an object carrying ``liquidVolumes`` (pyhamilton/interface.py:930-944); the fake echoes the volume it was
asked to move, which is test data, not a device measurement.  ``initialize``, ``aspirate`` and ``dispense`` accept
calls while the fake interface is stopped, unlike the real ``send_command``, so the runtime's e-stop latch and reset
can be exercised; this is a deliberate fidelity gap.  Nothing here talks to a device.
"""


class _FakeServerThread:
    """The local server thread object a real HamiltonInterface owns."""

    def __init__(self):
        self.exited = False

    def has_exited(self):
        return self.exited


class _Result:
    """The part of the upstream AspirateResult/DispenseResult the driver reads."""

    def __init__(self, volume):
        self.liquidHeights = []
        self.liquidVolumes = [float(volume)]
        self.raw = None


class FakeHamiltonInterface:
    def __init__(self, **_options):
        self.active = False
        self.server_thread = _FakeServerThread()
        self.initialized = False
        self.calls = []

    # -- lifecycle ------------------------------------------------------------------
    def start(self):
        self.active = True
        self.server_thread.exited = False

    def stop(self):
        self.active = False
        self.server_thread.exited = True

    def is_open(self):
        return self.active

    # -- commands -------------------------------------------------------------------
    def initialize(self, **more_options):
        self.calls.append(("initialize", more_options))
        self.initialized = True
        return None

    def aspirate(self, pos_tuples, vols, **more_options):
        self.calls.append(("aspirate", pos_tuples, vols, more_options))
        return _Result(vols[0])

    def dispense(self, pos_tuples, vols, **more_options):
        self.calls.append(("dispense", pos_tuples, vols, more_options))
        return _Result(vols[0])

    def move_by_seq(self, source_plate_seq, target_plate_seq, **more_options):
        self.calls.append(("move_by_seq", source_plate_seq, target_plate_seq, more_options))
        return None

    def set_labware_property(self, labware_id, property_name, property_value):
        self.calls.append(("set_labware_property", labware_id, property_name, property_value))
        return None
