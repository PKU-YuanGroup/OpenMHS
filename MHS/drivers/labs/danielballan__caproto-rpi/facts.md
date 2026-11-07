OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.danielballan/caproto-rpi

Every fact cites the pinned clone at commit `3642405070a513369de87c7c684962cbd148bcff`. `upstream_code` refs name
`path/in/clone:LINE` or a bounded range. The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

Tags: `epics`, `epics-ca`, `caproto`, `raspberry-pi`, `gpio`, `led`, `tag-bridge`.

## Facts

| fact | source | ref |
|---|---|---|
| iocs/hat.py defines IOC with a state pvproperty (default 0) whose put callback is write_state; write_state maps a truthy value to GPIO.HIGH and a falsy value to GPIO.LOW and writes that level to every configured pin. | upstream_code | iocs/hat.py:25-34 |
| The state startup hook selects GPIO.BOARD numbering, configures every pin as an output and drives it LOW; the shutdown hook drives every pin LOW and calls GPIO.cleanup. | upstream_code | iocs/hat.py:36-47 |
| The hat IOC requires a comma-separated --pins argument, converts each token to int and passes the list to IOC(pins=...). | upstream_code | iocs/hat.py:56-63 |
| The hat IOC argument parser sets default_prefix='rpi:'. | upstream_code | iocs/hat.py:52 |
| The hats.yml playbook copies only hat.py into /opt/iocs. | upstream_code | hats.yml:10-16 |
| iocs/rgb.py defines IOC with a color pvproperty whose default value is the one-element list ['000000']; write_color parses value[0] as a base-16 integer, sets every channel duty cycle and returns value. | upstream_code | iocs/rgb.py:45-51 |
| rescale maps an 8-bit channel value to 100 * (x / 255)**2.8, a 0-100 duty-cycle scale with gamma 2.8; the comment attributes 2.8 to the RGB LED vendor. | upstream_code | iocs/rgb.py:19-26 |
| duty_cycle extracts the red, green and blue 8-bit channels with the masks 0xff0000, 0x00ff00 and 0x0000ff and rescales each. | upstream_code | iocs/rgb.py:29-36 |
| The color startup hook selects GPIO.BOARD numbering, configures each channel pin as an output LOW, creates one 2000 Hz PWM object per channel and starts each at duty 0. | upstream_code | iocs/rgb.py:53-65 |
| The color shutdown hook sets every PWM channel to duty 0, stops it, drives every pin LOW and calls GPIO.cleanup. | upstream_code | iocs/rgb.py:67-75 |
| The rgb IOC argument parser sets default_prefix='rpi:'. | upstream_code | iocs/rgb.py:80 |
| The rgb IOC requires --red, --green and --blue BOARD pin arguments and passes them to IOC(red=..., green=..., blue=...). | upstream_code | iocs/rgb.py:84-91 |

## PV point (tag_config)

| point | PV suffix | type | access | ref |
|---|---|---|---|---|
| state | state | integer | read-write | iocs/hat.py:34 |

The Channel Access name is the deployment prefix plus the pvproperty attribute name. The shipped supervisor
configuration starts the hat IOC with `--pins 11,16` and a templated `--prefix=hat{{ prefix }}:`
(`supervisor_config/hat.conf:2`). The operator supplies `prefix` to `native.py`; it is deployment data, not a fact of
the clone.

## Scope and what is not covered

- The package serves the hat IOC (`iocs.hat:IOC`, the card's first entry symbol) through its `state` PV, not the
  in-process Python object.
- NOT COVERED: the rgb IOC (`iocs.rgb:IOC`, the `color` PV). It is a separate IOC process; the shipped playbook
  `hats.yml` deploys only `hat.py` (`hats.yml:10-16`); the shipped supervisor configurations give BOARD pin 11 to both
  IOCs (`supervisor_config/hat.conf:2` `--pins 11,16`, `supervisor_config/rgb.conf:2` `--blue 11`), so the two do not
  run side by side as shipped; and `write_color` parses `value[0]` of a PV declared as the one-element list
  `['000000']` (`iocs/rgb.py:45-51`): what a written colour does depends on how the installed caproto server hands a
  one-element string array to the put hook (a list, or the unwrapped string, whose `value[0]` is its first hex digit),
  which the clone does not show. The tag-bridge helper does not encode arrays in this version.
- No line states a numeric input range for the state PV. It is declared with `Limit.operator_required`; without an
  operator overlay every value is refused with `MHS.SAFETY.LIMITS_UNSET`. The example overlay narrows the endpoint
  to the two levels 0 and 1; the IOC itself maps any truthy/falsy value to HIGH/LOW.
- The stop writes `state = 0` and confirms it with a fresh Channel Access read. That proves the IOC executed the put
  (`write_state` drives the pins LOW per the code), not the electrical state of the pins. It does not call the IOC
  shutdown hook, so it does not run `GPIO.cleanup`; it is not an independent hardware e-stop.
- The fake is an analytic stand-in with a placeholder initial value (state 0), not a recording of a deployed IOC. It
  models no GPIO pin, LED or board failure.
- The hardware backend is a caproto Channel Access client and was never run. A human must sign `reviewed_by` with
  scope `hardware` before it opens; this package keeps `reviewed_by: null`.
- Licence: the clone has no `LICENSE` file and the card records NOASSERTION / unknown; publication is a human
  review decision.
