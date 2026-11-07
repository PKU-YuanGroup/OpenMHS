"""OpenMHS driver for gh.amsikking/thorlabs_mcm3000: the Thorlabs MCM3000 series 3-axis controller.

A direct Driver over ``thorlabs_MCM3000:Controller`` (the card's entry symbol, confirmed in the clone's AST).  The
upstream controller speaks a framed binary serial protocol: it builds each command from a fixed header, a channel
word and a 32-bit signed little-endian encoder count (``thorlabs_MCM3000.py:97-102``, ``135-138``).  A SerialDriver
command table cannot reproduce those bytes, so this package uses a ``native.py`` factory instead of the card's
``family-config``/``SerialDriver`` helper (DEVIATION FROM THE CARD in RESULT.json).

Capabilities:

* reads ``position_ch0``, ``position_ch1`` and ``position_ch2``: the encoder position of each of the three channels
  in micrometres, read through the controller's own ``get_position_um``;
* ``x-cap.amsikking.move_channel.v1``: one channel moved to an absolute (or, with ``relative``, an offset) target in
  micrometres through the controller's blocking ``move_um``.  The travel of a channel follows the stage entry
  (ZFM2020/ZFM2030 or MMP-2XY) that the operator configures in the constructor, so the target is
  ``Limit.operator_required`` and every move is refused ``MHS.SAFETY.LIMITS_UNSET`` until the site's overlay states
  the per-channel travel;
* ``cap.motion.stop.v1`` and the e-stop: the vendor protocol's abrupt Stop Command (``65 04``, channel, stop mode
  ``0x01``) sent to every configured channel.  The upstream class itself implements no stop (its docstring says so,
  ``thorlabs_MCM3000.py:7-8``); the command is the one the vendor document defines, sent through the upstream's own
  ``_send`` frame writer, so the wire syntax is the clone's.

Every Limit and Fact cites a line of the clone at the pinned commit
(390cd97e44abe04945db9b73ec8dc34a099d9f96), except the Stop Command Fact, which cites page 2 of the vendor protocol
PDF (the gate reports that citation as REF_BINARY and a reviewer opens the page).  This package is model-authored and
unreviewed: it is checked on the fake backend only, no hardware backend was imported or executed, and no hardware run
is claimed.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read

#: The connected stage is a constructor choice; the upstream table gives one travel per supported stage, so the
#: driver cannot declare one numeric bound for the connected unit (thorlabs_MCM3000.py:41-44, 167-170).
TRAVEL_REASON = (
    "the travel is a property of the stage the operator configures in the controller's stages argument: the clone "
    "tabulates ZFM2020/ZFM2030 at +/-12700 um and MMP-2XY at +/-25400 um (thorlabs_MCM3000.py:42-44) and "
    "_legalize_move_um refuses a target outside the selected entry (thorlabs_MCM3000.py:167-170), so the site "
    "declares the travel of each configured channel"
)

#: The vendor's abrupt stop command (MCM3000_Direct_Serial_Communication.pdf:2); the stop mode is always 0x01.
_STOP_HEADER = b"\x65\x04"
_STOP_MODE = b"\x01\x00\x00"


class ThorlabsMcm3000(Driver):
    device_id = "mcm3000"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R1"
    native = "thorlabs_MCM3000:Controller"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeMcm3000"}
    vendor, model = "Thorlabs", "MCM3000 series 3-axis controller"
    display_name = "Thorlabs MCM3000 series 3-axis controller"
    tags = ["thorlabs", "mcm3000", "mcm3001", "3-axis", "stage", "stepper", "encoder", "motion"]
    facts = [
        Fact("The upstream adaptor covers the Thorlabs MCM3000 and MCM3001 3-axis controllers",
             source="upstream_code", ref="thorlabs_MCM3000.py:6"),
        Fact("The controller's serial port is opened at 460800 baud with a 5 s read timeout",
             source="upstream_code", ref="thorlabs_MCM3000.py:27"),
        Fact("The supported stage table gives ZFM2020/ZFM2030 0.2116667 um/count within +/-12700 um and MMP-2XY "
             "0.5 um/count within +/-25400 um", source="upstream_code", ref="thorlabs_MCM3000.py:42-44"),
        Fact("_legalize_move_um asserts that the requested position lies within the selected stage's "
             "position_limit_um", source="upstream_code", ref="thorlabs_MCM3000.py:167-170"),
        Fact("A position query is the 6-byte command 0A 04 <channel> 00 00 00; the 12-byte reply carries the "
             "channel at byte 6 and the signed 32-bit little-endian encoder count in its last four bytes",
             source="upstream_code", ref="thorlabs_MCM3000.py:97-102"),
        Fact("A move is the 12-byte command 53 04 06 00 00 00 <channel word> <signed 32-bit encoder count>",
             source="upstream_code", ref="thorlabs_MCM3000.py:135-138"),
        Fact("A relative move first refreshes the encoder position and then adds the requested offset before the "
             "limit check", source="upstream_code", ref="thorlabs_MCM3000.py:163-166"),
        Fact("The upstream class docstring says a stop function is not implemented",
             source="upstream_code", ref="thorlabs_MCM3000.py:7-8"),
        Fact("The vendor protocol defines an abrupt Stop Command with header 65 04, the channel byte and stop mode "
             "0x01 that stops any type of motor move on the specified channel",
             source="vendor_doc", ref="MCM3000_Direct_Serial_Communication.pdf:2"),
        Fact("The stage encoder is assumed to be zero at the centre of its range for the +/- position checks",
             source="upstream_code", ref="thorlabs_MCM3000.py:110-113"),
        Fact("Only the channels with a stage entry are available, and the constructor requires exactly three stage "
             "and reverse entries", source="upstream_code", ref="thorlabs_MCM3000.py:32-54"),
    ]
    safe_state = ("all configured channels stopped by the vendor's abrupt Stop Command (65 04, channel, stop mode "
                  "0x01)")

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("position_ch0", unit="um", description="Encoder position of channel 0 in micrometres")
    def position_ch0(self):
        return self._position(0)

    @read("position_ch1", unit="um", description="Encoder position of channel 1 in micrometres")
    def position_ch1(self):
        return self._position(1)

    @read("position_ch2", unit="um", description="Encoder position of channel 2 in micrometres")
    def position_ch2(self):
        return self._position(2)

    # -- motion ---------------------------------------------------------------------------------------------------
    @action(name="x-cap.amsikking.move_channel.v1", verb="invoke", risk="R1", exclusive=True,
            description="Move one configured controller channel to a position in micrometres and report the "
                        "position the controller reads back",
            input={
                "channel": Field("integer", unit="1", description="Channel index: 0, 1 or 2",
                                 limit=Limit(allowed=[0, 1, 2], source="upstream_code",
                                             ref="thorlabs_MCM3000.py:32-54")),
                "position_um": Field("number", unit="um",
                                     description="Target position in micrometres, or an offset when relative is "
                                                 "true",
                                     limit=Limit.operator_required(TRAVEL_REASON)),
                "relative": Field("boolean",
                                  description="Treat position_um as an offset from the current position (default "
                                              "false)"),
            },
            output={
                "channel": Field("integer", unit="1", description="Channel that was moved"),
                "target_position_um": Field("number", unit="um",
                                            description="Absolute target the controller was given, after its "
                                                        "encoder-count conversion"),
                "measured_position_um": Field("number", unit="um",
                                              description="Position read back from the controller after the move"),
                "reached": Field("boolean",
                                 description="True when the blocking move returned within the controller's own "
                                             "one-count tolerance"),
            })
    def move_channel(self, channel, position_um, relative=False):
        channel = int(channel)
        self._require_channel(channel)
        target = self.native.move_um(channel, float(position_um), relative=bool(relative), block=True)
        measured = float(self.native.get_position_um(channel))
        return {"channel": channel, "target_position_um": float(target),
                "measured_position_um": measured, "reached": True}

    @action(cap="cap.motion.stop.v1",
            description="Stop all configured channels with the vendor's abrupt Stop Command",
            input={"deceleration": Field(
                "number", unit="m/s2",
                description="Accepted for the class only: the controller's Stop Command is abrupt and takes no "
                            "deceleration profile")})
    def stop_motion(self, deceleration=None):
        self._stop_all()
        return {"stopped": True}

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop(native="_send")
    def stop_all(self):
        """The native stop: the vendor Stop Command sent to every configured channel by the upstream _send."""
        self._stop_all()

    # -- lifecycle ------------------------------------------------------------------------------------------------
    def teardown(self):
        self.native.close()

    # -- helpers --------------------------------------------------------------------------------------------------
    def _require_channel(self, channel):
        if channel not in tuple(self.native.channels):
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               f"channel {channel} has no stage configured on this controller")

    def _position(self, channel):
        self._require_channel(channel)
        return float(self.native.get_position_um(channel))

    def _stop_all(self):
        for channel in tuple(self.native.channels):
            channel_byte = int(channel).to_bytes(1, "little")
            self.native._send(_STOP_HEADER + channel_byte + _STOP_MODE, int(channel))
