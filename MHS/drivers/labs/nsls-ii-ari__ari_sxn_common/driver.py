"""OpenMHS driver for gh.nsls-ii-ari/ari_sxn_common: the ARI M1 mirror-section devices, read only.

DEVIATION FROM THE CARD: the card proposes the config-only ``OphydDriver`` family helper with
``ari_sxn_common.ari_ophyd:M1`` as the entry class.  ``M1`` is an Ophyd ``Device``, but every member this package
serves is a nested custom Device or a custom ``EpicsMotor`` subclass, not one of the direct
``Component(EpicsSignal | EpicsSignalRO | Signal, "literal")`` declarations the Ophyd source proof accepts.  The
``M1`` motors are ``Component(ID29EpicsMotor, ...)`` (ari_ophyd.py:97-106), ``ID29EpicsMotor`` is a subclass of
``EpicsMotor`` (common_ophyd.py:116), the vacuum sub-device is ``_VacuumDevices`` / ``_AriSxnC`` (ari_ophyd.py:9-35),
``slits`` is a ``BaffleSlit`` and ``diag`` is a ``Diagnostic`` (ari_ophyd.py:112-140).  This package is therefore a
direct ``Driver`` over the confirmed entry symbol, with a ``native.py`` factory.

The package preserves the card's primary scope read-only: it publishes the live mirror-axis, baffle-slit blade,
diagnostic blade/filter, diagnostic current, baffle-slit current and vacuum-gauge readings and the parent's
current-location signal, and one observational capability that reads the M1 photocurrent (the
``diag.currents.current1.mean_value`` Signal that ``M1.__init__`` exposes as ``photocurrent``, ari_ophyd.py:86-94).  It
deliberately exposes no motor or slit setpoint: the card lists no write, and the clone states no travel bound, so an
operator envelope cannot be sourced here.  Motor movement and slit movement are therefore not covered.

NOT COVERED (model review, 2026-11-05): ``M1.trigger()``.  The author served it as the package's only capability, but
it triggers the ``BaffleSlit`` and ``Diagnostic`` children (ari_ophyd.py:142-155), whose ``currents`` are ``ID29EM``
(an ophyd ``NSLS_EM``, common_ophyd.py:180) and whose camera is ``Prosilica`` with ophyd's ``SingleTrigger`` mixin
(common_ophyd.py:245, 673-688, 763-771).  Those trigger implementations live in ophyd, outside the clone, and the
package never stages the Device; classic ophyd's ``SingleTrigger`` refuses a trigger on an unstaged detector, so the
served action could not be expected to work live, while the fake's trigger always returned a done status.  Staging
would also change the camera's and electrometer's acquisition settings on a running beamline.

Every reading is taken through the native classic Ophyd Signal API: ``user_readback.get(use_monitor=False)`` for the
custom ``ID29EpicsMotor`` members (whose ``user_readback`` is named at common_ophyd.py:147), ``.get(use_monitor=False)``
for the ``ID29EpicsSignalRO`` vacuum gauges and for the ``mean_value`` currents.  ``locations.get()`` runs the
upstream ``LocationSignal.get`` (common_ophyd.py:433-516), which evaluates the parent's configured locations and
returns the tuple of location flags.

The clone states no engineering unit for any motor, current or vacuum record, so no field carries a unit.  The
package is model-authored and unreviewed (``reviewed_by`` is null); it has run on the fake backend only and has
never connected to an EPICS IOC.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, action, read

#: The observational photocurrent capability (model review): no catalogue read class fits an optics.mirror device.
PHOTOCURRENT = "x-cap.nsls-ii-ari.m1_photocurrent.v1"

#: The pinned source files used by the facts and the interface.
SOURCE = "src/ari_sxn_common/ari_ophyd.py"
COMMON = "src/ari_sxn_common/common_ophyd.py"


def _number(signal):
    """Read a native Ophyd Signal freshly and return its value."""
    return signal.get(use_monitor=False)


def _positions(signal):
    """Read one ``ID29EpicsMotor`` readback freshly."""
    return signal.user_readback.get(use_monitor=False)


class AriM1Section(Driver):
    device_id = "ari-m1-section"
    device_kind = "optics.mirror"
    mode = "hardware"
    risk = "R0"
    native = "ari_sxn_common.ari_ophyd:M1"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeM1"}
    vendor = "NSLS-II ARI/SXN"
    model = "M1 mirror section (ARI M1)"
    display_name = "ARI M1 mirror section (ari_sxn_common, read only)"
    tags = ["ophyd", "bluesky", "epics", "nsls-ii", "ari", "mirror", "baffle-slit", "diagnostic", "read-only"]
    safe_state = ("unchanged: the package only reads native Signals; it serves no trigger, motor, slit, shutter or "
                  "camera command and declares no native stop")

    facts = [
        Fact("M1 is the ophyd Device for the ARI M1 mirror section and extends DeviceWithLocations",
             source="upstream_code", ref=f"{SOURCE}:38"),
        Fact("M1 declares the five mirror motor Components Ry_coarse, Ry_fine, Rz, x and y as ID29EpicsMotor",
             source="upstream_code", ref=f"{SOURCE}:97-106"),
        Fact("M1 declares vacuum as _VacuumDevices, slits as BaffleSlit and diag as Diagnostic",
             source="upstream_code", ref=f"{SOURCE}:108-140"),
        Fact("M1.trigger calls the parent trigger, the slits trigger and the diag trigger, and returns their "
             "combined status", source="upstream_code", ref=f"{SOURCE}:142-155"),
        Fact("ID29EpicsMotor is a subclass of ophyd EpicsMotor", source="upstream_code", ref=f"{COMMON}:116"),
        Fact("ID29EpicsMotor.__init__ sets the kind of user_setpoint and of user_readback", source="upstream_code",
             ref=f"{COMMON}:146-147"),
        Fact("ID29EpicsSignalRO is a subclass of ophyd EpicsSignalRO", source="upstream_code", ref=f"{COMMON}:154"),
        Fact("_AriSxnC declares ccg, tcg and ip as ID29EpicsSignalRO and gv as ID29TwoButtonShutter",
             source="upstream_code", ref=f"{SOURCE}:16-23"),
        Fact("BaffleSlit declares top, bottom, inboard and outboard as ID29EpicsMotor and currents as ID29EM",
             source="upstream_code", ref=f"{COMMON}:751-761"),
        Fact("Diagnostic declares blade and filter as ID29EpicsMotor, camera as Prosilica and currents as ID29EM",
             source="upstream_code", ref=f"{COMMON}:661-671"),
        Fact("DeviceWithLocations declares locations as a Component of its own LocationSignal",
             source="upstream_code", ref=f"{COMMON}:590-591"),
        Fact("LocationSignal.get evaluates the parent's configured locations and puts the matching flags at read "
             "time", source="upstream_code", ref=f"{COMMON}:509-516"),
        Fact("BaffleSlit aliases the mean_value of currents.current1 through current4 as top, bottom, inboard and "
             "outboard", source="upstream_code", ref=f"{COMMON}:734-746"),
        Fact("Diagnostic exposes currents.current1 through current4 and their mean_value members",
             source="upstream_code", ref=f"{COMMON}:647-659"),
        Fact("M1.__init__ renames diag.currents.current1.mean_value to <name>_photocurrent, hints it and exposes it "
             "as the photocurrent attribute", source="upstream_code", ref=f"{SOURCE}:86-94"),
        Fact("ID29EM derives from NSLS_EM, imported from ophyd.quadem", source="upstream_code", ref=f"{COMMON}:180"),
        Fact("Prosilica combines SingleTrigger, imported from ophyd.areadetector.trigger_mixins, with "
             "ProsilicaDetector", source="upstream_code", ref=f"{COMMON}:245"),
        Fact("ID29EM.__init__ puts 'EM180' into the nd_array_port of current1 to current4 while it is constructed",
             source="upstream_code", ref=f"{COMMON}:212-224"),
        Fact("Diagnostic.trigger reads the camera array counter, then triggers the camera, the currents and the "
             "parent and combines their statuses", source="upstream_code", ref=f"{COMMON}:673-688"),
        Fact("BaffleSlit.trigger triggers the currents and the parent and combines their statuses",
             source="upstream_code", ref=f"{COMMON}:763-771"),
    ]

    # -- mirror axes -------------------------------------------------------------------------------------------
    @read("ry_coarse", description="Ry_coarse.user_readback, a fresh read of the coarse Ry mirror motor; the clone "
                                   "states no engineering unit")
    def ry_coarse(self):
        return _positions(self.native.Ry_coarse)

    @read("ry_fine", description="Ry_fine.user_readback, a fresh read of the fine Ry mirror motor; the clone states "
                                 "no engineering unit")
    def ry_fine(self):
        return _positions(self.native.Ry_fine)

    @read("rz", description="Rz.user_readback, a fresh read of the Rz mirror motor; the clone states no engineering "
                            "unit")
    def rz(self):
        return _positions(self.native.Rz)

    @read("x", description="x.user_readback, a fresh read of the x mirror motor; the clone states no engineering unit")
    def x(self):
        return _positions(self.native.x)

    @read("y", description="y.user_readback, a fresh read of the y mirror motor; the clone states no engineering unit")
    def y(self):
        return _positions(self.native.y)

    # -- baffle-slit blades ------------------------------------------------------------------------------------
    @read("slit_top", description="slits.top.user_readback, a fresh read of the top baffle-slit blade; the clone "
                                  "states no engineering unit")
    def slit_top(self):
        return _positions(self.native.slits.top)

    @read("slit_bottom", description="slits.bottom.user_readback, a fresh read of the bottom baffle-slit blade; the "
                                     "clone states no engineering unit")
    def slit_bottom(self):
        return _positions(self.native.slits.bottom)

    @read("slit_inboard", description="slits.inboard.user_readback, a fresh read of the inboard baffle-slit blade; "
                                      "the clone states no engineering unit")
    def slit_inboard(self):
        return _positions(self.native.slits.inboard)

    @read("slit_outboard", description="slits.outboard.user_readback, a fresh read of the outboard baffle-slit "
                                       "blade; the clone states no engineering unit")
    def slit_outboard(self):
        return _positions(self.native.slits.outboard)

    # -- diagnostic blade and filter ---------------------------------------------------------------------------
    @read("diag_blade", description="diag.blade.user_readback, a fresh read of the diagnostic blade motor; the "
                                    "clone states no engineering unit")
    def diag_blade(self):
        return _positions(self.native.diag.blade)

    @read("diag_filter", description="diag.filter.user_readback, a fresh read of the diagnostic filter motor; the "
                                     "clone states no engineering unit")
    def diag_filter(self):
        return _positions(self.native.diag.filter)

    # -- diagnostic currents -----------------------------------------------------------------------------------
    @read("diag_current1", description="diag.currents.current1.mean_value, a fresh read of diagnostic current 1; "
                                       "the clone states no engineering unit")
    def diag_current1(self):
        return _number(self.native.diag.currents.current1.mean_value)

    @read("diag_current2", description="diag.currents.current2.mean_value, a fresh read of diagnostic current 2; "
                                       "the clone states no engineering unit")
    def diag_current2(self):
        return _number(self.native.diag.currents.current2.mean_value)

    @read("diag_current3", description="diag.currents.current3.mean_value, a fresh read of diagnostic current 3; "
                                       "the clone states no engineering unit")
    def diag_current3(self):
        return _number(self.native.diag.currents.current3.mean_value)

    @read("diag_current4", description="diag.currents.current4.mean_value, a fresh read of diagnostic current 4; "
                                       "the clone states no engineering unit")
    def diag_current4(self):
        return _number(self.native.diag.currents.current4.mean_value)

    # -- baffle-slit currents ----------------------------------------------------------------------------------
    @read("slit_current1", description="slits.currents.current1.mean_value (aliased as top), a fresh read of "
                                       "baffle-slit current 1; the clone states no engineering unit")
    def slit_current1(self):
        return _number(self.native.slits.currents.current1.mean_value)

    @read("slit_current2", description="slits.currents.current2.mean_value (aliased as bottom), a fresh read of "
                                       "baffle-slit current 2; the clone states no engineering unit")
    def slit_current2(self):
        return _number(self.native.slits.currents.current2.mean_value)

    @read("slit_current3", description="slits.currents.current3.mean_value (aliased as inboard), a fresh read of "
                                       "baffle-slit current 3; the clone states no engineering unit")
    def slit_current3(self):
        return _number(self.native.slits.currents.current3.mean_value)

    @read("slit_current4", description="slits.currents.current4.mean_value (aliased as outboard), a fresh read of "
                                       "baffle-slit current 4; the clone states no engineering unit")
    def slit_current4(self):
        return _number(self.native.slits.currents.current4.mean_value)

    # -- vacuum gauges -----------------------------------------------------------------------------------------
    @read("vacuum_ccg", description="vacuum.AriSxnC.ccg, a fresh read of the cold-cathode gauge signal; the clone "
                                    "states no engineering unit")
    def vacuum_ccg(self):
        return _number(self.native.vacuum.AriSxnC.ccg)

    @read("vacuum_tcg", description="vacuum.AriSxnC.tcg, a fresh read of the thermocouple gauge signal; the clone "
                                    "states no engineering unit")
    def vacuum_tcg(self):
        return _number(self.native.vacuum.AriSxnC.tcg)

    @read("vacuum_ip", description="vacuum.AriSxnC.ip, a fresh read of the ion-pump gauge signal; the clone states "
                                   "no engineering unit")
    def vacuum_ip(self):
        return _number(self.native.vacuum.AriSxnC.ip)

    # -- locations ---------------------------------------------------------------------------------------------
    @read("locations", type="array", items=Field("string"),
          description="The location names where the parent's LocationSignal reports the section is currently "
                      "positioned; the names and their number come from the deployment's locations_data")
    def locations(self):
        value = self.native.locations.get()
        to_mapping = getattr(value, "_asdict", None)
        if callable(to_mapping):
            value = to_mapping()
        items = getattr(value, "items", None)
        if callable(items):
            return [str(name) for name, active in items() if active]
        if isinstance(value, (list, tuple, set)):
            return [str(name) for name in value]
        raise DriverFailed("MHS.DEVICE.FAULTED",
                           f"the native locations signal returned an unsupported value type {type(value).__name__}")

    # -- the observational capability (model review: replaces the unstaged M1.trigger) ---------------------------
    @action(name=PHOTOCURRENT, verb="read", risk="R0",
            description="Read the M1 photocurrent: a fresh get of diag.currents.current1.mean_value, the electrometer "
                        "statistics value M1 exposes as photocurrent; no unit is stated and its age depends on "
                        "whether the electrometer is acquiring",
            output={
                "photocurrent": Field("number", description="diag.currents.current1.mean_value; the clone states no "
                                                            "engineering unit"),
            })
    def read_photocurrent(self):
        return {"photocurrent": _number(self.native.diag.currents.current1.mean_value)}
