# Facts and tags for gh.ad-sdl/ot2_module

Every fact cites the pinned clone at commit `39ffdfdb73c3bc08bb988c5140cfc1af3cecbd0c`.  The same facts are in
`driver.py`; the reference file is generated from the driver, and the table below from the reference file.

| fact | source | ref |
|---|---|---|
| The module is a MADSci node for Opentrons liquid handlers, the OT-2 and the Flex | vendor_doc | README.md:3 |
| OT2_Driver builds the robot base URL from config.ip and config.port and sets the Opentrons-Version: 2 request header | upstream_code | src/ot2_interface/ot2_driver_http.py:71-72 |
| The constructor probes /robot/lights and raises RuntimeError when the probe does not return HTTP 200 | upstream_code | src/ot2_interface/ot2_driver_http.py:70-77 |
| After the probe the constructor switches the robot lights on; when the probe does not report them off it first switches them off and sleeps one second | upstream_code | src/ot2_interface/ot2_driver_http.py:79-84 |
| change_lights_status posts {'on': status} to /robot/lights | upstream_code | src/ot2_interface/ot2_driver_http.py:419-424 |
| transfer opens the local protocol file, posts it to /protocols with timeout=600, prints the answer's status code, text and reason, creates a run at /runs with timeout=60 and returns the protocol id and run id | upstream_code | src/ot2_interface/ot2_driver_http.py:146-169 |
| resume posts actionType 'play' to /runs/{run_id}/actions without a timeout and returns the response without checking its status code | upstream_code | src/ot2_interface/ot2_driver_http.py:249-256 |
| cancel posts actionType 'stop' to /runs/{run_id}/actions without a timeout and returns the response without checking its status code | upstream_code | src/ot2_interface/ot2_driver_http.py:271-278 |
| execute compares the answer of the play action with 201, which it calls the good response code for this endpoint, and only prints when it differs | upstream_code | src/ot2_interface/ot2_driver_http.py:188-195 |
| execute posts play and polls check_run_status every second, catching and printing every exception, until the run is failed, succeeded or stopped | upstream_code | src/ot2_interface/ot2_driver_http.py:184-210 |
| RunStatus names idle, running, finishing, succeeded, failed, paused, stop-requested and stopped | upstream_code | src/ot2_interface/ot2_driver_http.py:29-39 |
| check_run_status reads /runs/{run_id}, prints when the answer is not HTTP 200 and constructs RunStatus from the response data.status | upstream_code | src/ot2_interface/ot2_driver_http.py:294-300 |
| get_run returns the JSON of GET /runs/{run_id} and only prints when the answer is not HTTP 200 | upstream_code | src/ot2_interface/ot2_driver_http.py:317-323 |
| get_runs sends GET /runs without a timeout, maps the id, protocolId, status and current of each run in its data list to runID, protocolID, status and current, and returns None when /runs does not answer HTTP 200 | upstream_code | src/ot2_interface/ot2_driver_http.py:369-386 |
| get_robot_status returns 'offline' when get_runs returns None, skips succeeded and stop-requested runs, returns the status of the first other run whose status RunStatus names, and returns 'idle' when none does | upstream_code | src/ot2_interface/ot2_driver_http.py:396-409 |
| reset_robot_data sends DELETE /runs/{runID} for every run whose status is failed | upstream_code | src/ot2_interface/ot2_driver_http.py:411-417 |
| send_request joins base_url and the request extension, sets the Opentrons-Version: 2 header when no headers are given, requires a method keyword and passes the keyword arguments to requests.request | upstream_code | src/ot2_interface/ot2_driver_http.py:444-461 |
| The protocol generator's Temperature_Set command sets a temperature module to an integer change_temp | upstream_code | src/ot2_interface/protopiler/config.py:262-268 |
| The protocol generator's Move_Labware command moves labware inside the Flex with the gripper | upstream_code | src/ot2_interface/protopiler/config.py:271-272 |
| OT2Node.execute sets self.run_id to the run id before OT2_Driver.execute and back to None after it returns | upstream_code | src/ot2_rest_node.py:436-438 |
| OT2Node.execute answers a run whose status is stopped with the message that the OT2 is successfully IDLE after stopping a protocol | upstream_code | src/ot2_rest_node.py:454-465 |
| OT2Node.safety_stop logs and sets node_status.stopped; it sends no stop to the robot | upstream_code | src/ot2_rest_node.py:522-527 |
| OT2Node.cancel logs and calls self.ot2_interface.cancel(self.run_id) | upstream_code | src/ot2_rest_node.py:529-534 |

## Limits

