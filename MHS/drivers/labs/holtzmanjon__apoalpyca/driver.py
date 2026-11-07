"""OpenMHS TagDriver for the APO 1m Ash Dome rotation through its ASCOM Alpaca dome server.

The upstream repository is an Alpaca device server. ``device/dome_app.py``
routes the ``dome`` device type, and the responders in ``device/dome.py``
expose the low-level ``APOAshDome`` class as Alpaca properties and methods.
This package therefore declares the Alpaca members of that server as
``tag_config`` points; the SDK's TagBridge reads and invokes them through a
transport. The hardware transport (``native.py``) is an HTTP Alpaca client for
the operator's server address. It never starts before a human signs
``reviewed_by`` with scope hardware: every tag-bridge hardware backend needs
that signature, at every risk class and for every author.

Scope: dome rotation (slew, park, find home, set park) and read-only status.
The shutters are NOT COVERED: OpenShutter and CloseShutter drive relays on
fixed timers held only in local variables (86 s and 120 s,
``device/APOAshDome.py:35-36``, ``:204-287``) and nothing aborts a running
shutter cycle, so no source-backed stop exists for them; the weather and
watchdog threads also close the shutter on their own (``:112-140``).

The stop is the server's own ``AbortSlew`` method, which calls
``APOAshDome.abort_slew`` and then ``stop``: that writes the rotation relay
``DOME_POWER`` off and sets ``slewing`` false, and the package confirms the
stop by reading the ``slewing`` property back. That is the server's software
flag, not sensed motion: the dome coasts.

Thread-start race: SlewToAzimuth, Park and FindHome return as soon as a worker
thread is started; the thread energises the relay later, in ``rotate()``, which
first calls ``stop()`` and then switches the relay on and sets ``slewing``
(``device/APOAshDome.py:342-357``). An AbortSlew that lands in between is
undone. The package therefore completes those commands only after a fresh
``slewing == True`` read within ``confirm_ms``; a stop that arrives meanwhile
overlaps a request in flight, is reported not achieved and is retried. A worker
slower than ``confirm_ms`` (Park also waits for the weather check before its
slew thread starts), a target already within tolerance, and slews started by
another client of the same server end as unknown outcomes or stay a residual
hazard: the dome's physical power switch is the real stop, which only a human
may cite as ``estop_physical_ref``.
"""

from mhs.driver import Action, Fact, Field, Limit, TagDriver

DOME = "device/dome.py"
DOME_APP = "device/dome_app.py"
LOW = "device/APOAshDome.py"
SAFETY = "device/APOSafety.py"

#: Alpaca members exactly as the responder classes in device/dome.py name them.
POINTS = {
    "azimuth": {"member": "azimuth", "type": "number", "access": "read",
                "source_ref": f"{DOME}:208",
                "description": "Dome azimuth property; the responder returns the cached APOAshDome.azimuth"},
    "shutterstatus": {"member": "shutterstatus", "type": "integer", "access": "read",
                      "source_ref": f"{DOME}:359",
                      "description": "ASCOM shutter state: 0 open, 1 closed, 2 opening, 3 closing, 4 error"},
    "slewing": {"member": "slewing", "type": "boolean", "access": "read",
                "source_ref": f"{DOME}:415",
                "description": "The server's slewing flag (set by rotate, cleared by stop); not sensed motion"},
    "athome": {"member": "athome", "type": "boolean", "access": "read",
               "source_ref": f"{DOME}:178",
               "description": "Home switch state, read through the server's athome property"},
    "atpark": {"member": "atpark", "type": "boolean", "access": "read",
               "source_ref": f"{DOME}:193",
               "description": "Whether the encoder azimuth is within the park tolerance"},
    "abortslew": {"member": "abortslew", "method": True,
                  "source_ref": f"{DOME}:432",
                  "description": "AbortSlew: turn off dome rotation power"},
    "findhome": {"member": "findhome", "method": True,
                 "source_ref": f"{DOME}:466",
                 "description": "FindHome: rotate until the home switch asserts"},
    "park": {"member": "park", "method": True,
             "source_ref": f"{DOME}:500",
             "description": "Park: slew to the stored park position"},
    "setpark": {"member": "setpark", "method": True,
                "source_ref": f"{DOME}:517",
                "description": "SetPark: store the current azimuth as the park position"},
    "slewtoazimuth": {"member": "slewtoazimuth", "method": True, "params": {"Azimuth": "integer"},
                      "source_ref": f"{DOME}:563-570",
                      "description": "SlewToAzimuth: start an asynchronous slew to the given azimuth"},
}

_AZIMUTH = Field("integer", unit="deg",
                 limit=Limit(min=0, max=360, source="upstream_code", ref=f"{DOME}:578-580"),
                 description="Target azimuth in whole degrees; the responder casts the form value to int")
