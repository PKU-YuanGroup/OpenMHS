# Facts and tags for gh.asvela/keyoscacquire

Every fact cites its source at commit `1d093470ab99769c9b149816d7faa4b61a4837d2`: `upstream_code` (a line of the
Python source of the clone). The same facts are written into `driver.py` (`facts = [...]`); the reference file is
generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The clone drives Keysight InfiniiVision X-series oscilloscopes of the 1000, 2000, 3000, 4000 and 6000 series | upstream_code | keyoscacquire/oscilloscope.py:30 |
| '*IDN?' answers maker, model, serial and firmware, for example 'KEYSIGHT TECHNOLOGIES,MSO9104A,MY12345678,06.30.00609' | upstream_code | keyoscacquire/oscilloscope.py:90-91 |
| The error queue is a FIFO of at most 30 entries and ':SYSTem:ERRor?' returns 'error number,description' | upstream_code | keyoscacquire/oscilloscope.py:232-243 |
| The operation condition register ':OPERegister:CONDition?' has its third bit (value 8) set while the instrument is running | upstream_code | keyoscacquire/oscilloscope.py:286-288 |
| The acquisition type is NORMal, AVERage or HRESolution; AVER<m> also sets the number of averages to <m> | upstream_code | keyoscacquire/oscilloscope.py:335-340 |
| The acquisition type is sent as the first four characters in upper case, so NORMal becomes ':ACQuire:TYPE NORM', AVERage 'AVER' and HRESolution 'HRES' | upstream_code | keyoscacquire/oscilloscope.py:363-365 |
| The number of averages is checked to lie between 2 and 65,536 before ':ACQuire:COUNt' is written | upstream_code | keyoscacquire/oscilloscope.py:404-408 |
| The points mode of the acquisition is one of RAW, MAX and NORMal | upstream_code | keyoscacquire/config.py:16 |
| NORMal points mode is limited to 62,500 points, whereas RAW gives up to 1e6 points | upstream_code | keyoscacquire/config.py:14-15 |
| A num_points value of 0 selects the maximum number of points for the current points mode | upstream_code | keyoscacquire/config.py:18-20 |
| The waveform transfer format is BYTE, WORD or ASCii | upstream_code | keyoscacquire/installed_cli_programmes.py:30 |
| ':RUN' sets the oscilloscope running and ':STOP' stops the acquisition | upstream_code | keyoscacquire/oscilloscope.py:270-276 |

Limits (all `upstream_code`):

| parameter | command | limit | ref |
|---|---|---|---|
| acq_type | :ACQuire:TYPE | NORMal, AVERage or HRESolution | keyoscacquire/oscilloscope.py:335-340 (the setter sends the first four characters, line 364) |
| num_averages | :ACQuire:COUNt | 2 to 65536 | keyoscacquire/oscilloscope.py:406 |
| p_mode | :WAVeform:POINts:MODE | RAW, MAX or NORMal | keyoscacquire/config.py:16 |
| num_points | :WAVeform:POINts | 0 to 1000000 | keyoscacquire/config.py:14-20 (RAW up to 1e6, NORMal 62,500, 0 selects the maximum) |
| wav_format | :WAVeform:FORMat | BYTE, WORD or ASCii | keyoscacquire/installed_cli_programmes.py:30 |

Safety: the e-stop writes `:STOP`, the clone's stop command (oscilloscope.py:274-276); the acquisition stops. There
is no hardware e-stop to cite and none is needed at R1. The driver does not transfer the waveform (see RESULT.json
notes): it serves the acquisition settings, the operation condition register and the error queue.

Tags: oscilloscope, keysight, infinivision, scpi
