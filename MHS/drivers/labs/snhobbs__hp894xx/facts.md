# Facts and tags for gh.snhobbs/hp894xx

Every fact cites its source at commit `6745a53c20fb02b1a178fde70b1975b6b86f3518`.  The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The upstream driver class is HP89400Device, a PrologixGPIBEthernetDevice | upstream_code | python/HP894xx/HP89400Device.py:55 |
| The class constructor forwards its arguments to PrologixGPIBEthernetDevice | upstream_code | python/HP894xx/HP89400Device.py:56-57 |
| The README describes the package as HP89400 Series Vector Signal Analyzer GPIB Control using the Prologix GPIB-ETHERNET adapter | vendor_doc | README.md:2 |
| GetXCenter queries SENS:FREQ:CENT? and GetXSpan queries SENS:FREQ:SPAN? | upstream_code | python/HP894xx/HP89400Device.py:121-125 |
| GetXUnits queries CALC:X:UNIT:FREQ? and GetYUnits queries CALC:UNIT:POW? | upstream_code | python/HP894xx/HP89400Device.py:114-119 |
| GetDataLength queries CALC:DATA:HEAD:POIN? and returns an int | upstream_code | python/HP894xx/HP89400Device.py:111-112 |
| GetReadDataPoints queries SENS:AVER:COUN:INT? and returns an int | upstream_code | python/HP894xx/HP89400Device.py:192-193 |
| get_operating_condition queries STAT:OPER:COND? and returns an int | upstream_code | python/HP894xx/HP89400Device.py:171-173 |
| get_error_code takes the leading comma-separated field of an error string as an int | upstream_code | python/HP894xx/HP89400Device.py:74-76 |
| read_errors queries SYST:ERR?, and read_error_code returns get_error_code(read_errors()) | upstream_code | python/HP894xx/HP89400Device.py:95-99 |
| read_data starts a data read with StartDataRead and parses the comma-separated reply into floats | upstream_code | python/HP894xx/HP89400Device.py:198-211 |
| StartDataRead writes CALC:DATA? | upstream_code | python/HP894xx/HP89400Device.py:195-196 |
| abort writes abor until the write succeeds | upstream_code | python/HP894xx/HP89400Device.py:130-137 |
| enable_autorange writes SENS:VOLT:RANGE:AUTO with an integer 0/1 setting | upstream_code | python/HP894xx/HP89400Device.py:189-190 |
| The README's sample capture shows a 5 MHz span centred at 2.5 MHz with 1601 points, X unit HZ and Y unit VRMS/RTHZ | vendor_doc | README.md:23-41 |
| The README states that no x values are saved, only y values, and that the x values can be determined from the header | vendor_doc | README.md:55 |

Limits: none.  The package exposes no numeric setting, so it declares no Limit: it does not infer a bound from the
README sample capture, a constructor default or an unread PDF.  The README numbers above are one sample capture, not
device bounds; they are not used as Limits.

Safety: the upstream interface is observational (reads, a trace read, an abort and a boolean autorange setting); it
has no motion, heater or radiation source, so the declared risk is R0.  The upstream `abort` (`abor`,
python/HP894xx/HP89400Device.py:130-137) is exposed as the `x-cap.snhobbs.abort_measurement.v1` action, but R0 needs
neither an independent hardware e-stop nor a safe-state action (SAFE-045 applies at R2 and above).

Fake: `FakeHP89400` implements only public methods of the upstream class (gate G7), returns query replies as the
strings the upstream transport returns, and returns an eight-point trace.  Every number and reply in the fake is
placeholder test data (`# placeholder`); the real centre, span, point count, average count and trace are settings of
the analyzer.  The README's sample capture shows 1601 points (README.md:41); that is one configuration, not a fixed
size of the device.

Tags: vector signal analyzer, spectrum, gpib, prologix, measurement
