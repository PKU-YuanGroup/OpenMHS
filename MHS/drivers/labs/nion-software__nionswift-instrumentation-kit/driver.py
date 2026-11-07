"""OpenMHS driver for gh.nion-software/nionswift-instrumentation-kit: a Nion STEM instrument.

A direct Driver (decorated methods) over the upstream device class
``nion.device_kit.InstrumentDevice:Instrument``.  That class is the device-facing adapter of the Nion
instrumentation kit: it is constructed from an instrument id, a ``ValueManagerLike`` and an
``AxisManagerLike`` (nion/device_kit/InstrumentDevice.py:60-67) and it reads and writes every named
instrument control through those managers (InstrumentDevice.py:192-206).

* reads: the accelerating voltage (EHT), the defocus (C10), the energy offset (ZLPoffset) and the beam
  current (BeamCurrent);
* writes: the accelerating voltage, the defocus and the energy offset.  No text file of the clone states a
  range for any of them, so every write is ``Limit.operator_required``: it is refused
  ``MHS.SAFETY.LIMITS_UNSET`` until the site supplies the range of its instrument
  (``site-limits.example.json`` shows the overlay);
* the upstream class has no stop, blank or shutdown method.  The e-stop and the safe-state action therefore
  write the EHT control as 0 through the value manager, which removes the high tension.  The upstream does
  not document the polarity of the blanker control (``C_Blank`` is listed with the label "Blanking" and a
  default of False at nion/instrumentation/AcquisitionPreferences.py:70), so the driver does not guess it.

The accelerating voltage is a high-voltage hazard: this driver is R3.  Every Fact cites a line of the clone at
the pinned commit (4db575faa502752dc5018754006391c4850a604b).  The package is model-authored and unreviewed,
so the loader refuses its hardware backend (that refusal is enforced at R2 and R3, which is this package); it
is checked on the fake backend only.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write


class NionInstrument(Driver):
    device_id = "nion-instrument"
    device_kind = "instrument.microscope"
    mode = "hardware"
    risk = "R3"
    native = "nion.device_kit.InstrumentDevice:Instrument"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeInstrument"}
    vendor, model = "Nion", "nionswift-instrumentation-kit Instrument"
    display_name = "Nion STEM instrument (nion.device_kit.InstrumentDevice:Instrument)"
    tags = ["stem", "electron-microscope", "high-voltage", "instrument"]
    facts = [
        Fact("Instrument is constructed from an instrument id, a ValueManagerLike and an AxisManagerLike",
             source="upstream_code", ref="nion/device_kit/InstrumentDevice.py:60-67"),
        Fact("TryGetVal reads a named control through value_manager.get_value and SetVal writes it through "
             "value_manager.set_value", source="upstream_code",
             ref="nion/device_kit/InstrumentDevice.py:192-206"),
        Fact("The voltage property reads the EHT control with GetVal and writes it with SetVal",
             source="upstream_code", ref="nion/device_kit/InstrumentDevice.py:155-161"),
        Fact("The defocus_m property reads the C10 control with GetVal and writes it with SetVal",
             source="upstream_code", ref="nion/device_kit/InstrumentDevice.py:147-153"),
        Fact("The energy_offset_eV property reads the ZLPoffset control with GetVal and writes it with SetVal",
             source="upstream_code", ref="nion/device_kit/InstrumentDevice.py:164-171"),
        Fact("get_electrons_per_pixel reads BeamCurrent and multiplies it by 1E12 to obtain picoamperes, so "
             "the stored control is in amperes", source="upstream_code",
             ref="nion/device_kit/InstrumentDevice.py:132-137"),
        Fact("max_defocus is set in __init__ and _set_config_property accepts it (and stage_size_nm) as a "
             "configuration property, so it is a configurable attribute and not a fixed instrument bound",
             source="upstream_code", ref="nion/device_kit/InstrumentDevice.py:69-86"),
    ]
    safe_state = "high tension off: the EHT control is written as 0 through the instrument value manager"

    # -- reads ------------------------------------------------------------------------------------------------
    @read("beam_voltage", unit="V", description="Accelerating voltage, the EHT control in volts")
    def beam_voltage(self) -> float:
        return float(self.native.GetVal("EHT"))

    @read("defocus_m", unit="m", description="Defocus, the C10 control in meters")
    def defocus_m(self) -> float:
        return float(self.native.GetVal("C10"))

    @read("energy_offset_ev", unit="eV", description="Energy offset, the ZLPoffset control in electron volts")
    def energy_offset_ev(self) -> float:
        return float(self.native.GetVal("ZLPoffset"))

    @read("beam_current_a", unit="A",
          description="Beam current, the BeamCurrent control in amperes (the unit get_electrons_per_pixel uses)")
    def beam_current_a(self) -> float:
        return float(self.native.GetVal("BeamCurrent"))

    # -- writes -----------------------------------------------------------------------------------------------
    @write("beam_voltage", unit="V", description="Accelerating voltage, the EHT control in volts",
           limit=Limit.operator_required(
               "the clone names the EHT control but states no accelerating-voltage range "
               "(nion/device_kit/InstrumentDevice.py:155-161); the range depends on the column and the "
               "high-voltage supply of the deployed instrument and is supplied by the operator"))
    def set_beam_voltage(self, value: float) -> float:
        self._set_control("EHT", value)
        return float(self.native.GetVal("EHT"))

    @write("defocus_m", unit="m", description="Defocus, the C10 control in meters",
           limit=Limit.operator_required(
               "the clone exposes the defocus through C10 and a configurable max_defocus attribute, not a fixed "
               "range (nion/device_kit/InstrumentDevice.py:69-86, 147-153); the lens range of the deployed "
               "instrument is supplied by the operator"))
    def set_defocus_m(self, value: float) -> float:
        self._set_control("C10", value)
        return float(self.native.GetVal("C10"))

    @write("energy_offset_ev", unit="eV", description="Energy offset, the ZLPoffset control in electron volts",
           limit=Limit.operator_required(
               "the clone names the ZLPoffset control but states no energy range "
               "(nion/device_kit/InstrumentDevice.py:164-171); the range of the deployed energy filter is "
               "supplied by the operator"))
    def set_energy_offset_ev(self, value: float) -> float:
        self._set_control("ZLPoffset", value)
        return float(self.native.GetVal("ZLPoffset"))

    # -- safe state -------------------------------------------------------------------------------------------
    @action(name="x-cap.nion-software.high_tension_off.v1", safe_state=True,
            description="Remove the high tension: write the EHT control as 0 through the value manager; no input",
            output={"high_tension_off": Field("boolean", description="True when the EHT control reads back as 0")})
    def high_tension_off(self) -> dict:
        self._set_control("EHT", 0.0)
        return {"high_tension_off": float(self.native.GetVal("EHT")) == 0.0}

    # -- safety -----------------------------------------------------------------------------------------------
    @estop
    def stop(self) -> None:
        """The native stop this driver can offer: write EHT as 0, which removes the high tension."""
        self._set_control("EHT", 0.0)

    def _set_control(self, name: str, value: float) -> None:
        """Write one control and turn the value manager's False answer into a failed receipt."""
        accepted = self.native.SetVal(name, value)
        if accepted is False:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"the value manager refused {name} = {value}")
