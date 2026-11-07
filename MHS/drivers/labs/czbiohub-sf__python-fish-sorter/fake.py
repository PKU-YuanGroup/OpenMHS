"""Fake backend of the Fish Sorter pneumatics driver: an in-memory stand-in for ValveController.

Gate G7: the public methods defined here are exactly the public methods of
``fish_sorter.hardware.valve_controller:ValveController`` at the pinned commit -- ``read_register``
(lines 68-88), ``write_register`` (lines 90-114) and ``disconnect`` (lines 61-66).  The fake keeps
the same register map shape (``config["register"]`` and ``config["function_codes"]``) and returns
pymodbus-shaped replies: a read reply with ``.registers`` and ``isError()``, a write reply with
``isError()`` and, when a test asks for one, a Modbus exception reply whose ``isError()`` is true
(pymodbus returns such a reply as a message, not as a Python exception: valve_test.py:88-96).
It opens no socket and talks to no device.

Behind the registers the fake stands in for the controller program of the CoDeSys project in the
clone (``hardware/valve_control/FishSorterValveControl.pro``, a binary file the gate cannot read;
its text is visible with ``strings``).  In its Init step the program takes a valid code from the
function register (%MW4), copies it to the echo register (%MW6) and runs that code's step, which
sets its Press and Vacuum outputs and writes 0 back to the function register.  An invalid code
stays in the function register and is not echoed.  The fake takes a code as soon as it is written
(the program takes it on its next scan); the timed draw (2) and expel (4) sequences are not
timed here, and a code written while one runs is modelled only by the test hook
``_end_sequence_on_next_code`` (the sequence's end clears the function register, so the code is
lost and the echo keeps the sequence's code).

The register addresses, function codes and initial register values below are test data for the
fake, not facts about the instrument: every number is marked ``# placeholder``.  A deployment
passes its own ``config`` mapping to the driver; the driver reads the map from the native object.
"""

#: The steps of the controller program's sequencer, as its text reads: code -> (Press, Vacuum) after the step;
#: None leaves that output as it was.
_PROGRAM_STEPS = {
    2: (False, False),      # placeholder: DRAW_FUNC; the draw sequence ends with Vacuum := 0, Press := 0
    4: (False, False),      # placeholder: EXPEL_FUNC; the expel sequence ends with Vacuum := 0, Press := 0
    8: (False, None),       # placeholder: PRESS0_FUNC, Press := 0
    9: (True, None),        # placeholder: PRESS1_FUNC, Press := 1
    16: (None, True),       # placeholder: ATMOS0_FUNC, Vacuum := 1 (the upstream's vac_on)
    17: (None, False),      # placeholder: ATMOS1_FUNC, Vacuum := 0 (the upstream's vac_off)
    128: (False, False),    # placeholder: IDLE_FUNC, Vacuum := 0, Press := 0
}


class _HoldingRegisters:
    """The part of a pymodbus read reply the driver uses (``valve_test.py:82`` reads ``registers``)."""

    def __init__(self, registers):
        self.registers = list(registers)

    def isError(self):
        return False


class _WriteResult:
    """The part of a pymodbus write reply the driver checks."""

    def isError(self):
        return False


class _ExceptionReply:
    """A Modbus exception reply as pymodbus returns it: a message whose ``isError()`` is true."""

    def __init__(self, function_code, exception_code):
        self.function_code = function_code | 0x80
        self.exception_code = exception_code
        self.registers = []

    def isError(self):
        return True


