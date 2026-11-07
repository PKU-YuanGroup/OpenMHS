"""OpenMHS driver for gh.tektronix/curvequery: waveform download from Tektronix 4/5/6 Series MSO scopes.

A direct Driver over the upstream ``curvequery._tek_series_mso_curve_feat:TekSeriesCurveFeat`` plugin.  The card
proposes a ``ScpiDriver`` (family ``scpi``, decision ``family-config``), but the upstream interface is a Visadore
feature object, not a table of fixed command lines: the class lists the sources and assembles each per-source
command from the source name (``{}:SCALE?``, ``display:global:{}:state?``) and reads the curve as an IEEE binary
block (``_tek_series_mso_curve_feat.py:101, 109, 166-173, 268-273``).  A command table cannot express those bytes,
so this package is a direct Driver over the upstream class with a ``native.py`` factory (DEVIATION FROM THE CARD,
recorded in RESULT.json).

* the served capability is one extension action that calls the upstream ``feature()`` and returns the
  ``WaveformCollection`` it builds: one trace per displayed source, with the per-source horizontal scale, the
  per-source vertical window (analog and math) and the source names;
* the clone has no separate scalar read or write: ``TekSeriesCurveFeat`` exposes only ``feature()`` (line 21), and
  the sibling setup/acquire/default-setup features are different classes registered under different entry points
  (setup.cfg:45-69).  A direct Driver names one upstream class, so this package serves the curve feature only;
* there is no numeric input, so there is no Limit to declare and no operator-required bound to overlay;
* the driver is R0 (observation): it transfers data and has no actuating output.  The upstream feature stops the
  acquisition while it reads and restores the previous ``ACQuire:STATE`` afterwards (lines 223-225 and 307-308).

NOT COVERED: the setup, default-setup and acquire features of the same package are not served.  They belong to
``TekSeriesSetupFeat``, ``TekSeriesDefaultFeat`` and ``TekSeriesAcquireFeat``, which are separate upstream classes
and therefore cannot be reached through the single ``native`` symbol this driver resolves.

Every Fact cites a line of the clone at the pinned commit (57e59cc076eb41feaa3c606dcc5a68d447b44026).  This package
is model-authored and unreviewed, is checked on the fake backend only, and never ran on hardware.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, action

CURVE_FEAT = "curvequery/_tek_series_mso_curve_feat.py"
API_TYPES = "curvequery/api_types.py"
SETUP_CFG = "setup.cfg"

CURVE_DOWNLOAD = "x-cap.tektronix.curve_download.v1"


class TektronixMSO(Driver):
    device_id = "mso"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R0"
    native = "curvequery._tek_series_mso_curve_feat:TekSeriesCurveFeat"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeCurveFeature"}
    vendor = "Tektronix"
    model = "4/5/6 Series MSO oscilloscope"
    display_name = "Tektronix 4/5/6 Series MSO waveform download (curvequery)"
    tags = ["oscilloscope", "tektronix", "mso44", "mso46", "mso54", "mso56", "mso58", "curvequery", "visa"]
    facts = [
        Fact("curvequery is a layer on PyVISA and the Visadore plugin manager for downloading waveform data from "
             "an oscilloscope", source="vendor_doc", ref="README.md:15-16"),
        Fact("The curve feature is registered for the MSO44, MSO46, MSO54, MSO56 and MSO58 with the entry point "
             "curve = curvequery._tek_series_mso_curve_feat:TekSeriesCurveFeat", source="upstream_code",
             ref=f"{SETUP_CFG}:45-69"),
        Fact("The package pins visadore 1.0, pyvisa 1.11.3 and tqdm 4.62.2 or later", source="upstream_code",
             ref=f"{SETUP_CFG}:21-24"),
        Fact("TekSeriesCurveFeat.feature returns a WaveformCollection whose data maps each source name to a "
             "Waveform(data, x_scale, y_scale)", source="upstream_code", ref=f"{CURVE_FEAT}:20-46"),
        Fact("The source list comes from data:source:available? and only sources whose "
             "display:global:<source>:state reply is on are kept", source="upstream_code",
             ref=f"{CURVE_FEAT}:107-124"),
        Fact("A source is kept only when display:global:<source>:state? replies with a non-zero integer",
             source="upstream_code", ref=f"{CURVE_FEAT}:59-70"),
        Fact("The horizontal scale is slope = WFMOutpre:XINCR and offset = -PT_OFF * slope + XZERO, in the "
             "WFMOutpre:XUNIT unit", source="upstream_code", ref=f"{CURVE_FEAT}:72-97"),
        Fact("The analog vertical window is scale * (5 - position) to scale * (-5 - position), from the source's "
             "SCALE and POSITION queries", source="upstream_code", ref=f"{CURVE_FEAT}:99-105"),
        Fact("Analog samples are converted with WFMOutpre:YMUlt and WFMOutpre:YZEro", source="upstream_code",
             ref=f"{CURVE_FEAT}:175-186"),
        Fact("A decomposed digital bit is named <source>_D<bit> and each sample is (sample >> (2 * bit)) & 1",
             source="upstream_code", ref=f"{CURVE_FEAT}:188-197"),
        Fact("With decompose_dch the feature yields the eight bit channels; without it the same source becomes one "
             "8-bit word", source="upstream_code", ref=f"{CURVE_FEAT}:275-290"),
        Fact("MATH sources carry no y_scale", source="upstream_code", ref=f"{CURVE_FEAT}:297-300"),
        Fact("Each download takes its record length from horizontal:recordlength?", source="upstream_code",
             ref=f"{CURVE_FEAT}:149"),
        Fact("The record is read from data:start 1 to data:stop <record length>", source="upstream_code",
             ref=f"{CURVE_FEAT}:170-173"),
        Fact("The feature saves ACQuire:STATE and writes ACQuire:STATE STOP for the transfer", source="upstream_code",
             ref=f"{CURVE_FEAT}:223-225"),
        Fact("The feature restores the saved ACQuire:STATE after the transfer", source="upstream_code",
             ref=f"{CURVE_FEAT}:307-308"),
        Fact("Waveform is a namedtuple of data, x_scale and y_scale", source="upstream_code", ref=f"{API_TYPES}:7"),
        Fact("WaveformCollection.sources returns the keys of data", source="upstream_code",
             ref=f"{API_TYPES}:31-44"),
    ]
    safe_state = "acquisition stopped during the transfer; the saved ACQuire:STATE is restored afterwards"

    @action(
        name=CURVE_DOWNLOAD,
        description="Download every displayed waveform source through the curvequery feature and return the traces",
        input={
            "decompose_digital_channels": Field(
                "boolean",
                description="True splits a digital source into eight 1-bit channels; False returns one 8-bit word"),
        },
        output={
            "sources": Field(
                "array", items=Field("string", description="Source name reported by the instrument"),
                description="Downloaded sources in the order the feature returned them"),
            "traces": Field(
                "array", items=Field(
                    "array", items=Field(
                        "number", description="One sample as the feature returned it: a scaled analog value or a "
                                              "digital bit/word"),
                    description="Samples of one source"),
                description="Waveform samples per source, in the same order as sources"),
            "x_slope": Field(
                "array", items=Field("number", description="Horizontal interval between samples, in x_unit"),
                description="Horizontal sample interval of each source"),
            "x_offset": Field(
                "array", items=Field("number", description="Horizontal position of sample zero, in x_unit"),
                description="Horizontal offset of each source"),
            "x_unit": Field(
                "array", items=Field("string", description="Horizontal unit the instrument reported"),
                description="Horizontal unit of each source"),
            "y_top": Field(
                "array", items=Field(
                    "number", nullable=True,
                    description="Top of the vertical display window, or null when the source has no y scale"),
                description="Top of the vertical window of each source"),
            "y_bottom": Field(
                "array", items=Field(
                    "number", nullable=True,
                    description="Bottom of the vertical display window, or null when the source has no y scale"),
                description="Bottom of the vertical window of each source"),
        },
    )
    def download_curves(self, decompose_digital_channels=True):
        collection = self.native.feature(
            use_pbar=False, decompose_dch=bool(decompose_digital_channels), verbose=False
        )
        sources = list(collection.sources)
        traces, x_slopes, x_offsets, x_units, y_tops, y_bottoms = [], [], [], [], [], []
        for source in sources:
            waveform = collection[source]
            x_scale = waveform.x_scale
            if x_scale is None:
                raise DriverFailed("MHS.DEVICE.FAULTED",
                                   f"the feature returned {source!r} without a horizontal scale")
            traces.append([float(sample) for sample in waveform.data])
            x_slopes.append(float(x_scale.slope))
            x_offsets.append(float(x_scale.offset))
            x_units.append(str(x_scale.unit))
            y_scale = waveform.y_scale
            if y_scale is None:
                y_tops.append(None)
                y_bottoms.append(None)
            else:
                y_tops.append(float(y_scale.top))
                y_bottoms.append(float(y_scale.bottom))
        return {
            "sources": sources,
            "traces": traces,
            "x_slope": x_slopes,
            "x_offset": x_offsets,
            "x_unit": x_units,
            "y_top": y_tops,
            "y_bottom": y_bottoms,
        }
