"""Fake backend of the scanning SQUID microscope: an in-memory ``SusceptometerMicroscope`` with two components.

``FakeSusceptometerMicroscope`` has the two Microscope attributes the driver uses, ``atto`` and ``scanner``
(set by ``_add_atto`` and ``_add_scanner``, microscope/microscope.py:132, 169).  ``atto`` mirrors the members of
``instruments.atto.ANC300`` the driver reaches: ``axes`` (atto.py:59), the QCoDeS ``parameters`` table with the
``mode_ax<n>`` parameters (70-79; a fake parameter with ``get``/``set``), ``stop`` (143-152), ``step`` (154-177) and
``_parse_axis`` (185-209).  ``scanner`` has ``get_pos`` (scanner.py:109-131).  Nothing here opens a VISA session or a
DAQ task, and ``step`` does not wait: the upstream sleeps abs(steps)/frequency*1.25 s (atto.py:172).

``step`` records its ``stepu``/``stepd`` command twice, as the upstream writes it (``ask``, atto.py:169, through the
class's ``ask_raw``, which sends every command twice, 109-124), but it counts the requested steps once.  That count is a
placeholder and a gap of this fake: the source does not show what the ANC300 does with the second copy, so the fake
says nothing about the steps a command makes.  (A hardware driver's fake view carries the SDK's fixed fake fidelity
contract, so this gap is stated here and in RESULT.json, not in a fidelity object.)

The axis map is the example configuration's (docs/examples/config_susceptometer.json:49); the scanner position and
the step bookkeeping are placeholders, not device facts.
"""

from __future__ import annotations


class _FakeParameter:
    """A QCoDeS Parameter's get and set, as the upstream calls them (atto.py:278, 312-314)."""

    def __init__(self, value):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value


class _FakeANC300:
    def __init__(self):
        self.axes = {"x": 1, "y": 2, "z": 3}            # docs/examples/config_susceptometer.json:49
        self.parameters = {f"mode_ax{index}": _FakeParameter("gnd") for index in self.axes.values()}
        self._commands = []                              # wire commands the upstream would write, for the tests
        self._steps = {axis: 0 for axis in self.axes}    # placeholder step bookkeeping

    def _parse_axis(self, axis):
        """atto.py:185-209 for a label (the driver passes labels)."""
        if not isinstance(axis, str):
            raise ValueError("axis of type str or int.")
        index = self.axes[axis]
        return axis, index

    def stop(self, axis):
        axis, index = self._parse_axis(axis)
        self._commands.append(f"stop {index}")                       # atto.py:151
        self.parameters[f"mode_ax{index}"].set("gnd")                # atto.py:152 (setm n gnd)

    def step(self, axis, steps):
        axis, index = self._parse_axis(axis)
        if not isinstance(steps, int):
            raise ValueError("steps must be an integer.")              # atto.py:163-164
        self.parameters[f"mode_ax{index}"].set("stp")                # atto.py:167
        direction = "u" if steps > 0 else "d"
        command = f"step{direction} {index} {abs(steps)}"            # atto.py:168-169
        self._commands.append(command)                               # ask_raw writes it once (atto.py:120)
        self._commands.append(command)                               # and again (atto.py:121)
        self._commands.append(f"stepw {index}")                      # atto.py:170
        self._steps[axis] += steps                                   # placeholder: counted once; no wait, no physics
        self.parameters[f"mode_ax{index}"].set("gnd")                # atto.py:173


class _FakeScanner:
    def __init__(self):
        self._position = [0.0, 0.0, -1.0]                # placeholder voltages

    def get_pos(self):
        return list(self._position)


class FakeSusceptometerMicroscope:
    def __init__(self, **_options):
        self.atto = _FakeANC300()
        self.scanner = _FakeScanner()
