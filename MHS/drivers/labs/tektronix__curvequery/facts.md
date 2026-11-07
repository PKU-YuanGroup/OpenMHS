# Facts and tags for gh.tektronix/curvequery

Every fact cites its source at commit `57e59cc076eb41feaa3c606dcc5a68d447b44026`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| curvequery is a layer on PyVISA and the Visadore plugin manager for downloading waveform data from an oscilloscope | vendor_doc | README.md:15-16 |
| The curve feature is registered for the MSO44, MSO46, MSO54, MSO56 and MSO58 with the entry point curve = curvequery._tek_series_mso_curve_feat:TekSeriesCurveFeat | upstream_code | setup.cfg:45-69 |
| The package pins visadore 1.0, pyvisa 1.11.3 and tqdm 4.62.2 or later | upstream_code | setup.cfg:21-24 |
| TekSeriesCurveFeat.feature returns a WaveformCollection whose data maps each source name to a Waveform(data, x_scale, y_scale) | upstream_code | curvequery/_tek_series_mso_curve_feat.py:20-46 |
| The source list comes from data:source:available? and only sources whose display:global:<source>:state reply is on are kept | upstream_code | curvequery/_tek_series_mso_curve_feat.py:107-124 |
| A source is kept only when display:global:<source>:state? replies with a non-zero integer | upstream_code | curvequery/_tek_series_mso_curve_feat.py:59-70 |
| The horizontal scale is slope = WFMOutpre:XINCR and offset = -PT_OFF * slope + XZERO, in the WFMOutpre:XUNIT unit | upstream_code | curvequery/_tek_series_mso_curve_feat.py:72-97 |
| The analog vertical window is scale * (5 - position) to scale * (-5 - position), from the source's SCALE and POSITION queries | upstream_code | curvequery/_tek_series_mso_curve_feat.py:99-105 |
| Analog samples are converted with WFMOutpre:YMUlt and WFMOutpre:YZEro | upstream_code | curvequery/_tek_series_mso_curve_feat.py:175-186 |
| A decomposed digital bit is named <source>_D<bit> and each sample is (sample >> (2 * bit)) & 1 | upstream_code | curvequery/_tek_series_mso_curve_feat.py:188-197 |
| With decompose_dch the feature yields the eight bit channels; without it the same source becomes one 8-bit word | upstream_code | curvequery/_tek_series_mso_curve_feat.py:275-290 |
| MATH sources carry no y_scale | upstream_code | curvequery/_tek_series_mso_curve_feat.py:297-300 |
| Each download takes its record length from horizontal:recordlength? | upstream_code | curvequery/_tek_series_mso_curve_feat.py:149 |
| The record is read from data:start 1 to data:stop <record length> | upstream_code | curvequery/_tek_series_mso_curve_feat.py:170-173 |
| The feature saves ACQuire:STATE and writes ACQuire:STATE STOP for the transfer | upstream_code | curvequery/_tek_series_mso_curve_feat.py:223-225 |
| The feature restores the saved ACQuire:STATE after the transfer | upstream_code | curvequery/_tek_series_mso_curve_feat.py:307-308 |
| Waveform is a namedtuple of data, x_scale and y_scale | upstream_code | curvequery/api_types.py:7 |
| WaveformCollection.sources returns the keys of data | upstream_code | curvequery/api_types.py:31-44 |

There is no Limit. The package's only capability takes one boolean input (`decompose_digital_channels`), no
numeric input and no numeric output bound, so there is nothing to restrict and no `site-limits.example.json`.

Safety: the driver is R0 (observation). It transfers waveform data and controls no physical output. The upstream
feature stops the acquisition during the transfer and restores the saved `ACQuire:STATE` afterwards
(`curvequery/_tek_series_mso_curve_feat.py:223-225,307-308`); that is the only device state the driver affects.

Tags: oscilloscope, tektronix, mso44, mso46, mso54, mso56, mso58, curvequery, visa