The one action input is `protocol_path`, a string.  A protocol decides the volumes, labware, modules and motion of
its run; the clone uploads the file as it is (src/ot2_interface/ot2_driver_http.py:146-158) and names no protocol
or directory a deployment may run.  `protocol_path` is therefore `Limit.operator_required`: every start is refused
`MHS.SAFETY.LIMITS_UNSET` until the operator overlay lists the approved protocol paths as an `allowed` set, and a
path outside that set is refused `MHS.SAFETY.ENVELOPE_VIOLATION` before any request.  The match is exact on the
string; what a listed file contains when it is uploaded is the operator's responsibility.
`site-limits.example.json` allows one placeholder path; it is an example, not a statement about any protocol.  The
envelope cannot bound what an allowed protocol does: volumes, temperatures (the clone's own protocol generator sets temperature modules,
src/ot2_interface/protopiler/config.py:262-268) and speeds stay the protocol's.  The catalogue classes
`cap.fluid.aspirate.v1` and `cap.fluid.dispense.v1` were not bound: they address a declared labware well, while
the upstream run interface accepts a whole protocol file and the streaming example never aspirates or dispenses
(tests/test_ot2_streaming.py:12-65).

## Safety

- The e-stop (`@estop`, native `send_request`) and the safe-state action `x-cap.ad-sdl.stop_active_run.v1` both
  read GET /runs and send the run stop action, the request `OT2_Driver.cancel` builds
  (src/ot2_interface/ot2_driver_http.py:271-277), to every run listed as running, paused, finishing or in a status
  the clone's RunStatus does not name, and to a run of this driver whose play request may still be in flight
  (created, still idle).  Idle, succeeded, failed, stop-requested and stopped runs are left alone.
- Each stop is confirmed by a fresh GET /runs/{id}: the run must read stop-requested, stopped, succeeded or failed.
  Otherwise, or when GET /runs does not answer HTTP 200 with a run list, the stop raises
  `MHS.SAFETY.SAFE_STATE_UNREACHED`; the runtime keeps the latch and retries the stop path in the background.  The
  answer code of the stop action is reported but not relied on: the clone calls 201 the good answer of this
  endpoint (src/ot2_interface/ot2_driver_http.py:188-195), and the run's state decides.
- The stop path sends its requests through the upstream `send_request` (src/ot2_interface/ot2_driver_http.py:444-461)
  with a 5 s timeout per request, the package's choice: `cancel`, `get_runs` and the run reads pass none
  (:275-277, :370, :295, :318), and a silent robot must not hold the e-stop forever.  A slow robot can therefore
  give a failed e-stop receipt that the background retry confirms later.
- stop-requested means the robot accepted the stop; the clone does not say when motion ends.  It is a run stop over
  the HTTP API, not a hardware stop; requests outside a run are not stopped (this driver sends none), and module
  set points a protocol made (a temperature module, protopiler/config.py:262-268) are not reset by this driver;
  whether the robot resets them when a run stops is not stated in the clone.  The clone documents no independent
  hardware e-stop, so `estop_physical_ref` is not set; the input-free safe-state action meets SAFE-045.
- No reset hook and no re-enable: a stopped run stays stopped, and only a new `x-cap.ad-sdl.start_protocol.v1` (a new
  upload and run) starts the robot again, refused while latched.
- The node's `safety_stop` is not a stop path: it only sets a flag and logs (src/ot2_rest_node.py:522-527).  The
  node's `cancel` reaches the native `cancel` with the run id it keeps only while `execute` runs
  (src/ot2_rest_node.py:436-438, :529-534).
- `start_protocol` returns once the robot accepted the play action (HTTP 201, else `MHS.DEVICE.FAULTED` with the
  code); the run continues on the robot after it returns, also after the session ends, until it ends or is
  stopped.  When the play request raises, or the play was accepted but the run cannot be read, the outcome is
  `unknown`.  A cancellation before the play stops the new idle run; one after it sends the stop to the run.
- The stop path reads only the id and status of each run of GET /runs, as `get_runs` reads them
  (src/ot2_interface/ot2_driver_http.py:377-379); the `runs` read uses `get_runs` itself, which indexes each run's
  `protocolId` (:378), so a run without one makes that read fail but not the stop.
- `execute` swallows every exception in its polling loop and has no timeout
  (src/ot2_interface/ot2_driver_http.py:197-210); this driver does not call it.
- Opening the hardware backend runs the upstream constructor, which switches the robot lights
  (src/ot2_interface/ot2_driver_http.py:79-84).  `transfer` prints the upload's status code, text and reason to
  standard output (:155-157), and `check_run_status` and `get_run` print on a non-200 answer (:297-298, :320-321):
  an endpoint that talks over stdio would receive those lines in its protocol stream.

## Fake

The fake is an analytic in-memory stand-in for the HTTP client, not a recording and not the Opentrons simulator: no
HTTP traffic and no timing model.  It keeps the upstream method names and return shapes, the RunStatus values, 201
for an accepted run action and 200 for a read, KeyError from `check_run_status` for an answer without data, and the
`send_request` routes the stop path uses.  It decides what the clone does not state, each marked `# placeholder`:
which run transitions are refused (409), the codes of an unknown run or path (404) and of an unanswered run list
(503), the error bodies, and the timing (a stopped run reads stop-requested once, then stopped; a started run stays
running until a test changes it).  It does not open the protocol path, it accepts a new run while another is
active, and its ids and starting state are test data.  It cannot show that a real protocol moves liquid.

Tags: liquid-handler, pipette, protocol-runner, http
