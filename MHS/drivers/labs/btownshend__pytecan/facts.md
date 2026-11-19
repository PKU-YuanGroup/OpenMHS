# Facts and tags for gh.btownshend/pytecan

Every fact cites its source at commit `b80ab8d5549856998269f4bd60edab75986a17d6`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone:LINE`). The same facts are in `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The README describes the repository as a Python interface to the Tecan EVO 100 | vendor_doc | README.md:4 |
| The README says the modules generate .gem programs that are loaded into Gemini on a Tecan EVO and run | vendor_doc | README.md:6 |
| Gemini is the class of the Gemini interface module | upstream_code | Gemini/gemini.py:8 |
| execute writes one command to the Gemini pipe with WriteFile, reads one reply with ReadFile, and parses the reply as semicolon-separated fields whose first field is the error code; a nonzero code raises CmdError | upstream_code | Gemini/gemini.py:21-43 |
| open connects to the named pipe \\.\pipe\gemini with CreateFile | upstream_code | Gemini/gemini.py:91-97 |
| getstatus, getversion, getvar, setvar and start_pipetting send GET_STATUS, GET_VERSION, GET_VARIABLE, SET_VARIABLE and START_PIPETTING through execute | upstream_code | Gemini/gemini.py:55-86 |
| setvar formats the value with two decimals ('%.2f') | upstream_code | Gemini/gemini.py:76-82 |
| The example client sets the variable testvar and then reads GET_MAX_VARIABLES and GET_VARIABLE_NAME | upstream_code | Gemini/gemtest.py:8-20 |
| close() is a pass and the class's methods are exactly execute, setdebug, flush, getvar, getstatus, getversion, setvar, start_pipetting, close and open: it has no stop, abort, cancel or halt method | upstream_code | Gemini/gemini.py:8-126 |
| The error table lists 'Cancel was pressed' as error code 12, a reported condition, not a command | upstream_code | Gemini/gemini.py:19 |
| The log parser maps the LiHa commands BMX, BMY and BMZ to 'Stop X/Y/Z drive movement immediately' | upstream_code | parselog/parselog.py:74-76 |
| fwparse takes dev, send and reply, uses send[0] as the command and looks it up in devnames[dev][1] | upstream_code | parselog/parselog.py:235-259 |
| The device map assigns the LiHa command table to the C5 and C6 subdevices | upstream_code | parselog/parselog.py:136 |
| IOException and CmdError inherit BaseException | upstream_code | Gemini/gemini.py:12-17 |

Limits: the value of the configured Gemini variable is `Limit.operator_required`. No text file of the clone states a
range or physical unit for a Gemini variable; the loaded .gem program and the site define them. No dimensionless
unit is asserted. `site-limits.example.json` shows an
example overlay only, not a device bound.

Safety and blocked state: `Gemini` has no stop, abort, cancel or halt method, and `close()` is a pass. The only
stop-like strings in the Gemini files are BMX/BMY/BMZ in the log parser, which are the low-level LiHa commands
Gemini sends to its subdevice, not host-pipe commands. An R2 liquid handler cannot meet SAFE-045 without inventing
one, so the driver has no `@estop` and no safe-state action and `RESULT.json` records `HELPER_MISSING`. The fake is
an in-memory stand-in, not a recording, and no hardware was attached.

Tags: tecan, evo 100, gemini, liquid handler, pipetting, named pipe, windows

Scope: only the Gemini pipe client is served. The README also names thermocycler and incubator interfaces
(`README.md:8-9`); the repository's TRobot, PTC, RIC, BioShake and Scale drivers are outside this package.

Model-review limitations for unblocking: the Python 3 native port was read but not imported or run. It retains
BaseException-derived native errors, which need explicit receipt/error translation; its blocking ReadFile has no
timeout. Its getvar error-14 handling also differs from the pinned Python 2 code, whose exception instance is
compared directly to 14. These port details need validation together with a real stop path. The fake close is a no-op,
matching `Gemini.close()`, and does not disconnect the pipe or stop a running pipetting program. The stock gate test
keeps asserting no failed gates and therefore remains failing while the package is blocked. The card's required
publication/licence decision is unresolved; its lock remains NOASSERTION/unknown.
