"""Fake backend of the Newport XPS driver: an in-memory stand-in for newportxps.newportxps:NewportXPS.

Gate G7: every public method defined here is a method of
``newportxps.newportxps:NewportXPS`` in the clone, with the same call shape the
driver uses: ``get_group_status``, ``get_hardware_status``,
``get_positioner_errors``, ``get_stage_position``, ``get_tuning``,
``move_stage``, ``home_group``, ``enable_group``, ``disable_group``,
``abort_group`` and ``disconnect`` (newportxps/newportxps.py:612-767, 570-610,
685-693, 132-136).  The class keeps the same ``groups``, ``stages`` and
``trajectories`` instance attributes as the upstream constructor
(newportxps/newportxps.py:53-84).

Everything below is placeholder test data, not a fact about an XPS and not a
recording: the group and stage names, their status texts, the start position
and the tuning gains all depend on the controller's system.ini/stages.ini and
on the installed stages.  The object never opens a socket or an FTP
connection; a move is applied immediately so a position read after the move
shows the new value.  The native methods return the same shapes the upstream
methods return: dictionaries keyed by group/stage, a position value, and the
tuning dictionary of twelve keys (newportxps/newportxps.py:422-442).
"""

_TUNING_KEYS = ("closedloopstatus", "kp", "ki", "kd", "ks", "inttime", "dfilter",
                "gkp", "gki", "gkd", "kform", "ffgain")


class FakeNewportXPS:
    def __init__(self, **_options):
        # The names and the shape of these dictionaries follow read_systemini (newportxps/newportxps.py:204-256);
        # the values are placeholders for one single-axis group on a test bench.
        self.groups = {"SampleX": {"category": "SingleAxisInUse", "positioners": ["Pos"]}}   # placeholder
        self.stages = {"SampleX.Pos": {"stagetype": "fake stage"}}                           # placeholder
        self.trajectories = {}                                                               # placeholder
        self.traj_group = "SampleX"                                                          # placeholder
        self.firmware_version = "XPS-D fake"                                                 # placeholder
        self._connected = True
        self._positions = {"SampleX.Pos": 0.0}                                               # placeholder
        self._group_status = {"SampleX": "Ready state from motion"}                          # placeholder
        self._hardware_status = {"SampleX.Pos": "First driver powered on"}                   # placeholder
        self._positioner_errors = {"SampleX.Pos": "OK"}                                      # placeholder
        self._enabled = {"SampleX": True}                                                    # placeholder
        self._tuning = {"SampleX.Pos": dict.fromkeys(
            _TUNING_KEYS, 0.0)}                                                              # placeholder
        self._tuning["SampleX.Pos"]["closedloopstatus"] = 1.0                                # placeholder
        self._stop_calls = 0

    # -- helpers (private: not part of the upstream surface) ---------------------------------------------------
    def _group_of(self, stage):
        return stage.rpartition(".")[0]

    def _groups(self, group):
        if group is None:
            return list(self.groups)
        return [group]

    # -- state reads ------------------------------------------------------------------------------------------
    def get_group_status(self):
        return dict(self._group_status)

    def get_hardware_status(self):
        return dict(self._hardware_status)

    def get_positioner_errors(self):
        return dict(self._positioner_errors)

    def get_stage_position(self, stage):
        if stage not in self.stages:
            raise ValueError(f"stage {stage!r} is not configured")
        return self._positions[stage]

    def get_tuning(self, stage):
        if stage not in self.stages:
            return None
        return dict(self._tuning[stage])

    # -- actions ----------------------------------------------------------------------------------------------
    def move_stage(self, stage, value, relative=False):
        if stage not in self.stages:
            raise ValueError(f"stage {stage!r} is not configured")
        if relative:
            self._positions[stage] += float(value)
        else:
            self._positions[stage] = float(value)
        self._group_status[self._group_of(stage)] = "Ready state from motion"                # placeholder
        return [self._positions[stage]]

    def home_group(self, group, with_raise=True):
        if group not in self.groups:
            raise ValueError(f"group {group!r} is not configured")
        for positioner in self.groups[group]["positioners"]:
            self._positions[f"{group}.{positioner}"] = 0.0                                   # placeholder
        self._group_status[group] = "Ready from home search"                                 # placeholder

    def enable_group(self, group=None):
        for name in self._groups(group):
            self._enabled[name] = True
            self._group_status[name] = "Ready state from motion"                             # placeholder

    def disable_group(self, group=None):
        for name in self._groups(group):
            self._enabled[name] = False
            self._group_status[name] = "Disabled state"                                      # placeholder

    def abort_group(self, group=None):
        target = group if group is not None else self.traj_group
        if target is not None:
            self._group_status[target] = "Ready state from motion"                           # placeholder
        self._stop_calls += 1

    def disconnect(self):
        self._connected = False
