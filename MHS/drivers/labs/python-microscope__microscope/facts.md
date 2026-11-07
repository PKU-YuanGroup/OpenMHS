# Facts and tags for gh.python-microscope/microscope

Every fact cites its source at commit `47c13d0342dca476a279f2de2da5b84ce2162326`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The laser is opened on a serial line at 115200 baud, 8N1 with a 0.1 s timeout; the constructor queries the serial number (sn?), disables autostart (@cobas 0) and reads the head's maximum power in mW (gmlp?) | upstream_code | microscope/lights/cobolt.py:46-66 |
| initialize() disables direct control (@cobasdr 0) and forces autostart on (@cob1) | upstream_code | microscope/lights/cobolt.py:109-114 |
| Emission is turned on with the l1 command after get_is_on() confirms it, and get_is_on() reads l? and returns True when the reply is b'1' | upstream_code | microscope/lights/cobolt.py:118-141 |
| The native disable sends the l0 command and returns its reply; it does not clear the Device.enabled flag that enable() sets | upstream_code | microscope/lights/cobolt.py:131-135 |
| get_status sends l?, p?, pa?, f? and hrs? and returns each reply as a status line | upstream_code | microscope/lights/cobolt.py:86-98 |
| A power fraction is converted to mW of the head's maximum power and written as '@cobasp <watts>' with four decimals; the comment states that there is no minimum power and any non-negative number is accepted | upstream_code | microscope/lights/cobolt.py:156-164 |
| The LightSource power property is in the [0, 1] interval, and its setter clips the argument to that interval before reaching _do_set_power | upstream_code | microscope/abc.py:1245-1249 |
| OnlyTriggersBulbOnSoftwareMixin fixes trigger_type to SOFTWARE and trigger_mode to BULB, and its _do_trigger raises IncompatibleStateError ('trigger does not make sense in trigger mode bulb, only enable') | upstream_code | microscope/_utils.py:108-140 |

Limits: the power set point is bounded by `Limit(min=0, max=1, source="upstream_code", ref="microscope/abc.py:1245-1247")`,
the [0, 1] interval of the upstream `LightSource.power` property. The head's maximum power in mW is read from the
head at connect (`gmlp?`, microscope/lights/cobolt.py:64), so the absolute wattage is a property of the head, not a
bound of this driver; the driver publishes power as a fraction of it. No operator overlay is needed.

Safety: the e-stop and the safe-state action `x-cap.python-microscope.disable_emission.v1` both call the native
`disable()` (`l0`). The driver is R2 (a laser above class 1, MHS/spec/04-safety.md; a model review raised it from the card's R1, and a
class 3B or 4 head is R3); the safe-state action is its independent stop, and the clone documents no hardware e-stop
on the serial line, so none is claimed.

Tags: laser, light-source, serial