class FakeValveController:
    """In-memory Wago valve controller: holding registers, the two configured maps and the program's outputs."""

    def __init__(self, config=None, env="prod", **_options):
        self.config = config if isinstance(config, dict) else {
            "connect": {
                "host": "192.0.2.10",            # placeholder (a documentation address)
                "port": 502,                     # placeholder
            },
            "register": {
                "start_address": 12288,          # placeholder
                "draw_time_add_offset": 0,       # placeholder
                "expel_time_add_offset": 2,      # placeholder
                "func_add_offset": 4,            # placeholder
                "func_echo_add_offset": 6,       # placeholder
                "func_idle_type": 14,            # placeholder
            },
            "function_codes": {
                "idle_atm": 0,                   # placeholder
                "draw": 2,                       # placeholder
                "expel": 4,                      # placeholder
                "press_off": 8,                  # placeholder
                "press_on": 9,                   # placeholder
                "vac_on": 16,                    # placeholder
                "vac_off": 17,                   # placeholder
                "func_idle": 128,                # placeholder
            },
        }
        self.env = env
        self._connected = True
        register = self.config["register"]
        self._start = int(register["start_address"])
        self._func = self._start + int(register["func_add_offset"])
        self._echo = self._start + int(register["func_echo_add_offset"])
        self._registers = {
            self._start + int(register["draw_time_add_offset"]): 50,    # placeholder
            self._start + int(register["expel_time_add_offset"]): 150,  # placeholder
            self._func: 0,                                              # placeholder
            self._echo: 0,                                              # placeholder
            self._start + int(register["func_idle_type"]): 0,           # placeholder
        }
        self._press = False             # the program's Press output
        self._vacuum = False            # the program's Vacuum output
        self._error_replies = 0         # test hook: answer the next requests with a Modbus exception reply
        self._error_writes_only = False  # test hook: only writes get the exception replies
        self._stalled = False           # test hook: the program takes no code (it is not scanning)
        self._sequence_ends = None      # test hook: a running draw or expel sequence ends after the next code

    # -- the upstream surface ---------------------------------------------------------------------------------
    def _connect(self):
        self._connected = True

    def _check_connect(self):
        if not self._connected:
            self._connect()

    def disconnect(self):
        self._connected = False

    def read_register(self, add_offset, count=1):
        self._check_connect()
        if self._error_replies and not self._error_writes_only:
            self._error_replies -= 1
            return _ExceptionReply(0x03, 0x04)                          # placeholder: read, device failure
        address = self._start + int(add_offset)
        return _HoldingRegisters(self._registers.get(address + index, 0)   # placeholder
                                 for index in range(count))

    def write_register(self, add_offset, value):
        self._check_connect()
        if self._error_replies:
            self._error_replies -= 1
            return _ExceptionReply(0x06, 0x04)                          # placeholder: write, device failure
        address = self._start + int(add_offset)
        self._registers[address] = int(value)
        if address == self._func:
            self._scan()
        return _WriteResult()

    # -- the controller program -------------------------------------------------------------------------------
    def _scan(self):
        if self._sequence_ends is not None:
            # The end step of a running draw or expel sequence: both outputs 0 and the function register cleared, so
            # the code just written is lost; the echo keeps the sequence's code.
            self._press = self._vacuum = False
            self._registers[self._func] = 0
            self._registers[self._echo] = self._sequence_ends
            self._sequence_ends = None
            return
        if self._stalled:
            return
        code = self._registers[self._func]
        step = _PROGRAM_STEPS.get(code)
        if step is None:
            return
        self._registers[self._echo] = code
        press, vacuum = step
        if press is not None:
            self._press = press
        if vacuum is not None:
            self._vacuum = vacuum
        self._registers[self._func] = 0

    # -- test hooks (not upstream) ----------------------------------------------------------------------------
    def _reply_with_errors(self, count=1, writes_only=False):
        self._error_replies = int(count)
        self._error_writes_only = bool(writes_only)

    def _stall(self, stalled=True):
        self._stalled = bool(stalled)

    def _end_sequence_on_next_code(self, code=2):                       # placeholder: DRAW_FUNC
        self._registers[self._echo] = int(code)
        self._sequence_ends = int(code)

    def _outputs(self):
        return {"press": self._press, "vacuum": self._vacuum}
