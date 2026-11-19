r"""OpenMHS driver for gh.btownshend/pytecan: the Tecan EVO 100 Gemini pipe client.

A direct Driver over the card's entry class ``Gemini`` (Gemini/gemini.py:8).  The class is the host side of the
Gemini control software on a Tecan EVO 100: it writes one command to the Windows named pipe ``\\.\pipe\gemini``,
reads one reply, and parses the reply as semicolon-separated fields whose first field is an error code
(Gemini/gemini.py:21-43, 91-97).  The card names the python-object family; a direct Driver is used because the
action and the safety question are not a set of plain method bindings (DEVIATION FROM THE CARD).

Interface:

* reads: the status line (``getstatus``), the software version (``getversion``) and the value of the configured
  Gemini variable (``getvar``);
* write: the value of that configured variable (``setvar``); its range is operator-supplied because no text of the
  clone states a range for a Gemini variable;
* action: start the pipetting program Gemini has loaded (``start_pipetting``), an x-cap extension because no
  catalogue class carries the input-free start of an already loaded program.

BLOCKED on the stop path.  The class defines no stop, abort, cancel or halt method (Gemini/gemini.py:8-126) and
``close()`` is a pass (Gemini/gemini.py:88-89).  The only stop-like command strings in the Gemini files are BMX,
BMY and BMZ, which the log parser describes as the low-level LiHa commands Gemini sends to its subdevice
(parselog/parselog.py:74-76) and whose ``fwparse`` receives the subdevice command and reply
(parselog/parselog.py:235-259); they are not host-pipe commands.  An R2 liquid handler without a source-backed stop
cannot meet SAFE-045 without inventing a command, so the driver declares no ``@estop`` and no safe-state action and
RESULT.json records HELPER_MISSING.  No hardware was attached; the fake backend is the only one used.

Every Fact cites a line of the clone at the pinned commit b80ab8d5549856998269f4bd60edab75986a17d6.  The package is
model-authored and unreviewed; the hardware factory is a separate Python 3 port and was never imported or run.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, read, write


class TecanGemini(Driver):
    device_id = "tecan-gemini"
    device_kind = "lab.liquid_handler"
    mode = "hardware"
    #: A liquid handler that starts pipetting programs is R2 even though the card's risk_floor is R1
    #: (MHS/spec/04-safety.md, section 2.1: pipetting into a plate).
    risk = "R2"
    native = "gemini:Gemini"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeGemini"}
    vendor, model = "Tecan", "EVO 100 with Gemini"
    display_name = "Tecan EVO 100 liquid handler (Gemini pipe client)"
    tags = ["tecan", "evo 100", "gemini", "liquid handler", "pipetting", "named pipe", "windows"]
    facts = [
        Fact("The README describes the repository as a Python interface to the Tecan EVO 100",
             source="vendor_doc", ref="README.md:4"),
        Fact("The README says the modules generate .gem programs that are loaded into Gemini on a Tecan EVO and run",
             source="vendor_doc", ref="README.md:6"),
        Fact("Gemini is the class of the Gemini interface module", source="upstream_code",
             ref="Gemini/gemini.py:8"),
        Fact("execute writes one command to the Gemini pipe with WriteFile, reads one reply with ReadFile, and parses "
             "the reply as semicolon-separated fields whose first field is the error code; a nonzero code raises "
             "CmdError", source="upstream_code", ref="Gemini/gemini.py:21-43"),
        Fact("open connects to the named pipe \\\\.\\pipe\\gemini with CreateFile", source="upstream_code",
             ref="Gemini/gemini.py:91-97"),
        Fact("getstatus, getversion, getvar, setvar and start_pipetting send GET_STATUS, GET_VERSION, GET_VARIABLE, "
             "SET_VARIABLE and START_PIPETTING through execute", source="upstream_code",
             ref="Gemini/gemini.py:55-86"),
        Fact("setvar formats the value with two decimals ('%.2f')", source="upstream_code",
             ref="Gemini/gemini.py:76-82"),
        Fact("The example client sets the variable testvar and then reads GET_MAX_VARIABLES and GET_VARIABLE_NAME",
             source="upstream_code", ref="Gemini/gemtest.py:8-20"),
        Fact("close() is a pass and the class's methods are exactly execute, setdebug, flush, getvar, getstatus, "
             "getversion, setvar, start_pipetting, close and open: it has no stop, abort, cancel or halt method",
             source="upstream_code", ref="Gemini/gemini.py:8-126"),
        Fact("The error table lists 'Cancel was pressed' as error code 12, a reported condition, not a command",
             source="upstream_code", ref="Gemini/gemini.py:19"),
        Fact("The log parser maps the LiHa commands BMX, BMY and BMZ to 'Stop X/Y/Z drive movement immediately'",
             source="upstream_code", ref="parselog/parselog.py:74-76"),
        Fact("fwparse takes dev, send and reply, uses send[0] as the command and looks it up in devnames[dev][1]",
             source="upstream_code", ref="parselog/parselog.py:235-259"),
        Fact("The device map assigns the LiHa command table to the C5 and C6 subdevices",
             source="upstream_code", ref="parselog/parselog.py:136"),
        Fact("IOException and CmdError inherit BaseException", source="upstream_code", ref="Gemini/gemini.py:12-17"),
    ]
    #: The clone has no stop; this sentence says so rather than claiming a state the client cannot reach.
    safe_state = ("unreachable through this client: Gemini defines no stop, abort or cancel method and close() is a "
                  "pass, so a latched stop cannot stop a START_PIPETTING program or its plunger")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        #: The Gemini variable this device exposes.  The name is a deployment choice, not a device fact; the clone's
        #: example uses testvar (Gemini/gemtest.py:8).
        self._variable_name = str(self.options.get("variable_name", "testvar"))

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("status", type="string", description="Status line returned by Gemini's GET_STATUS command")
    def status(self):
        return self.native.getstatus()

    @read("version", type="string", description="Software version returned by Gemini's GET_VERSION command")
    def version(self):
        return self.native.getversion()

    @read("variable", description="Value of the configured Gemini variable (GET_VARIABLE); its unit is deployment-specific")
    def variable(self):
        return self.native.getvar(self._variable_name)

    # -- write ----------------------------------------------------------------------------------------------------
    @write("variable",
           description="Value of the configured Gemini variable, sent with SET_VARIABLE and two decimals",
           limit=Limit.operator_required(
               "no text file of the clone states a range for a Gemini variable; the loaded .gem program and the "
               "site define it, so the site supplies the accepted range in the operator overlay"))
    def set_variable(self, value):
        self.native.setvar(self._variable_name, value)
        return float(self.native.getvar(self._variable_name))

    # -- action ---------------------------------------------------------------------------------------------------
    @action(name="x-cap.btownshend.start_pipetting.v1", risk="R2",
            description="Start the pipetting program that Gemini has loaded (START_PIPETTING)",
            output={"started": Field("boolean", description="True once Gemini accepted START_PIPETTING"),
                    "status": Field("string", description="Status line Gemini returned after the start")})
    def start_pipetting(self):
        self.native.start_pipetting()
        return {"started": True, "status": self.native.getstatus()}

    # -- lifecycle -------------------------------------------------------------------------------------------------
    def teardown(self):
        self.native.close()
