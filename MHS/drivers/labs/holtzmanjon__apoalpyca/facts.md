OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.holtzmanjon/apoalpyca

Every fact cites the pinned clone at commit `3d4c48ec092c7dfd095f47b30efe9eb29ca2d031`. `upstream_code` refs name
`path/in/clone:LINE`; `vendor_doc` refs name a text documentation file. The same facts are in `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

Tags: `dome`, `alpaca`, `ascom`, `observatory`, `tag-bridge`.

## Facts

| fact | source | ref |
|---|---|---|
| The dome app registers the dome device type with init_routes(falc_app, 'dome', dome). | upstream_code | device/dome_app.py:258 |
| The dome app serves every route from one wsgiref simple_server with serve_forever. | upstream_code | device/dome_app.py:276-280 |
| start_dome_device constructs one APOAshDome(logger=logger) for the dome responders. | upstream_code | device/dome.py:55-58 |
| The azimuth responder returns the dome_dev.azimuth attribute; it does not call get_azimuth. | upstream_code | device/dome.py:208-216 |
| get_azimuth recomputes azimuth from the encoder position, enc.pos/steps_per_degree + HOME_POSITION modulo 360, and stores it in self.azimuth. | upstream_code | device/APOAshDome.py:359-364 |
| The shutterstatus responder returns dome_dev.shutterstatus as an integer. | upstream_code | device/dome.py:359-368 |
| ShutterState defines open 0, closed 1, opening 2, closing 3 and error 4. | upstream_code | device/APOAshDome.py:50-55 |
| abortslew calls dome_dev.abort_slew(). | upstream_code | device/dome.py:432-441 |
| abort_slew calls stop; stop writes relay DOME_POWER 0 and sets slewing false. | upstream_code | device/APOAshDome.py:322-333 |
| rotate calls stop, resets the encoder, sets the DOME_DIRECTION relay, then switches the DOME_POWER relay on and sets slewing true. | upstream_code | device/APOAshDome.py:342-357 |
| set_relay sleeps 0.2 s after every relay call. | upstream_code | device/APOAshDome.py:432-442 |
| open_upper and close_upper drive UPPER_POWER and start a Timer(upper_time, ...) held in a local variable that schedules set_upper_open or set_upper_closed. | upstream_code | device/APOAshDome.py:204-224 |
| UPPER_TIME is 86 and LOWER_TIME is 120. | upstream_code | device/APOAshDome.py:35-36 |
| open_shutter returns without opening when APOSafety.issafe() is false. | upstream_code | device/APOAshDome.py:266-276 |
| close_shutter closes the upper shutter when lower is false and then runs close_louvers, which executes /home/ocs/bin/ms1 off 9. | upstream_code | device/APOAshDome.py:278-293 |
| monitor_weather and reset_watchdog loop forever and call close_shutter when issafe() is false and the shutter is neither closed nor closing. | upstream_code | device/APOAshDome.py:112-140 |
| The slewtoazimuth responder casts the Azimuth form field to int, rejects a value outside 0..360 and calls dome_dev.slewtoazimuth(azimuth). | upstream_code | device/dome.py:563-584 |
| slewtoazimuth calls close_shutter instead of slewing when issafe() is false and the shutter is neither closed nor closing; otherwise it starts a thread running gotoazimuth. | upstream_code | device/APOAshDome.py:366-376 |
| gotoazimuth returns without rotating when the target is within DOME_TOLERANCE; otherwise it calls rotate, polls get_azimuth in a loop without a sleep until within DOME_TOLERANCE/4 of the target offset by one degree or 180 s, then calls stop. | upstream_code | device/APOAshDome.py:378-404 |
| DOME_TOLERANCE is 3. | upstream_code | device/APOAshDome.py:41 |
| park starts a thread only when not atpark; sendpark calls slewtoazimuth(park_position). | upstream_code | device/APOAshDome.py:309-320 |
| home starts a thread only when not athome; sendhome calls rotate(1) and waits up to 180 s for the home switch; only when the switch asserts does it switch DOME_POWER off and clear slewing, and when the timer expires it only logs. | upstream_code | device/APOAshDome.py:148-176 |
| atpark compares the encoder azimuth with park_position within DOME_TOLERANCE; set_park stores the current azimuth as the park position. | upstream_code | device/APOAshDome.py:295-307 |
| APOSafety.stat sends a UDP request and waits in recvfrom on a socket without a timeout, then exec()s a slice of the reply. | upstream_code | device/APOSafety.py:65-83 |
| The watchdog thread toggles a relay on the dome control board every two minutes; the control box has an internal timer that closes the dome after 3-4 minutes if the relay is not reset. | vendor_doc | docs/apoashdome.txt:14-17 |

## Alpaca points (tag_config)

| point | Alpaca member | kind | access | ref |
|---|---|---|---|---|
| azimuth | `azimuth` | number (deg) | read | device/dome.py:208 |
| shutterstatus | `shutterstatus` | integer | read | device/dome.py:359 |
| slewing | `slewing` | boolean | read | device/dome.py:415 |
| athome | `athome` | boolean | read | device/dome.py:178 |
| atpark | `atpark` | boolean | read | device/dome.py:193 |
| abortslew | `abortslew` | method | invoke | device/dome.py:432 |
| findhome | `findhome` | method | invoke | device/dome.py:466 |
| park | `park` | method | invoke | device/dome.py:500 |
| setpark | `setpark` | method | invoke | device/dome.py:517 |
| slewtoazimuth | `slewtoazimuth` | method, form `Azimuth` integer | invoke | device/dome.py:563-570 |

The device type cited by `device_type_ref` is `dome` at `device/dome_app.py:258`. The server has one dome instance
(`maxdev = 0`, `device/dome.py:33`), so `device_number` is 0. `tag_config` sets `confirm_ms` 1500 and `poll_ms` 100.

## Scope, limits and stop

- The package integrates the rotation of the APO 1m Ash Dome through its Alpaca server, plus read-only status. The
  repository also contains separate TCube, TC300, K8056 and LTS150 devices (and focuser, switch and safety-monitor
  servers); they are not part of this dome package.
- NOT COVERED: OpenShutter and CloseShutter. They switch shutter relays on fixed timers (86 s upper, 120 s lower)
  held only in local variables; nothing aborts a running shutter cycle, so no source-backed stop exists for them
  (`device/APOAshDome.py:35-36`, `:204-287`). The weather and watchdog threads close the shutter on their own
  (`:112-140`), and CloseShutter also runs the louver subprocess `/home/ocs/bin/ms1 off 9`. The shutter status stays
  readable.
- The only numeric input is the SlewToAzimuth target. The responder converts the form value to `int` and rejects
  anything outside 0..360 (`device/dome.py:570-580`), so the input is an integer with a sourced 0..360 limit.
  A fractional azimuth is refused rather than silently truncated by the driver.
- Started rotation, not arrival: SlewToAzimuth, Park and FindHome return when the server has started a worker
  thread; the thread switches the relay on later, in `rotate()` (after three relay calls of 0.2 s each). The package
  completes each command only after a fresh `slewing == True` read within `confirm_ms` (1.5 s). A target within
  `DOME_TOLERANCE` (3 degrees), a dome already parked or home, an unsafe-weather SlewToAzimuth (which closes the
  shutter instead), a Park whose worker waits on the weather check, and a short slew that ends between two polls
  all end `MHS.OUTCOME.UNKNOWN`; ordinary commands are then refused until a confirmed stop. This is conservative.
- The stop is `AbortSlew` confirmed by reading the `slewing` property back. The responder calls
  `APOAshDome.abort_slew()`, which calls `stop()`: `DOME_POWER` is written 0 and `slewing` is set false. This is the
  server's own flag, not a read of the relay or the encoder, and the dome coasts. A stop that arrives while a
  slew, park or home command is still waiting for its start is reported not achieved and retried after the command
  ends (the bridge's in-flight rule).
- Thread-start race (residual): an AbortSlew that lands after a worker thread was started and before its `rotate()`
  is undone by `rotate()`, possibly after the stop's `slewing == False` read. The started-rotation confirmation
  narrows this to a worker slower than `confirm_ms`, or a slew started by another client of the same server (any
  Alpaca client, including SyncToAzimuth, which also slews, `device/dome.py:619`). The dome's physical power switch
  is the real stop; only a human may cite it as `estop_physical_ref`.
- Once past `rotate()`, the worker loops only call `stop()` again and do not re-energise the relay. After an abort,
  `gotoazimuth` keeps polling without a sleep for up to 180 s, which can slow the server's replies to stop retries
  and reads. If the home switch never asserts, `sendhome` leaves the relay on and `slewing` true after its 180 s
  timer: the dome keeps turning until an AbortSlew.
- The server is one single-threaded `wsgiref` simple_server. A request that blocks holds every other request,
  including AbortSlew: SlewToAzimuth calls `APOSafety.issafe()` before it answers, and `APOSafety.stat` waits in a UDP
  `recvfrom` without a timeout (and `exec()`s a slice of the reply). A blocked server makes the e-stop report
  `MHS.SAFETY.SAFE_STATE_UNREACHED` and retry; it never reports a stop it did not confirm.
- The `azimuth` property is the cached `APOAshDome.azimuth` attribute; the responder does not call `get_azimuth`,
  which is what refreshes it from the encoder. A stale or non-finite value is refused by the codec rather than
  invented.
- NOT COVERED: the weather monitor, the safety-monitor Alpaca device, the louver controller and the watchdog relay
  are not separate capabilities of this package.

## Fake and hardware backend

- The fake is an analytic in-memory Alpaca stand-in, not a recording of the deployed server. It stores placeholder
  property values (all marked `# placeholder` in `fake.py`), sets the slewing flag at once on a started rotation
  (unless its `start_delayed` test switch models a worker that has not reached `rotate()`), starts no rotation for a
  target within `DOME_TOLERANCE` or when already parked or home, clears the flag on AbortSlew, and models no motion,
  encoder, weather check, timer, worker timing or transport failure. Its timing is F0: every method returns
  immediately.
- `native.py` is an HTTP Alpaca client for the operator's host and port; it imports no upstream code and does not
  run in the acceptance gate. Every tag-bridge hardware backend is refused until a human signs `reviewed_by` with
  scope hardware.
