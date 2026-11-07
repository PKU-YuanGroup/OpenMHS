"""OpenMHS driver for gh.czbiohub-sf/python-fish-sorter: the Wago pneumatic valve controller.

The clone's ``fish_sorter.hardware.valve_controller:ValveController`` (line 7) is the Modbus TCP client for the
Wago valve controller of the Fish Sorter v2.  The higher layer ``PickingPipette`` (picking_pipette.py:15) writes
named function codes to its function register: idle (lines 140-147), pressure off/on (149-167) and vacuum off/on
(169-187).  This package binds that controller, not the pipette stage: ``ZaberController`` has no stop, abort or
halt method and its blocking ``move_arm`` calls cannot be cancelled through the clone, so the stage motion is
deliberately NOT covered.  Only the pneumatic outputs of the instrument are controlled here.

The controller program is the CoDeSys project of the clone (``hardware/valve_control/FishSorterValveControl.pro``;
hardware/README.md:3-5).  It is a binary file, so no Fact cites it; its text (readable with ``strings``) says that
the program takes a valid code from the function register (%MW4), copies it to the echo register (%MW6) and runs
that code's step, which sets its Press and Vacuum outputs and writes 0 back to the function register: 128 sets
Vacuum := 0 and Press := 0 ("Press is OFF, Atmos is ON"), 16 (the upstream's vac_on) Vacuum := 1, 17 (vac_off)
Vacuum := 0, 9 Press := 1 and 8 Press := 0.  Its text shows no exit from a running draw (2) or expel (4) sequence
on a new code; the end of such a sequence sets both outputs to 0 and writes 0 to the function register.

* reads: the draw-time, expel-time, function and echo registers (none of them is a sensed valve position);
* writes: the draw and expel times in milliseconds.  No text file of the clone states a range for either
  register, so both are ``Limit.operator_required``: every write is refused ``MHS.SAFETY.LIMITS_UNSET`` until the
  site supplies the range (``site-limits.example.json`` shows an example overlay);
* actions: pressure on/off, vacuum on/off and atmospheric idle as extension ids (no catalogue class binds a
  pressure/vacuum function-code controller), plus the input-free safe-state action.  Each writes its code, checks
  the Modbus reply, then waits at most 0.5 s until the controller has taken the code (the function register reads
  0 and the echo register holds the code).  A Modbus exception reply, or a code the controller cleared without
  taking it, is a failed command; a write that raised, a code still waiting after 0.5 s or a code whose take
  cannot be read back is an unknown outcome; neither is ever a completed command;
* the native e-stop writes the idle code once and checks the Modbus reply without waiting; the safe-state action
  that the runtime runs after it writes the idle code again and confirms that the controller took it, so an
  e-stop completes only when the controller took the idle code.

Every Fact cites a line of the clone at the pinned commit (a8f2409fa6924b1aed83e1224c34a0528b5cb002).  This package
is model-authored and unreviewed: it is checked on the fake backend only, claims no hardware run and no MHS-Device
level.
"""

import threading
import time

from mhs.driver import Cancelled, Driver, DriverFailed, Fact, Field, Limit, OutcomeUnknown, action, estop, read, write

#: Package policy, not a device fact: how long a command waits for the controller program to take its code, and
#: the read-back interval.  The default e-stop budget (1000 ms) covers the native stop plus this wait.
_TAKE_TIMEOUT_S = 0.5
_POLL_S = 0.02
#: Guards the lazy creation of each driver's Modbus transaction lock.
_LOCK_GUARD = threading.Lock()


