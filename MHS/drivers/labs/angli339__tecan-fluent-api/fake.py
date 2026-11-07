"""Fake backend of the Tecan Fluent driver: an in-memory stand-in for tecan_fluent.tecan_ctrl:Tecan.

Gate G7: every public method defined here exists on the upstream class (tecan_fluent/tecan_ctrl.py:52-172), and the
two other attributes the driver reaches, ``rt`` and ``ch``, are set by the upstream __init__
(tecan_fluent/tecan_ctrl.py:26-28).  The fake imports nothing from the clone and does no .NET call.  All values below
are test data, not device facts: the status words, the channel object and the recorded call list are placeholders
written only so the driver can be exercised.  Nothing here talks to a device.

The fake keeps the upstream precondition: ``run_command`` raises RuntimeError when ``self.ch`` is None
(tecan_fluent/tecan_ctrl.py:41-44), so the action methods raise the same error once the stop has detached the
channel.
"""


class _FakeRuntime:
    """The RuntimeController object the upstream keeps in ``self.rt`` (tecan_fluent/tecan_ctrl.py:26)."""

    def __init__(self):
        self.status = "Idle"            # placeholder status word

    def GetFluentStatus(self):
        return self.status

    def StopMethod(self):
        self.status = "Stopped"         # placeholder status word


class FakeTecan:
    """An in-memory Tecan object with the public surface the driver uses."""

    def __init__(self, **_options):
        self.rt = _FakeRuntime()
        self.ch = object()              # placeholder: an attached Execution Channel
        self.actuations = []            # placeholder record of the commands the driver sent

    def _require_channel(self):
        if self.ch is None:
            raise RuntimeError("API channel is not open")

    def liha_aspirate(self, volumes, i_selected_tips, labware, i_selected_wells, liquid_class,
                      is_switch_container_source_enabled=False):
        self._require_channel()
        self.actuations.append(("liha_aspirate", list(volumes), list(i_selected_tips), labware,
                                list(i_selected_wells), liquid_class))

    def liha_dispense(self, volumes, i_selected_tips, labware, i_selected_wells, liquid_class):
        self._require_channel()
        self.actuations.append(("liha_dispense", list(volumes), list(i_selected_tips), labware,
                                list(i_selected_wells), liquid_class))

    def liha_mix(self, n_cycles, volumes, i_selected_tips, labware, i_selected_wells, liquid_class):
        self._require_channel()
        self.actuations.append(("liha_mix", n_cycles, list(volumes), list(i_selected_tips), labware,
                                list(i_selected_wells), liquid_class))

    def mca_aspirate(self, volume, labware, liquid_class):
        self._require_channel()
        self.actuations.append(("mca_aspirate", volume, labware, liquid_class))

    def mca_dispense(self, volume, labware, liquid_class):
        self._require_channel()
        self.actuations.append(("mca_dispense", volume, labware, liquid_class))
