# Facts and tags for gh.pymeasure/pymeasure

Every fact cites its source at commit `9c6a96014e74bda79988ae0757a6b38ca390d247`: `vendor_doc` (a text file of the
clone) or `upstream_code` (`path/in/clone.py:LINE`).  The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

The package drives the Keithley DMM6500, the first of the card's entry symbols
(`pymeasure.instruments.keithley.keithleyDMM6500:KeithleyDMM6500`, keithleyDMM6500.py:160).  The card is a driver
pack for a repository of many device classes, so recon picked the one class that matches the card's candidate
classes and its `instrument.dmm` resource.

| fact | source | ref |
|---|---|---|
| KeithleyDMM6500 is a 6.5-digit multimeter; the class uses the SCPI command set to communicate with the instrument | upstream_code | pymeasure/instruments/keithley/keithleyDMM6500.py:160-164 |
| voltage is the ':READ?' measurement in volts of the active measurement mode | upstream_code | pymeasure/instruments/keithley/keithleyDMM6500.py:603-606 |
| measure_voltage() switches the mode to DC voltage, or AC voltage with ac=True, and sets the voltage range | upstream_code | pymeasure/instruments/keithley/keithleyDMM6500.py:700-713 |
| current is the ':READ?' measurement in amperes of the active measurement mode | upstream_code | pymeasure/instruments/keithley/keithleyDMM6500.py:486-489 |
| measure_current() switches the mode to DC current, or AC current with ac=True, and sets the current range | upstream_code | pymeasure/instruments/keithley/keithleyDMM6500.py:583-596 |
| measure_resistance() selects 2-wire resistance with wires=2 or 4-wire resistance with wires=4 and sets the range; any other value raises ValueError | upstream_code | pymeasure/instruments/keithley/keithleyDMM6500.py:811-829 |
| temperature is the ':READ?' measurement in degrees Celsius of the active measurement mode | upstream_code | pymeasure/instruments/keithley/keithleyDMM6500.py:961-964 |
| The NPLC integration time of the active mode is validated as a truncated range with values=[0.0005, 15] | upstream_code | pymeasure/instruments/keithley/keithleyDMM6500.py:349-366 |
| The number of display digits of the active mode is validated as one of 3, 4, 5, 6 | upstream_code | pymeasure/instruments/keithley/keithleyDMM6500.py:368-376 |
| scan_stop() aborts a scanning measurement by writing :ABOR, stopping the measurement arming and triggering sequence | upstream_code | pymeasure/instruments/keithley/keithleyDMM6500.py:1315-1321 |

Limits: NPLC is limited to 0.0005 to 15 (the `values=[0.0005, 15]` line of the upstream `nplc` control,
keithleyDMM6500.py:365).  The catalogue classes the measurement actions bind have no numeric input fields that this
driver takes (voltage takes `dc`, current takes nothing, resistance takes `four_wire`), so this is the only bound.

Safety: the e-stop is the native `scan_stop()` (`:ABOR`, keithleyDMM6500.py:1315-1321), which aborts the measurement
arming and triggering sequence; it is also the declared safe state.  The DMM6500 has no motion or source output in
this driver, and no line of the clone documents an independent hardware e-stop, so `estop_physical_ref` is not set
(the card's risk floor is R1, so SAFE-045's R2+ rule does not apply).

Tags: dmm, multimeter, electrical measurement, scpi, keithley
