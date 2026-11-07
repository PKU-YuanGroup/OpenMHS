"""Hardware backend: opens the upstream HamiltonInterface and adapts plain labware names to its deck objects.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed, and it is R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json (the loader does this at R2 and R3 only; an R0 or R1 package must not claim it).  The acceptance
gate runs the fake backend and never imports this module or pyhamilton.

The upstream package only works on Windows with the Hamilton Venus/OEM software installed (README.md:5, 39), and
HamiltonInterface expects its STAR-OEM files beside the package (pyhamilton/__init__.py:13-17).  Options are the
constructor options of HamiltonInterface: ``address``, ``port``, ``simulating``, ``windowed``, ``server_mode``,
``persistent`` and ``debug`` (pyhamilton/interface.py:527).  ``simulating=True`` is not a robot simulator: it only
logs the commands instead of sending them (pyhamilton/interface.py:596-598, 730-733); use the fake backend for a dry
run.

The adapter takes the layout name and the well identifier of the driver actions and builds a ``Plate96``
(pyhamilton/resources/deckresource.py:513-520) for the upstream ``aspirate``/``dispense`` call, which expects
``(labware, index)`` tuples (pyhamilton/interface.py:886-890, 948-952).  This package therefore drives 96-well
labware only; 384-well, 24-well and other deck resources are not covered.
"""


class HamiltonDeck:
    """The upstream HamiltonInterface with plain-name labware positions for one 96-well plate at a time."""

    def __init__(self, interface, plate_type):
        self._interface = interface
        self._plate_type = plate_type
        self._plates = {}

    @property
    def server_thread(self):
        return self._interface.server_thread

    def start(self):
        self._interface.start()

    def stop(self):
        self._interface.stop()

    def is_open(self):
        return self._interface.is_open()

    def initialize(self, **more_options):
        return self._interface.initialize(**more_options)

    def aspirate(self, pos_tuples, vols, **more_options):
        return self._interface.aspirate([self._position(item) for item in pos_tuples], list(vols),
                                        **more_options)

    def dispense(self, pos_tuples, vols, **more_options):
        return self._interface.dispense([self._position(item) for item in pos_tuples], list(vols),
                                        **more_options)

    def move_by_seq(self, source_plate_seq, target_plate_seq, **more_options):
        return self._interface.move_by_seq(source_plate_seq, target_plate_seq, **more_options)

    def set_labware_property(self, labware_id, property_name, property_value):
        return self._interface.set_labware_property(labware_id, property_name, property_value)

    def _position(self, item):
        if not isinstance(item, tuple) or len(item) != 2:
            raise ValueError(f"expected a (labware, well) pair, got {item!r}")
        labware, well = item
        plate = self._plates.get(labware)
        if plate is None:
            plate = self._plate_type(labware)
            self._plates[labware] = plate
        return plate, self._well_index(plate, well)

    @staticmethod
    def _well_index(plate, well):
        wanted = str(well).strip().upper()
        index = 0
        while True:
            try:
                if plate.position_id(index).upper() == wanted:
                    return index
            except ValueError:
                break
            index += 1
        raise ValueError(f"well {well!r} is not a position of labware {plate.layout_name()!r}")


def connect(**options):
    from pyhamilton.interface import HamiltonInterface
    from pyhamilton.resources.deckresource import Plate96

    return HamiltonDeck(HamiltonInterface(**options), Plate96)
