# Facts and tags for gh.nion-software/nionswift-instrumentation-kit

Every fact cites its source at commit `4db575faa502752dc5018754006391c4850a604b`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Instrument is constructed from an instrument id, a ValueManagerLike and an AxisManagerLike | upstream_code | nion/device_kit/InstrumentDevice.py:60-67 |
| TryGetVal reads a named control through value_manager.get_value and SetVal writes it through value_manager.set_value | upstream_code | nion/device_kit/InstrumentDevice.py:192-206 |
| The voltage property reads the EHT control with GetVal and writes it with SetVal | upstream_code | nion/device_kit/InstrumentDevice.py:155-161 |
| The defocus_m property reads the C10 control with GetVal and writes it with SetVal | upstream_code | nion/device_kit/InstrumentDevice.py:147-153 |
| The energy_offset_eV property reads the ZLPoffset control with GetVal and writes it with SetVal | upstream_code | nion/device_kit/InstrumentDevice.py:164-171 |
| get_electrons_per_pixel reads BeamCurrent and multiplies it by 1E12 to obtain picoamperes, so the stored control is in amperes | upstream_code | nion/device_kit/InstrumentDevice.py:132-137 |
| max_defocus is set in __init__ and _set_config_property accepts it (and stage_size_nm) as a configuration property, so it is a configurable attribute and not a fixed instrument bound | upstream_code | nion/device_kit/InstrumentDevice.py:69-86 |

Limits: the accelerating voltage (EHT), the defocus (C10) and the energy offset (ZLPoffset) are
`Limit.operator_required`. No text of the clone states a range for any of these controls; the clone only names
them. The ranges depend on the deployed column, lens and energy filter, so the site supplies them through
`site-limits.json` (`site-limits.example.json` is an example overlay, not a statement about a unit). Until the
overlay is supplied, every write is refused `MHS.SAFETY.LIMITS_UNSET`.

Safety: the high voltage (EHT) is the reason this driver is R3. The upstream class has no stop, blank or
shutdown method, and no line of the clone documents an independent hardware e-stop. The driver therefore
declares the native stop as writing EHT as 0 through the value manager, and it declares
`x-cap.nion-software.high_tension_off.v1` as the safe-state action (SAFE-045). It does not guess the polarity of
the blanker control: `C_Blank` is listed with the label "Blanking" and a default of False at
nion/instrumentation/AcquisitionPreferences.py:70, but no line says which value blanks the beam. The package is
model-authored and unreviewed, so the loader refuses its hardware backend (enforced at R2 and R3).

Mock path: the upstream package owns no simulator of `InstrumentDevice:Instrument`; its test suite uses an
in-memory `ValueManagerLike` (nion/instrumentation/test/AcquisitionTestContextConfiguration.py:138-177) to drive
the adapter. The package follows that path: `fake.py` is a recording-style in-memory `GetVal`/`SetVal` object,
not the upstream simulator. The starting numbers in `fake.py` are test data marked `# placeholder`.

NOT COVERED: the upstream `Instrument` also reads and writes the 2D stage position (`stage_position_m`,
InstrumentDevice.py:139-145) and serves the EELS/ronchigram camera shapes and acquisition controllers. This
driver does not expose them: the 2D value needs `Geometry.FloatPoint` from the external nion-utils package,
which the driver may not import, and the camera/acquisition arrays are out of scope for this package.

Tags: stem, electron-microscope, high-voltage, instrument