_SLEWING = Field("boolean", description="Server slewing flag read after the command")
_ATHOME = Field("boolean", description="Home switch state read after the command")
_ATPARK = Field("boolean", description="Park position state read after the command")

SLEW, PARK = "x-cap.holtzmanjon.slew_azimuth.v1", "x-cap.holtzmanjon.park.v1"
HOME, SETPARK = "x-cap.holtzmanjon.find_home.v1", "x-cap.holtzmanjon.set_park.v1"
ABORT = "x-cap.holtzmanjon.abort_slew.v1"

_STOP = {"steps": [{"invoke": "abortslew"}], "confirm": [{"point": "slewing", "equals": False}]}
#: A started rotation: the worker thread's rotate() has switched the relay on and set the flag.
_STARTED = [{"point": "slewing", "equals": True}]


class ApoAshDome(TagDriver):
    device_id = "apo-ash-dome"
    device_kind = "device"
    mode = "hardware"
    risk = "R2"
    native = "device.APOAshDome:APOAshDome"
    backends = {"fake": ".fake:FakeApoDome", "hardware": ".native:connect"}
    vendor, model = "Apache Point Observatory", "1m Ash Dome"
    display_name = "APO 1m Ash Dome rotation (ASCOM Alpaca dome server)"
    tags = ["dome", "alpaca", "ascom", "observatory", "tag-bridge"]
    facts = [
        Fact("The dome app registers the dome device type with init_routes(falc_app, 'dome', dome).",
             source="upstream_code", ref=f"{DOME_APP}:258"),
        Fact("The dome app serves every route from one wsgiref simple_server with serve_forever.",
             source="upstream_code", ref=f"{DOME_APP}:276-280"),
        Fact("start_dome_device constructs one APOAshDome(logger=logger) for the dome responders.",
             source="upstream_code", ref=f"{DOME}:55-58"),
        Fact("The azimuth responder returns the dome_dev.azimuth attribute; it does not call get_azimuth.",
             source="upstream_code", ref=f"{DOME}:208-216"),
        Fact("get_azimuth recomputes azimuth from the encoder position, enc.pos/steps_per_degree + HOME_POSITION "
             "modulo 360, and stores it in self.azimuth.", source="upstream_code", ref=f"{LOW}:359-364"),
        Fact("The shutterstatus responder returns dome_dev.shutterstatus as an integer.", source="upstream_code",
             ref=f"{DOME}:359-368"),
        Fact("ShutterState defines open 0, closed 1, opening 2, closing 3 and error 4.", source="upstream_code",
             ref=f"{LOW}:50-55"),
        Fact("abortslew calls dome_dev.abort_slew().", source="upstream_code", ref=f"{DOME}:432-441"),
        Fact("abort_slew calls stop; stop writes relay DOME_POWER 0 and sets slewing false.", source="upstream_code",
             ref=f"{LOW}:322-333"),
        Fact("rotate calls stop, resets the encoder, sets the DOME_DIRECTION relay, then switches the DOME_POWER "
             "relay on and sets slewing true.", source="upstream_code", ref=f"{LOW}:342-357"),
        Fact("set_relay sleeps 0.2 s after every relay call.", source="upstream_code", ref=f"{LOW}:432-442"),
        Fact("open_upper and close_upper drive UPPER_POWER and start a Timer(upper_time, ...) held in a local "
             "variable that schedules set_upper_open or set_upper_closed.", source="upstream_code",
             ref=f"{LOW}:204-224"),
        Fact("UPPER_TIME is 86 and LOWER_TIME is 120.", source="upstream_code", ref=f"{LOW}:35-36"),
        Fact("open_shutter returns without opening when APOSafety.issafe() is false.", source="upstream_code",
             ref=f"{LOW}:266-276"),
        Fact("close_shutter closes the upper shutter when lower is false and then runs close_louvers, which executes "
             "/home/ocs/bin/ms1 off 9.", source="upstream_code", ref=f"{LOW}:278-293"),
        Fact("monitor_weather and reset_watchdog loop forever and call close_shutter when issafe() is false and the "
             "shutter is neither closed nor closing.", source="upstream_code", ref=f"{LOW}:112-140"),
        Fact("The slewtoazimuth responder casts the Azimuth form field to int, rejects a value outside 0..360 and "
             "calls dome_dev.slewtoazimuth(azimuth).", source="upstream_code", ref=f"{DOME}:563-584"),
        Fact("slewtoazimuth calls close_shutter instead of slewing when issafe() is false and the shutter is neither "
             "closed nor closing; otherwise it starts a thread running gotoazimuth.", source="upstream_code",
             ref=f"{LOW}:366-376"),
        Fact("gotoazimuth returns without rotating when the target is within DOME_TOLERANCE; otherwise it calls "
             "rotate, polls get_azimuth in a loop without a sleep until within DOME_TOLERANCE/4 of the target "
             "offset by one degree or 180 s, then calls stop.", source="upstream_code", ref=f"{LOW}:378-404"),
        Fact("DOME_TOLERANCE is 3.", source="upstream_code", ref=f"{LOW}:41"),
        Fact("park starts a thread only when not atpark; sendpark calls slewtoazimuth(park_position).",
             source="upstream_code", ref=f"{LOW}:309-320"),
        Fact("home starts a thread only when not athome; sendhome calls rotate(1) and waits up to 180 s for the "
             "home switch; only when the switch asserts does it switch DOME_POWER off and clear slewing, and when "
             "the timer expires it only logs.", source="upstream_code", ref=f"{LOW}:148-176"),
        Fact("atpark compares the encoder azimuth with park_position within DOME_TOLERANCE; set_park stores the "
             "current azimuth as the park position.", source="upstream_code", ref=f"{LOW}:295-307"),
        Fact("APOSafety.stat sends a UDP request and waits in recvfrom on a socket without a timeout, then exec()s "
             "a slice of the reply.", source="upstream_code", ref=f"{SAFETY}:65-83"),
        Fact("The watchdog thread toggles a relay on the dome control board every two minutes; the control box has an "
             "internal timer that closes the dome after 3-4 minutes if the relay is not reset.", source="vendor_doc",
             ref="docs/apoashdome.txt:14-17"),
    ]
    safe_state = ("Dome rotation relay commanded off by AbortSlew and the server's slewing flag read back false; not "
                  "sensed motion (the dome coasts). Shutter timers, the weather and watchdog threads and the louvers "
                  "are outside the stop, and a slew thread that has not yet run rotate() can re-energise the relay "
                  "after it; the dome's power switch is the real stop.")
    tag_config = {"profile": "alpaca", "device_type": "dome", "device_number": 0,
                  "device_type_ref": f"{DOME_APP}:258",
                  "timeout_ms": 1000, "confirm_ms": 1500, "poll_ms": 100, "points": POINTS}
    parameters = {
        "azimuth": Field("number", unit="deg", description="Dome azimuth from the server's azimuth property"),
        "shutterstatus": Field("integer", description="ASCOM shutter state: 0 open, 1 closed, 2 opening, "
                                                      "3 closing, 4 error"),
        "slewing": Field("boolean", description="Dome rotation in progress according to the server's flag"),
        "athome": Field("boolean", description="Home switch state reported by the server"),
        "atpark": Field("boolean", description="Whether the server reports the dome at the park position"),
    }
    reads = {"azimuth": {"point": "azimuth"}, "shutterstatus": {"point": "shutterstatus"},
             "slewing": {"point": "slewing"}, "athome": {"point": "athome"}, "atpark": {"point": "atpark"}}
    commands = {
        SLEW: {"steps": [{"invoke": "slewtoazimuth", "args": {"Azimuth": {"input": "azimuth"}}}],
               "confirm": _STARTED,
               "result": {"target_azimuth": {"input": "azimuth"}, "slewing": {"point": "slewing"}}},
        PARK: {"steps": [{"invoke": "park"}], "confirm": _STARTED,
               "result": {"slewing": {"point": "slewing"}}},
        HOME: {"steps": [{"invoke": "findhome"}], "confirm": _STARTED,
               "result": {"slewing": {"point": "slewing"}, "athome": {"point": "athome"}}},
        SETPARK: {"steps": [{"invoke": "setpark"}], "result": {"atpark": {"point": "atpark"}}},
        ABORT: dict(_STOP, result={"slewing": {"point": "slewing"}}),
    }
    actions = {
        SLEW: Action(name="slew_azimuth", risk="R2",
                     input={"azimuth": _AZIMUTH},
                     output={"target_azimuth": Field("integer", unit="deg",
                                                     description="Requested azimuth as sent to the server"),
                             "slewing": _SLEWING},
                     description=("Start a SlewToAzimuth and wait until the server reports slewing (relay on). "
                                  "Completion is a started rotation, not arrival; no start within 1.5 s is unknown")),
        PARK: Action(name="park", risk="R2", output={"slewing": _SLEWING},
                     description=("Start a Park slew to the stored park position and wait until the server reports "
                                  "slewing; already parked or no start within 1.5 s is unknown")),
        HOME: Action(name="find_home", risk="R2",
                     output={"slewing": _SLEWING, "athome": _ATHOME},
                     description=("Start a FindHome rotation and wait until the server reports slewing; already "
                                  "home or no start within 1.5 s is unknown")),
        SETPARK: Action(name="set_park", risk="R1", output={"atpark": _ATPARK},
                        description=("Store the current azimuth as the park position through SetPark; no motion "
                                     "is commanded")),
        ABORT: Action(name="abort_slew", safe_state=True, risk="R2", output={"slewing": _SLEWING},
                      description=("Switch the rotation relay off through AbortSlew and confirm the server's slewing "
                                   "flag is false; the dome coasts and the shutters are not affected")),
    }
    safety_bindings = {"estop": _STOP}
