"""OpenMHS TagDriver for the caproto Raspberry Pi hat IOC (``iocs/hat.py``).

The upstream repository ships two caproto PVGroups for a Raspberry Pi:

* ``iocs/hat.py:IOC`` exposes one integer ``state`` PV; ``write_state`` maps a
  truthy value to ``GPIO.HIGH``, a falsy value to ``GPIO.LOW`` and writes that
  level to every configured BOARD pin (``iocs/hat.py:25-34``).  This package
  serves this IOC only.
* ``iocs/rgb.py:IOC`` (the ``color`` PV) is NOT COVERED: it is a separate IOC
  process, the shipped playbook ``hats.yml`` deploys only ``hat.py``
  (``hats.yml:10-15``), the shipped supervisor configurations give BOARD pin 11
  to both IOCs (``supervisor_config/hat.conf:2``, ``supervisor_config/rgb.conf:2``),
  and ``write_color`` parses ``value[0]`` of a PV declared as the one-element
  list ``['000000']`` (``iocs/rgb.py:45-51``), so what a written colour does
  depends on how the installed caproto server passes a one-element string
  array to the put hook, which the clone does not show.

This is a configuration-only ``TagDriver`` for the ``state`` Channel Access PV.
The SDK's ``TagBridge`` reads and writes the PV suffix through a transport; the
deployment prefix belongs to ``native.py``.  The fake is a deterministic
``RecordingTagTransport`` of the one PV.  The hardware backend is an EPICS
Channel Access client built with caproto and is never opened before a human
signs ``reviewed_by`` with scope ``hardware`` (all tag-bridge hardware, every
risk class).

The stop writes ``state = 0`` and confirms it by a fresh read.  This proves the
IOC executed the put (``write_state`` drives the pins LOW per the code), not the
electrical state of the pins.  It does not call the IOC shutdown hook: it does
not run ``GPIO.cleanup``.

Licence: the clone has no ``LICENSE`` file and the card records NOASSERTION /
unknown; publication is a human review decision.
"""

from mhs.driver import Action, Fact, Field, Limit, TagDriver

HAT = "iocs/hat.py"
RGB = "iocs/rgb.py"

#: The Channel Access PV suffix exactly as the pvproperty attribute is declared upstream.
POINTS = {
    "state": {
        "pv": "state", "type": "integer", "access": "read-write", "source_ref": f"{HAT}:34",
        "description": "Hat state PV; write_state maps a truthy value to GPIO.HIGH and a falsy value to GPIO.LOW",
    },
}

_STOP = {
    "steps": [{"write": "state", "value": 0}],
    "confirm": [{"point": "state", "equals": 0}],
}
_HAT_ON = "x-cap.danielballan.hat_on.v1"
_ALL_OFF = "x-cap.danielballan.all_off.v1"

_STATE = Field("integer", unit="1", description="State PV read back after the command")


