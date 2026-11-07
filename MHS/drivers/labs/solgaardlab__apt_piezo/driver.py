"""OpenMHS driver for gh.solgaardlab/apt_piezo: one Thorlabs APT piezo channel.

A direct Driver (decorated methods) over the upstream piezo module class
``interface.module:Module``. The clone is a partial Thorlabs APT implementation:
``APT`` scans the bays of a BPC-303 controller over FTDI and builds one ``Module``
per used bay (``apt.py:12-21``); every ``Module`` writes framed APT messages
through ``protocol.message.Message`` (``interface/module.py:29-70``).

The clone has no position query and no mode query for a module, so the driver
publishes the commanded state it has sent. It never claims a measured position.

* reads: last commanded travel, last commanded control mode and the ``max_travel``
  value configured on the upstream Module object;
* writes: ``position`` (native ``move``) and ``closed_loop`` (native
  ``set_closed_loop``);
* actions: ``move_piezo`` (native ``move``) and ``zero_piezo`` (native ``zero``,
  which is also the safe-state action);
* the native stop is ``zero()``: the clone defines no separate stop command.

No text file of the clone states the travel range of an attached piezo stage.
The ``max_travel`` argument that ``APT`` passes to a Module is a library
configuration (``apt.py:21``), not a stage specification, so both position
inputs are ``Limit.operator_required`` and the site supplies the travel range
(``site-limits.example.json`` shows the overlay).

Every Fact cites a line of the clone at the pinned commit
677eb8f632b6b1d7c84c1fd83a5821239331e4a5. This package is model-authored and
unreviewed: the gate runs the fake backend only, and the hardware path has never
been run.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write

_TRAVEL_LIMIT_REASON = (
    "no text file of the clone states the travel of an attached piezo stage; Module.move clamps to max_travel, "
    "which APT supplies as a fixed constructor argument (apt.py:21), not a stage specification; the site supplies "
    "the travel range of its stage"
)


class AptPiezo(Driver):
    device_id = "apt-piezo"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R1"
    native = "interface.module:Module"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakePiezoModule"}
    vendor, model = "Thorlabs", "BPC-303 piezo controller (one bay)"
    display_name = "Thorlabs APT piezo channel (interface.module.Module)"
    tags = ["piezo", "thorlabs", "apt", "motion", "actuator"]
    facts = [
        Fact("The clone is a Thorlabs APT controller compatibility library for the BPC-303 controller through USB",
             source="vendor_doc", ref="README.md:3-9"),
        Fact("The README gives the move argument in microns", source="vendor_doc", ref="README.md:34"),
        Fact("The README lists piezo zeroing, control-mode changes and closed-loop piezo movement",
             source="vendor_doc", ref="README.md:16-18"),
        Fact("Module.__init__ enables closed-loop mode and sends the zero-position message",
             source="upstream_code", ref="interface/module.py:25-27"),
        Fact("Module.move clamps the requested travel between 0 and the configured max_travel",
             source="upstream_code", ref="interface/module.py:37-38"),
        Fact("Module.move sends message 0x0646 with a 2-byte channel word and a 2-byte output position computed "
             "from 0 to 32767", source="upstream_code", ref="interface/module.py:29-50"),
        Fact("Module.zero sends message 0x0658 with payload 0x01,0x00 to the module bay",
             source="upstream_code", ref="interface/module.py:52-57"),
        Fact("Module.set_closed_loop sends message 0x0640 with 0x01,0x02 for closed loop and 0x01,0x01 for open loop",
             source="upstream_code", ref="interface/module.py:59-70"),
        Fact("APT detects used bays among 10 and constructs each Module with a fixed max_travel constructor "
             "argument", source="upstream_code", ref="apt.py:12-21"),
        Fact("The controller opens the FTDI device 0x0403:0xfaf0 at 115200 baud, 8 data bits, 1 stop bit and no "
             "parity", source="upstream_code", ref="interface/controller.py:42-51"),
    ]
    safe_state = "piezo output commanded to its zero position (native zero())"

    # Last commanded values. Module.__init__ enables closed loop and sends the
    # zero message (interface/module.py:25-27), and a Module has no readback.
    _position = 0.0
    _closed_loop = True

    # -- reads ------------------------------------------------------------------------------------------------
    @read("position", unit="um",
          description="Last commanded piezo travel; the clone has no position readback, so it is 0 after "
                      "construction and the last value this driver sent afterwards")
    def position(self):
        return self._position

    @read("closed_loop", type="boolean",
          description="Last commanded control mode; True after construction because Module.__init__ enables "
                      "closed loop and the clone has no mode readback")
    def closed_loop(self):
        return self._closed_loop

    @read("max_travel", unit="um",
          description="Maximum travel configured on the upstream Module object (the max_travel constructor "
                      "argument, not a stage specification)")
    def max_travel(self):
        return self.native.max_travel

    # -- writes -------------------------------------------------------------------------------------------------
    @write("position", unit="um", description="Commanded piezo travel in micrometres (native move())",
           limit=Limit.operator_required(_TRAVEL_LIMIT_REASON))
    def set_position(self, value):
        self.native.move(value)
        self._position = float(value)
        return float(value)

    @write("closed_loop", type="boolean",
           description="Enable (True) or disable (False) the piezo closed-loop mode (native set_closed_loop())")
    def set_closed_loop(self, value):
        self.native.set_closed_loop(bool(value))
        self._closed_loop = bool(value)
        return bool(value)

    # -- actions -------------------------------------------------------------------------------------------------
    @action(name="x-cap.solgaardlab.move_piezo.v1",
            description="Command the piezo module to a travel in micrometres (native move())",
            input={"position_um": Field("number", unit="um", description="Target piezo travel in micrometres",
                                        limit=Limit.operator_required(_TRAVEL_LIMIT_REASON))},
            output={"position_um": Field("number", unit="um",
                                         description="Commanded piezo travel sent to the native move()")})
    def move_piezo(self, position_um):
        self.native.move(position_um)
        self._position = float(position_um)
        return {"position_um": float(position_um)}

    @action(name="x-cap.solgaardlab.zero_piezo.v1", safe_state=True,
            description="Command the piezo to its zero position (native zero()); it takes no input and is the "
                        "safe state",
            output={"position_um": Field("number", unit="um",
                                         description="Commanded piezo travel after the native zero() (the zero "
                                                     "position)")})
    def zero_piezo(self):
        self.native.zero()
        self._position = 0.0
        return {"position_um": 0.0}

    # -- safety --------------------------------------------------------------------------------------------------
    @estop(native="zero")
    def stop(self):
        """The only stop the clone defines: zero() commands the piezo output to zero."""
        self.native.zero()
        self._position = 0.0
