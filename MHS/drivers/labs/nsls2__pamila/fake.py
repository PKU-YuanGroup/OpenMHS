"""Fake backend of the PAMILA read-only middle-layer variable list.

The upstream class (``src/pamila/middle_layer/var_list.py:569``) is constructed from a
``MiddleLayerVariableListROSpec`` over middle-layer variables and exposes the methods this fake implements:
``get_all_mlv_count``, ``get_all_mlv_names``, ``get_mlv_names``, ``get_enabled_mlvs``, ``get_enabled_status``,
``put_enabled_status``, ``get``, ``enable_parallel_get`` and ``disable_parallel_get``.  Nothing here imports
``pamila``, ``ophyd``, ``pint`` or opens an EPICS connection.

The three member variables and every value and unit are placeholders chosen for the tests, not facts about any
machine; the real list is configured from a facility configuration and its names and units are deployment data.
The values are held in a list, as the upstream ``get`` keeps a list when the member dimensions differ
(``src/pamila/middle_layer/var_list.py:417-420``).
"""


class _FakeQuantity:
    """The magnitude and unit a real PAMILA read returns as a pint quantity."""

    def __init__(self, magnitude, unit):
        self.m = magnitude
        self.units = unit


class _FakeMLV:
    """One member variable: its name, magnitude and representation unit (all placeholders)."""

    def __init__(self, name, magnitude, unit):
        self.name = name
        self.magnitude = magnitude
        self.unit = unit


class FakeMiddleLayerVariableListRO:
    def __init__(self, **_options):
        self._all_mlvs = [
            _FakeMLV("PLACEHOLDER_MLV_A", 1.5, "A"),   # placeholder
            _FakeMLV("PLACEHOLDER_MLV_B", 2.5, "m"),   # placeholder
            _FakeMLV("PLACEHOLDER_MLV_C", 3.5, "1"),   # placeholder
        ]
        self._status = [True] * len(self._all_mlvs)
        self._parallel_get_enabled = True

    def get_all_mlv_count(self):
        return len(self._all_mlvs)

    def get_all_mlv_names(self):
        return [mlv.name for mlv in self._all_mlvs]

    def get_enabled_mlvs(self):
        return [mlv for mlv, enabled in zip(self._all_mlvs, self._status) if enabled]

    def get_mlv_names(self):
        return [mlv.name for mlv in self.get_enabled_mlvs()]

    def get_enabled_status(self):
        return list(self._status)

    def put_enabled_status(self, new_status_list):
        assert len(new_status_list) == self.get_all_mlv_count()
        if all(new == current for new, current in zip(new_status_list, self._status)):
            return
        self._status = list(new_status_list)

    def get(self, return_flat=True):
        return [_FakeQuantity(mlv.magnitude, mlv.unit) for mlv in self.get_enabled_mlvs()]

    def enable_parallel_get(self):
        self._parallel_get_enabled = True

    def disable_parallel_get(self):
        self._parallel_get_enabled = False