class CaprotoRpi(TagDriver):
    device_id = "caproto-rpi"
    device_kind = "device"
    mode = "hardware"
    risk = "R1"
    native = "iocs.hat:IOC"
    backends = {"fake": ".fake:FakeCaprotoRpi", "hardware": ".native:connect"}
    vendor, model = "danielballan", "caproto-rpi"
    display_name = "Raspberry Pi hat IOC (caproto EPICS Channel Access)"
    tags = ["epics", "epics-ca", "caproto", "raspberry-pi", "gpio", "led", "tag-bridge"]
    facts = [
        Fact("iocs/hat.py defines IOC with a state pvproperty (default 0) whose put callback is write_state; "
             "write_state maps a truthy value to GPIO.HIGH and a falsy value to GPIO.LOW and writes that level "
             "to every configured pin.", source="upstream_code", ref=f"{HAT}:25-34"),
        Fact("The state startup hook selects GPIO.BOARD numbering, configures every pin as an output and drives "
             "it LOW; the shutdown hook drives every pin LOW and calls GPIO.cleanup.",
             source="upstream_code", ref=f"{HAT}:36-47"),
        Fact("The hat IOC requires a comma-separated --pins argument, converts each token to int and passes the "
             "list to IOC(pins=...).", source="upstream_code", ref=f"{HAT}:56-63"),
        Fact("The hat IOC argument parser sets default_prefix='rpi:'.", source="upstream_code", ref=f"{HAT}:52"),
        Fact("The hats.yml playbook copies only hat.py into /opt/iocs.", source="upstream_code",
             ref="hats.yml:10-16"),
        Fact("iocs/rgb.py defines IOC with a color pvproperty whose default value is the one-element list "
             "['000000']; write_color parses value[0] as a base-16 integer, sets every channel duty cycle and "
             "returns value.", source="upstream_code", ref=f"{RGB}:45-51"),
        Fact("rescale maps an 8-bit channel value to 100 * (x / 255)**2.8, a 0-100 duty-cycle scale with gamma "
             "2.8; the comment attributes 2.8 to the RGB LED vendor.", source="upstream_code", ref=f"{RGB}:19-26"),
        Fact("duty_cycle extracts the red, green and blue 8-bit channels with the masks 0xff0000, 0x00ff00 and "
             "0x0000ff and rescales each.", source="upstream_code", ref=f"{RGB}:29-36"),
        Fact("The color startup hook selects GPIO.BOARD numbering, configures each channel pin as an output LOW, "
             "creates one 2000 Hz PWM object per channel and starts each at duty 0.",
             source="upstream_code", ref=f"{RGB}:53-65"),
        Fact("The color shutdown hook sets every PWM channel to duty 0, stops it, drives every pin LOW and calls "
             "GPIO.cleanup.", source="upstream_code", ref=f"{RGB}:67-75"),
        Fact("The rgb IOC argument parser sets default_prefix='rpi:'.", source="upstream_code", ref=f"{RGB}:80"),
        Fact("The rgb IOC requires --red, --green and --blue BOARD pin arguments and passes them to IOC(red=..., "
             "green=..., blue=...).", source="upstream_code", ref=f"{RGB}:84-91"),
    ]
    safe_state = ("Hat state PV written 0 and read back 0: write_state drove every configured hat pin LOW (proven "
                  "only as the IOC's executed put, not as a sensed pin level). The stop does not run GPIO.cleanup; "
                  "the rgb IOC and anything else on the Pi are outside it.")
    tag_config = {"profile": "epics-ca", "timeout_ms": 1000, "points": POINTS}
    parameters = {
        "hat_state": Field(
            "integer", unit="1", writable=True,
            limit=Limit.operator_required(
                "the IOC maps any truthy value to GPIO.HIGH and any falsy value to GPIO.LOW; no line states a "
                "numeric input range for the state PV"),
            description="Hat state PV; 0 drives the configured pins LOW and any other value drives them HIGH "
                        "(the IOC stores the resulting HIGH/LOW level)"),
    }
    reads = {"hat_state": {"point": "state"}}
    writes = {"hat_state": {"point": "state"}}
    commands = {
        _HAT_ON: {
            "steps": [{"write": "state", "value": 1}],
            "confirm": [{"point": "state", "equals": 1}],
            "result": {"hat_state": {"point": "state"}},
        },
        _ALL_OFF: dict(_STOP, result={"hat_state": {"point": "state"}}),
    }
    actions = {
        _HAT_ON: Action(
            name="hat_on", risk="R1", output={"hat_state": _STATE},
            description="Drive the hat pins HIGH through the state PV and confirm the state PV reads 1"),
        _ALL_OFF: Action(
            name="all_off", safe_state=True, risk="R1", output={"hat_state": _STATE},
            description="Write state 0 (every configured hat pin LOW) and confirm it reads back; the declared stop"),
    }
    safety_bindings = {"estop": _STOP}
