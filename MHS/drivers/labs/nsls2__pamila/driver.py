"""OpenMHS driver for gh.nsls2/pamila: a read-only middle-layer variable list.

The selected upstream class is ``pamila.middle_layer.var_list:MiddleLayerVariableListRO``
(``src/pamila/middle_layer/var_list.py:569``).  A PAMILA "MLVL" is a named, ordered collection of middle-layer
variables (MLVs) over a facility configuration; it reads the enabled members and can enable or disable members
locally.  The read-only subclass refuses every value write with ``ReadOnlyError``
(``src/pamila/middle_layer/var_list.py:582-592``).

* reads: the member count and names, the enabled member names and status, and the enabled values with their
  representation units;
* ``cap.sensing.read.v1``: the enabled values, optionally selected by member name.

The package is read only and data only (risk R0, changed by the model review).  The author's version served the
local enabled-status write as ``cap.device.configure.v1`` and the list's parallel-get switch (``var_list.py:170-176``)
as two extension actions, and bound ``disable_parallel_get`` as the e-stop to meet the R1 floor of the card.  That
switch only selects how member PVs are read; it stops nothing, so it is not a stop.  The model review removed the
write, the two actions and the e-stop: the list writes nothing to the machine (its put, set and set_and_wait raise
``ReadOnlyError``, ``var_list.py:582-592``), an e-stop is the endpoint's software latch, and the card's R1 floor
(from the scan's ``cap.device.configure.v1``, which this class cannot serve) needs a capability-class override to
``cap.sensing.read.v1`` before the gate passes (G3.RISK_FLOOR until then).

DEVIATION FROM THE CARD: the card's helper is ``OphydDriver``, but the entry class is not an ophyd Device and
declares no ``Component`` signals, so ``OphydDriver``'s signal bindings cannot express it.  This is a direct
``Driver`` over the selected entry class; the suggested ``set_and_wait`` methods of the read-only class raise
``ReadOnlyError`` and are not exposed.

Units: the clone does not fix an engineering unit for an MLV.  ``facility_configs/loader.py:96-103`` builds each
conversion from the ``repr_units`` of the deployment's element definition, so the unit is deployment data.  The
``value_units`` read reports the unit of each enabled value as the upstream quantity carries it; the ``values``
read returns the magnitudes in those units.

Every Fact cites the clone at the pinned commit 62a439b6be7cb72353575183a7fea26b45a35394.  This package is
model-authored and unreviewed (``reviewed_by`` is null); it is checked on the fake backend only and no hardware
backend has ever run.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, action, read

SOURCE = "src/pamila/middle_layer/var_list.py"


def _split_quantities(values):
    """``[(magnitude, unit)]`` for a quantity array, a list of quantities or plain numbers.

    The upstream ``get`` tries ``Q_.from_list`` and keeps the list when the members have different dimensions
    (``src/pamila/middle_layer/var_list.py:417-420``), so both shapes are possible.  A plain number carries no unit;
    the driver reports ``"1"`` for it and never invents a scale.
    """
    if values is None:
        return []
    if hasattr(values, "m") and hasattr(values, "units"):
        unit = str(values.units)
        raw = values.m
        try:
            magnitudes = list(raw)
        except TypeError:
            magnitudes = [raw]
        return [(float(magnitude), unit) for magnitude in magnitudes]
    out = []
    for value in values:
        if hasattr(value, "m") and hasattr(value, "units"):
            out.append((float(value.m), str(value.units)))
        else:
            out.append((float(value), "1"))
    return out


class PamilaVariableListRO(Driver):
    device_id = "pamila-variable-list"
    device_kind = "sensor"
    mode = "hardware"
    risk = "R0"
    native = "pamila.middle_layer.var_list:MiddleLayerVariableListRO"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeMiddleLayerVariableListRO"}
    vendor, model = "nsls2", "PAMILA MiddleLayerVariableListRO"
    display_name = "PAMILA read-only middle-layer variable list"
    tags = ["pamila", "bluesky", "ophyd", "middle-layer", "epics", "sensor", "read-only-list"]
    safe_state = ("unchanged: the package only reads the enabled middle-layer variables and writes nothing to the "
                  "machine or to the list; an e-stop latches the endpoint against further commands and stops nothing "
                  "physical")
    facts = [
        Fact("MiddleLayerVariableListBase is the common base of the read-only and writable variable lists",
             source="upstream_code", ref=f"{SOURCE}:116"),
        Fact("MiddleLayerVariableListRO sets read_only to True and is constructed from a "
             "MiddleLayerVariableListROSpec", source="upstream_code", ref=f"{SOURCE}:569-574"),
        Fact("MiddleLayerVariableListRO.put, set, set_and_wait and change_set_wait_method raise ReadOnlyError",
             source="upstream_code", ref=f"{SOURCE}:582-592"),
        Fact("get_all_mlv_count returns the number of all member variables", source="upstream_code",
             ref=f"{SOURCE}:460-461"),
        Fact("get_all_mlv_names returns the names of all member variables", source="upstream_code",
             ref=f"{SOURCE}:463-464"),
        Fact("get_mlv_names returns a copy of the enabled variable names", source="upstream_code",
             ref=f"{SOURCE}:466-467"),
        Fact("get_enabled_mlvs refreshes the enabled status and returns the enabled member variables",
             source="upstream_code", ref=f"{SOURCE}:261-263"),
        Fact("get_enabled_status returns a deep copy of the enabled-status list", source="upstream_code",
             ref=f"{SOURCE}:319-320"),
        Fact("put_enabled_status requires one status per member, returns when unchanged, and otherwise replaces "
             "the status list and reinitializes the enabled members", source="upstream_code",
             ref=f"{SOURCE}:322-336"),
        Fact("get reads every enabled member variable and tries to build one quantity array, leaving the list when "
             "the dimensions differ", source="upstream_code", ref=f"{SOURCE}:352-428"),
        Fact("enable_parallel_get and disable_parallel_get set the list flag and propagate it to the member PV "
             "objects", source="upstream_code", ref=f"{SOURCE}:170-176"),
        Fact("The list starts with one True enabled status per member variable", source="upstream_code",
             ref=f"{SOURCE}:144"),
        Fact("The read-only list spec carries the member variables and a parallel_get_enabled flag",
             source="upstream_code", ref=f"{SOURCE}:105-113"),
        Fact("A machine unit conversion is built from the repr_units of the deployment element definition",
             source="upstream_code", ref="src/pamila/facility_configs/loader.py:96-103"),
        Fact("A PAMILA device spec carries its components and its get and put action specs", source="upstream_code",
             ref="src/pamila/device/base.py:32-40"),
        Fact("The PAMILA machine module requires the PAMILA_FACILITY environment variable at import",
             source="upstream_code", ref="src/pamila/machine.py:8-13"),
        Fact("The MLVL example loads a machine configuration from examples/demo_generated/<facility>",
             source="upstream_code", ref="examples/nb_gen/03_mlvl.py:23"),
    ]

    # -- reads -------------------------------------------------------------------------------------------------
    @read("mlv_count", type="integer", unit="1",
          description="Number of middle-layer variables in the list, including disabled members")
    def mlv_count(self):
        return int(self.native.get_all_mlv_count())

    @read("mlv_names", type="array", items="string",
          description="Names of every middle-layer variable in the list, including disabled members")
    def mlv_names(self):
        return list(self.native.get_all_mlv_names())

    @read("enabled_mlv_names", type="array", items="string",
          description="Names of the enabled middle-layer variables, in list order")
    def enabled_mlv_names(self):
        return list(self.native.get_mlv_names())

    @read("enabled_status", type="array", items="boolean",
          description="One enabled flag per middle-layer variable, in list order")
    def enabled_status(self):
        return list(self.native.get_enabled_status())

    @read("values", type="array", items="number",
          description="Current values of the enabled middle-layer variables, in list order and in the "
                      "representation units reported by value_units")
    def values(self):
        return [magnitude for magnitude, _unit in _split_quantities(self.native.get(return_flat=True))]

    @read("value_units", type="array", items="string",
          description="Representation unit of each enabled value, in list order; the deployment facility "
                      "configuration supplies it")
    def value_units(self):
        return [unit for _magnitude, unit in _split_quantities(self.native.get(return_flat=True))]

    # -- capabilities ------------------------------------------------------------------------------------------
    @action(cap="cap.sensing.read.v1",
            description="Read the current values of the enabled middle-layer variables, optionally selected by "
                        "name; values are magnitudes in the units reported by the value_units state field",
            input={"fields": Field(
                "array", items="string",
                description="Member names to return; omit the input to return every enabled member")})
    def read_channels(self, fields=None):
        names = list(self.native.get_mlv_names())
        groups = self.native.get(return_flat=False)
        if len(names) != len(groups):
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               f"the list returned {len(groups)} member results for {len(names)} enabled names")
        if fields is None:
            wanted = set(names)
        else:
            wanted = set(fields)
            unknown = sorted(wanted - set(names))
            if unknown:
                raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                                   f"not an enabled middle-layer variable: {', '.join(unknown)}")
        values = {}
        for name, group in zip(names, groups):
            if name not in wanted:
                continue
            pairs = _split_quantities(group)
            if len(pairs) == 1:
                values[name] = pairs[0][0]
            else:
                values[name] = [magnitude for magnitude, _unit in pairs]
        return {"values": values}
