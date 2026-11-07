# Isolated simulator host (`isolated_process_v1`)

Some simulator environments cannot share the endpoint's process. Their constructor launches ROS and a simulator,
their `close()` signals a global `rospy` shutdown and calls `sys.exit`, a failed service call can end in
`sys.exit` too, and ROS 1 must initialise its node on a main thread. A `GymnasiumDriver` backend can declare that its
environment is built and driven in a child process that the endpoint starts and owns, and how that environment's
simulator is stopped and how the stop is read back (`mhs.bridge.sim_host`; the child is
`mhs.bridge.sim_host_child`):

```python
class PandaReach(GymnasiumDriver):
    backends = {"fake": ".fake:FakePandaReachEnv", "sim": ".host:make_env"}
    process_by_backend = {"sim": {
        "mode": "isolated_process_v1",
        "reset_kwargs": ["seed", "options"],          # the exact keywords the native reset accepts
        "start_timeout_s": 900.0,                      # child start, construction and the space description
        "step_timeout_s": 60.0, "reset_timeout_s": 300.0, "close_timeout_s": 60.0,
        "stop": "gazebo.pause_proxy",                  # a public attribute path, called with no argument
        "readback": {"path": "gazebo.get_physics_properties", "field": "pause", "equals": True},
        "stop_timeout_s": 5.0,                         # each stop, read-back and unfence round trip
        "settle_timeout_s": 60.0,                      # a world call in flight at the stop must end within this
        "source_refs": ["src/ros_gazebo_gym/core/gazebo_connection.py:136-148"],
    }, "fake": {...}}
```

The declaration is a contract about a source-reviewed backend: the paths, bounds and citation strings configure the
SDK; they prove nothing about the simulator. The bounds are package choices and must be labelled as such.
The host is POSIX only (descriptor passing, process sessions and process-group signals).

## What the backend entry is

The backend's `backends` entry must be a package-relative `.module:attribute`. The endpoint never imports it: the host
process loads the driver directory as a private package, imports the module and calls the attribute on its main thread
with the driver's options (JSON values), and the result is the environment. The host describes its action and
observation spaces (`Box`, `Discrete`, `MultiDiscrete`, `MultiBinary`, `Dict`, `Tuple`) to the endpoint, which builds
the contract from them as for any Gymnasium environment; an integer `Box` publishes integer items. Actions go to the
host as JSON and are converted to the real space's arrays there; observations come back as JSON values. An `info`
value that is not JSON is sent as a type label, never failing the call; an observation that is not JSON makes the
call's outcome unknown (it ran). The stop and read-back paths are resolved on `env.unwrapped` when the environment has
one (a Gymnasium wrapper chain), else on the environment.

The child's standard input, output and error are `/dev/null`: nothing the environment prints reaches the endpoint's
streams (a stdio MCP server stays intact) or the protocol, which uses two private pipes. The child imports nothing of
the SDK and is Python 3.8 syntax, so it can run under the simulator's own interpreter: `MHS_SIM_HOST_PYTHON` (an
absolute path) selects it; the default is the endpoint's interpreter.

## Guarantees

- Containment. A `SystemExit`, `KeyboardInterrupt` or global ROS shutdown inside the environment ends that call in
  the host, never the endpoint; after one, the host accepts only `close`. `os._exit` or a crash ends the host, which
  the endpoint sees as a dead host.
- Bounded calls. Every request waits at most its declared bound. A world call (`step`, `reset`) that outlives its bound
  is never cancelled: its outcome is `unknown` (`may_have_effect`), it stays owned (new world calls are refused
  `MHS.DEVICE.BUSY` with nothing sent, the safety status is unachieved, safety reset is refused), its late answer is
  recorded and never applied, and steps need an explicit world reset afterwards. A host that dies during a call makes
  that call's outcome unknown too.
- The e-stop. The endpoint latches first (and cancels running operations); the bridge then fences the host before it
  writes the stop request, so no world call is sent after it, and the host itself refuses a world call it receives
  after the stop. The stop runs in the host; when a world call was in flight, the bridge waits for it (at most
  `settle_timeout_s`) and sends the stop again, because the call may have undone the first one; then the read-back
  must return exactly `equals` (`True` is not `1`). Only then is the e-stop confirmed. A dead, broken or unresponsive
  host, a stop or read-back that raises or does not answer within `stop_timeout_s`, or any other value is an
  unreached safe state: `MHS.SAFETY.SAFE_STATE_UNREACHED`, the latch stays, the endpoint retries in the background
  (each retry stops afresh), and safety reset is refused until a stop is confirmed. A world call in flight that ends
  after the e-stop budget is confirmed by a later retry. The safety reset lifts the fence in the host; it changes
  nothing in the simulator.
- Close sends the stop and the read-back once more, waits for a world call in flight, calls `env.close()` in the host
  (an exit it raises is the environment's own close), closes the request pipe and waits for the host to exit, each
  bounded. A host that does not exit gets SIGTERM, which ends it with an ordinary interpreter exit, so `atexit`
  cleanup the environment registered still runs, and then SIGKILL of its process group. The outcome is `settled` only
  when the stop was confirmed, the close returned and the host exited by itself; otherwise `unsettled: ...` says
  what happened. Processes the environment launched outside the host's process group (ROS nodes start their own
  sessions) can survive a killed host. A host whose endpoint vanished without closing it (its request pipe closed)
  runs the stop, waits for a call in flight and closes the environment, each at most 10 s, then exits.

`readback` must name a state the simulator's stepping depends on: a read-back path equal to the stop, or a final
name that acknowledges a request (`success`, `status`, `status_message`, `ok`, `result` ...) is refused at
definition. The profile does not combine with physics timing, JSON checkpoints, the asynchronous profile or the dm_env
profile on one backend, and a manifest built on one backend is never projected onto another whose profile differs.

## The gate

The acceptance gate runs the package's fake in a real host process, so every G6 and G8 check goes through the host:
the e-stop must reach the declared stop (the gate records the host's calls), latched commands are refused with zero
native calls, and an injected native failure gives a failed receipt. G6 `HOST_FAIL_OPEN` then puts a filter on the
host that makes the read-back answer another value, makes the stop fail, or kills the host before the stop: each
e-stop must end `failed` `MHS.SAFETY.SAFE_STATE_UNREACHED` with the latch held. G7 `HOST_PATH` checks every declared
path of every backend against the clone at the pin: the first name must be an attribute of the native class (read as
for the fake's members), and every further name and every name of the read-back field must occur in the clone. That
shows that the names exist upstream, not what they do: the reviewer traces the stop and the read-back to the state the
simulator's step loop reads (REVIEW.md item 5). The host's own members (`stop`, `readback` and the like) are not
looked up upstream. The gate's network and device guard reaches the host: under the gate it applies the same guard
before it imports package code, or refuses to start.

## Not proven

That the declared stop stops the simulator, that the read-back reads its state, that another client or a GUI does not
resume it, that the bounds suit the deployment, and anything about the processes the environment launches. A
`GymnasiumDriver` whose `native` is a factory (`native_factory`) is not supported with a hosted backend: G7 does not
resolve its paths and reports the host's members. Evidence on a fake stays `contract_checked`.