class FishSorterPneumatics(Driver):
    device_id = "fish-sorter-pneumatics"
    device_kind = "fluid.valve"
    mode = "hardware"
    risk = "R2"
    native = "fish_sorter.hardware.valve_controller:ValveController"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeValveController"}
    vendor, model = "Wago", "CoDeSys pneumatic valve controller of the Fish Sorter v2"
    display_name = "Fish Sorter pneumatic valve controller (Wago, Modbus TCP)"
    tags = ["fish sorter", "pneumatics", "pressure", "vacuum", "valve", "wago", "modbus"]
    facts = [
        Fact("The hardware README lists CODESYS valve control code for use with Wago valve controllers among what "
             "the hardware directory includes", source="vendor_doc", ref="hardware/README.md:3-5"),
        Fact("ValveController communicates with the Wago valve controller to actuate the pressure and vacuum valves; "
             "the Wago controller was programmed with CoDeSys to receive specific function codes",
             source="upstream_code", ref="fish_sorter/hardware/valve_controller.py:7-11"),
        Fact("ValveController stores the config mapping it was given on self.config",
             source="upstream_code", ref="fish_sorter/hardware/valve_controller.py:25"),
        Fact("ValveController._connect creates a ModbusTcpClient with the configured host and port, timeout=5 and "
             "retries=3", source="upstream_code", ref="fish_sorter/hardware/valve_controller.py:30-44"),
        Fact("read_register returns read_holding_registers of count registers at start_address + add_offset and "
             "re-raises any exception", source="upstream_code",
             ref="fish_sorter/hardware/valve_controller.py:68-88"),
        Fact("write_register writes value to start_address + add_offset and returns the reply; on an exception it "
             "closes the client, reconnects and retries the same write once", source="upstream_code",
             ref="fish_sorter/hardware/valve_controller.py:90-114"),
        Fact("The upstream valve test checks rr.isError() and ExceptionResponse after a read: a Modbus exception "
             "reply is not a Python exception but a valid Modbus message", source="upstream_code",
             ref="fish_sorter/hardware/valve_test.py:80-96"),
        Fact("The upstream valve test writes a function code to 12288 + ADDRESS_OFFSET and reads the same register "
             "back", source="upstream_code", ref="fish_sorter/hardware/valve_test.py:98-103"),
        Fact("The shipped pneumatic config sets start_address 12288 and the offsets draw time 0, expel time 2, "
             "function 4, function echo 6 and idle type 14", source="upstream_code",
             ref="fish_sorter/configs/hardware/pneumatic_config.json:9-17"),
        Fact("The shipped function codes are idle_atm 0, draw 2, expel 4, press_off 8, press_on 9, vac_on 16, "
             "vac_off 17 and func_idle 128", source="upstream_code",
             ref="fish_sorter/configs/hardware/pneumatic_config.json:18-28"),
        Fact("PickingPipette.connect creates a ZaberController unless one was passed, creates the ValveController and "
             "writes idle_atm to the func_idle_type register", source="upstream_code",
             ref="fish_sorter/hardware/picking_pipette.py:72-79"),
        Fact("PickingPipette.idle ('Toggles to idle atmospheric pressure') writes func_idle to the function register",
             source="upstream_code", ref="fish_sorter/hardware/picking_pipette.py:140-147"),
        Fact("PickingPipette.pressure(False) writes press_off and pressure(True) writes press_on",
             source="upstream_code", ref="fish_sorter/hardware/picking_pipette.py:149-167"),
        Fact("PickingPipette.vacuum(False) writes vac_off and vacuum(True) writes vac_on",
             source="upstream_code", ref="fish_sorter/hardware/picking_pipette.py:169-187"),
        Fact("PickingPipette.draw_time and expel_time write a time in ms to the draw-time and expel-time registers",
             source="upstream_code", ref="fish_sorter/hardware/picking_pipette.py:189-211"),
        Fact("PickingPipette._pipette_wait sleeps in steps of max(0.05, t/3) and leaves its loop early when "
             "vc.read_register(address_offset) == 0; it writes nothing", source="upstream_code",
             ref="fish_sorter/hardware/picking_pipette.py:213-229"),
        Fact("PickingPipette._valve_cmd writes the register and then calls _pipette_wait on the same offset",
             source="upstream_code", ref="fish_sorter/hardware/picking_pipette.py:231-243"),
        Fact("PickingPipette.disconnect moves the pipette and homes x and y, then writes idle_atm to the func_idle_type "
             "register and closes both connections; it writes nothing to the function register",
             source="upstream_code", ref="fish_sorter/hardware/picking_pipette.py:81-94"),
        Fact("pyproject.toml declares the licence 'BSD 3-Clause License, CERN Open Hardware Licence Version 2 - Weakly "
             "Reciprocal'", source="upstream_code", ref="pyproject.toml:12"),
    ]
    safe_state = ("idle code (func_idle, 128 in the shipped config) written and taken by the controller (function "
                  "register back at 0, echo register equal to the code); per the CoDeSys program text in the clone "
                  "that step sets its Press and Vacuum outputs off (Press OFF, Atmos ON); not a sensed valve "
                  "position, and the Zaber stage is not stopped (not covered)")

    # -- reads ------------------------------------------------------------------------------------------------
    @read("draw_time_ms", type="integer", unit="ms",
          description="Draw-time register of the pneumatic controller")
    def draw_time_ms(self):
        return self._read_value(self._register("draw_time_add_offset"))

    @read("expel_time_ms", type="integer", unit="ms",
          description="Expel-time register of the pneumatic controller")
    def expel_time_ms(self):
        return self._read_value(self._register("expel_time_add_offset"))

    @read("function_code", type="integer",
          description="Function register: a code not yet taken by the controller program, which writes 0 back "
                      "when it takes one; not a valve state")
    def function_code(self):
        return self._read_value(self._register("func_add_offset"))

    @read("function_echo", type="integer",
          description="Echo register: the last code the controller program took; nothing here clears it, so it "
                      "can be stale; not a valve state")
    def function_echo(self):
        return self._read_value(self._register("func_echo_add_offset"))

    # -- writes: the two timing registers ----------------------------------------------------------------------
    @write("draw_time_ms", type="integer", unit="ms",
           description="Time in milliseconds the controller holds the draw function",
           limit=Limit.operator_required(
               "no text file of the clone states a draw-time range: the time is a configurable register and the "
               "site supplies the envelope"))
    def set_draw_time_ms(self, value):
        value = int(value)
        self._write(self._register("draw_time_add_offset"), value)
        return value

    @write("expel_time_ms", type="integer", unit="ms",
           description="Time in milliseconds the controller holds the expel function",
           limit=Limit.operator_required(
               "no text file of the clone states an expel-time range: the time is a configurable register and the "
               "site supplies the envelope"))
    def set_expel_time_ms(self, value):
        value = int(value)
        self._write(self._register("expel_time_add_offset"), value)
        return value

    # -- pneumatic function actions ---------------------------------------------------------------------------
    @action(name="x-cap.czbiohub-sf.set_pressure.v1",
            description="Pressure on or off: writes the upstream press_on or press_off code and waits until the "
                        "controller has taken it",
            input={"state": Field("boolean", description="True writes press_on; false writes press_off")},
            output={"pressure": Field("boolean", description="The pressure state whose code the controller took"),
                    "function_code": Field("integer", description="Function code the controller took")})
    def set_pressure(self, state):
        code = self._command("press_on" if state else "press_off")
        return {"pressure": bool(state), "function_code": code}

    @action(name="x-cap.czbiohub-sf.set_vacuum.v1",
            description="Vacuum on or off: writes the upstream vac_on or vac_off code (the controller program sets or "
                        "clears its Vacuum output) and waits until the controller has taken it",
            input={"state": Field("boolean", description="True writes vac_on; false writes vac_off")},
            output={"vacuum": Field("boolean", description="The vacuum state whose code the controller took"),
                    "function_code": Field("integer", description="Function code the controller took")})
    def set_vacuum(self, state):
        code = self._command("vac_on" if state else "vac_off")
        return {"vacuum": bool(state), "function_code": code}

    @action(name="x-cap.czbiohub-sf.idle_atmospheric.v1",
            description="Atmospheric idle: writes the upstream func_idle code and waits until the controller has "
                        "taken it",
            output={"idle": Field("boolean", description="True once the controller took the idle code"),
                    "function_code": Field("integer", description="Function code the controller took")})
    def idle_atmospheric(self):
        return {"idle": True, "function_code": self._command("func_idle")}

    # -- safe state and e-stop --------------------------------------------------------------------------------
    @action(name="x-cap.czbiohub-sf.safe_pneumatics.v1", safe_state=True,
            description="Safe-state stop path: writes the func_idle code and waits until the controller has taken "
                        "it; takes no input",
            output={"idle": Field("boolean", description="True once the controller took the idle code"),
                    "function_code": Field("integer", description="Function code the controller took")})
    def safe_pneumatics(self):
        return {"idle": True, "function_code": self._command("func_idle", stop=True)}

    @estop
    def stop(self):
        """The native stop: one write of the idle code with its Modbus reply checked; no wait for the controller to
        take it (the safe-state action that the runtime runs next confirms that)."""
        self._write(self._register("func_add_offset"), self._function("func_idle"), stop=True)

    # -- lifecycle ---------------------------------------------------------------------------------------------
    def teardown(self):
        self.native.disconnect()

    # -- config, register and reply helpers --------------------------------------------------------------------
    def _register(self, key):
        return int(self.native.config["register"][key])

    def _function(self, key):
        return int(self.native.config["function_codes"][key])

    @staticmethod
    def _checked(reply, what):
        """A pymodbus reply: an exception reply is a message whose isError() is true, not a raised exception."""
        is_error = getattr(reply, "isError", None)
        if not callable(is_error):
            raise OutcomeUnknown(f"the valve controller gave no Modbus reply to the {what}")
        if is_error():
            native_code = getattr(reply, "exception_code", None)
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               f"the valve controller answered the {what} with a Modbus exception reply",
                               native_code=native_code if isinstance(native_code, int) else str(reply))
        return reply

    def _io(self):
        """One Modbus transaction at a time.  The runtime calls reads, the e-stop and the safe-state action outside the
        driver lock, and ValveController is not written for concurrent use: every call may close and replace its
        client (_check_connect and the write retry, valve_controller.py:53-59 and 110-114).  The lock is held for
        one read or write, never across a command's wait, so the e-stop waits at most for one transaction."""
        lock = getattr(self, "_modbus_lock", None)
        if lock is None:
            with _LOCK_GUARD:
                lock = getattr(self, "_modbus_lock", None)
                if lock is None:
                    lock = self._modbus_lock = threading.Lock()
        return lock

    def _read_value(self, offset):
        with self._io():
            reply = self.native.read_register(offset)
        reply = self._checked(reply, "register read")
        registers = getattr(reply, "registers", None)
        if not registers:
            raise DriverFailed("MHS.DEVICE.FAULTED", "the valve controller returned no holding register")
        return int(registers[0])

    def _write(self, offset, value, *, stop=False):
        with self._io():
            if not stop:
                # The runtime cancels a running command before its e-stop writes (SAFE-040 order), so under the
                # transaction lock a command's write is either sent before the stop's write or not sent at all.
                self.check_cancelled()
            try:
                reply = self.native.write_register(offset, value)
            except Exception as exc:                    # a lost reply: the controller may have received the write
                raise OutcomeUnknown(f"the register write raised {type(exc).__name__}; whether the valve controller "
                                     "received it is not known") from exc
        self._checked(reply, "register write")

    def _command(self, name, *, stop=False):
        """Write one function code, then wait until the controller program has taken it (``stop``: the safe-state
        path, which no cancellation refuses)."""
        code = self._function(name)
        function_register = self._register("func_add_offset")
        echo_register = self._register("func_echo_add_offset")
        self._write(function_register, code, stop=stop)  # an exception reply: failed; a raised write: unknown
        try:
            deadline = time.monotonic() + _TAKE_TIMEOUT_S
            pending = self._read_value(function_register)
            while pending != 0 and time.monotonic() < deadline:
                if not stop:
                    self.check_cancelled()              # an e-stop's idle code follows this one
                time.sleep(_POLL_S)
                pending = self._read_value(function_register)
            echo = self._read_value(echo_register) if pending == 0 else None
        except Cancelled:
            raise
        except Exception as exc:                        # the code was written: whether it was taken is not known
            raise OutcomeUnknown(f"function code {code} was written, but the controller's registers could not be "
                                 f"read back ({type(exc).__name__})") from exc
        if pending != 0:
            raise OutcomeUnknown(f"the valve controller has not taken function code {code}: the function register "
                                 f"still holds {pending} after {int(_TAKE_TIMEOUT_S * 1000)} ms", native_code=pending)
        if echo != code:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               f"the valve controller cleared the function register but echoes {echo}, not {code}: "
                               "it did not take the code", native_code=echo)
        return code
