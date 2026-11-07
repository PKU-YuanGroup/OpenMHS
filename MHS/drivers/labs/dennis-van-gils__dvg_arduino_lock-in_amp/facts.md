# Facts and tags for gh.dennis-van-gils/dvg_arduino_lock-in_amp

Every fact cites its source at commit `64c0f18f9111eef2fc4feb10466c4dd9a39fb516`: `vendor_doc` (a text file of the
clone) or `upstream_code` (`path/in/clone:LINE`). The same facts are written into `driver.py` (`facts = [...]`);
the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The device is an Arduino lock-in amplifier running at a 25 kHz sampling rate with 12-bit analog resolution | vendor_doc | README.rst:17-19 |
| The microcontroller generates the reference signal REF_X and acquires the input signal SIG_I | vendor_doc | README.rst:40-41 |
| The reference signal REF_X is a true analog-out waveform between 0 and 3.3 V | vendor_doc | README.rst:51 |
| The upstream Waveform enumeration is Unknown=-1, Sine=0, Square=1 and Triangle=2 | upstream_code | Alia_protocol_serial.py:42-48 |
| Alia.set_ref writes the waveform, frequency, offset, amplitude and RMS amplitude as _wave, _freq, _offs, _ampl and _vrms commands, then reads the obtained values with query_ref | upstream_code | Alia_protocol_serial.py:819-844 |
| Alia.query_ref sends '?' and parses the waveform, frequency, offset, amplitude, RMS amplitude and the two clipping flags from a tab-separated reply | upstream_code | Alia_protocol_serial.py:685-697 |
| The firmware derives the reference frequency from the sampling rate as Fs/N_LUT and clamps N_LUT to the allowed look-up-table size | upstream_code | mcu_source/v1.0.0_VSCODE/src/main.cpp:374-380 |
| The look-up-table size is clamped between MIN_N_LUT 20 and MAX_N_LUT 1000 samples | upstream_code | mcu_source/v1.0.0_VSCODE/src/main.cpp:288-289 |
| The firmware clamps the reference offset, amplitude and RMS amplitude to at least 0.0 V | upstream_code | mcu_source/v1.0.0_VSCODE/src/main.cpp:382-398 |
| The firmware sets a clipping flag when the scaled reference waveform falls below 0.0 or above 1.0 of the analog reference | upstream_code | mcu_source/v1.0.0_VSCODE/src/main.cpp:332-340 |
| Alia.turn_on writes 'on' and Alia.turn_off writes 'off'; turn_off clears the input buffer and waits for the off acknowledgement | upstream_code | Alia_protocol_serial.py:399-430 |
| Alia.begin turns the lock-in amplifier off at startup | upstream_code | Alia_protocol_serial.py:185 |
| While the lock-in amplifier is running, the firmware switches it off on any received command, clears the transmit triggers and answers 'off' | upstream_code | mcu_source/v1.0.0_VSCODE/src/main.cpp:753-779 |
| On the transition from running to off, the firmware drives the DAC output to 0 V | upstream_code | mcu_source/v1.0.0_VSCODE/src/main.cpp:582-584 |
| Alia.query_ADC_autocalibration sends 'autocal?' and stores is_valid, gaincorr and offsetcorr from three tab-separated integers | upstream_code | Alia_protocol_serial.py:548-568 |
| The firmware reports the ADC calibration as is_valid, gaincorr and offsetcorr | upstream_code | mcu_source/v1.0.0_VSCODE/src/main.cpp:1075-1079 |
| The Alia constructor defaults to 1e6 baud with 1 s read and write timeouts | upstream_code | Alia_protocol_serial.py:139-158 |

Limits: `ref_offset`, `ref_amplitude` and `ref_amplitude_rms` are bounded 0 to 3.3 V by the vendor README
(README.rst:51), with the firmware's lower clamp at 0.0 V (main.cpp:382-398). `ref_waveform` is an allowed set of
Sine, Square and Triangle (Alia_protocol_serial.py:42-48). `ref_freq` is `Limit.operator_required`: the firmware
computes the output frequency as Fs/N_LUT with N_LUT clamped to 20..1000 (main.cpp:288-289, 374-380), so the Hz range
depends on the sampling rate of the installed board; the site supplies the range in `site-limits.example.json`.

Safety: the e-stop and the safe-state action `x-cap.dennis-van-gils.stop_acquisition.v1` both call the native
`turn_off()` (the `off` command). The firmware stops the acquisition and drives the reference DAC to 0 V on the
running-to-off transition (main.cpp:582-584). The clone documents no separate output-disable command and no independent
hardware e-stop, so `estop_physical_ref` is not set; the driver is R1, where SAFE-045 does not ask for one.

Tags: lock-in, lock-in-amplifier, signal-generation, adc, serial
