# Gymnasium live routes: asynchronous environments and dm_env

Two optional, per-backend declarations let `GymnasiumDriver` serve environments whose calling convention is not the
synchronous Gymnasium tuple API. Both are contracts about a source-reviewed backend: the flags, bounds and citation
strings configure the SDK; they do not prove native behavior. Undeclared backends keep their existing behavior. A
third extension, resets that integrate physics, is part of the physics timing profile
([simulation-timing.md](simulation-timing.md)), and the explicit checkpoint opt-out is in
[gym-checkpoints.md](gym-checkpoints.md).
An environment that must live in its own process (a constructor that launches ROS, a close that exits the
interpreter) is served by the isolated simulator host ([sim-host.md](sim-host.md)).

## Asynchronous environments (`asyncio_owned_loop_v1`)

```python
async_by_backend = {
    "sim": {
        "mode": "asyncio_owned_loop_v1",
        "step": "coroutine",              # env.step(action) returns an awaitable
        "reset": "sync",                  # env.reset(...) returns its result directly
        "reset_kwargs": [],               # the exact keywords the native reset accepts: [], ["seed"], ["seed", "options"]
        "step_timeout_s": 30.0,           # local bounds, 0.001..600 s
        "reset_timeout_s": 120.0,
        "close_timeout_s": 15.0,
        "remote_stop": "world.pause",     # optional: a public attribute path on the environment
        "stop_probe": "world.is_paused",  # optional: must return exactly True to confirm the stop
        "stop_timeout_s": 5.0,            # required with remote_stop, 0.001..60 s
        "settle_timeout_s": 10.0,         # required with remote_stop, 0..60 s
        "source_refs": ["path/in/clone.py:63-88"],
    }
}
```

One daemon thread runs one asyncio event loop and is the only thread that calls the environment's `step`, `reset`,
`close`, remote stop and stop probe. A client library bound to that loop, or one that is not thread-safe, is never
entered from two threads by those calls. The environment itself is constructed outside the loop, by the backend
factory on the caller's thread (a client that connects in its constructor does so there), and the bridge reads plain
attributes such as the spaces from the caller's thread. A declared coroutine that returns a non-awaitable, or a declared synchronous call that
returns an awaitable (closed, never awaited), is a profile violation: the call fails and further steps need an
explicit reset.

Ownership after a local timeout. A caller waits at most the declared bound. A native call that has not settled by
then is not cancelled: cancelling the local coroutine would not end the remote operation it started. The command's
outcome is `unknown` (`may_have_effect`), and the call stays owned: new native work is refused with `MHS.DEVICE.BUSY`
(nothing dispatched), the safety status reports the safe state unachieved, safety reset is refused, and native
cleanup is deferred. When it settles, its outcome is recorded (`async_status()["late"]` on the bridge) and never
applied to the world state; steps are refused until an explicit world reset succeeds. Operation cancellation is
observed between native calls, never inside one. The dispatch guard runs atomically with submission to the loop. It
refuses when the operation's cancel event is set, or when the e-stop epoch has advanced since the call was admitted.
Engaging the e-stop also latches the bridge. A later effectful call (`cap.world.step.v1`, `cap.world.reset.v1`,
`cap.world.seed.v1`, `cap.world.restore.v1`, and `restore`) is refused with `MHS.SAFETY.ESTOP_ENGAGED` until `reset`
(the safety reset) clears that latch. The latch does not depend on the endpoint's cancel event. Reads (`read`,
`world_state`, `cap.world.state.v1`) stay available. `safety_status` does not report the latch: a confirmed stop still
has an empty safety status, and an unconfirmed stop still reports the safe state unachieved. A call that was already
admitted when the e-stop engaged raises `signals.Cancelled` (the epoch or the cancel event). That is the receipt
status the endpoint records for that operation.

E-stop. With `remote_stop`, the bridge's native e-stop is that call, scheduled on the owned loop (it runs when the
loop is free: at an `await` of an owned coroutine, or after a blocking call returns), then the probe, then a bounded
wait for owned work to settle. The e-stop is confirmed only if the stop returned, the probe returned exactly `True`
and nothing is owned; otherwise its outcome is `unknown`, a queued stop stays owned (never dropped or duplicated), the
endpoint keeps the latch and retries, and safety reset is refused until a later e-stop confirms. Each retry stops
afresh, and close sends the stop once more before it closes the environment: a declared remote stop must be
idempotent. Only the latest stop attempt may clear an unconfirmed stop. Each e-stop and each close takes the next
attempt id. A slower attempt that finishes after a newer e-stop or close has published a failure does not clear that
failure, and it raises `MHS.OUTCOME.UNKNOWN` instead of returning a confirmed stop. A later attempt that confirms
still clears the flag. Close records a remote-stop failure on its own attempt id and does not clear an older
unconfirmed flag when close itself settles. A stop queued behind a blocking call inside the owned coroutine runs only
after that call returns; it cannot interrupt it. Without `remote_stop` the e-stop is the software latch, and while native work is owned the endpoint reports
`MHS.SAFETY.SAFE_STATE_UNREACHED` (`bridge_reports_unsafe`) instead of a stop it cannot make.

Close. Close sets the admission fence, then (when nothing is owned) runs the remote stop, `env.close()` and the loop
shutdown on the owned loop, each bounded. While native work is owned, close is deferred and resumes exactly once when
the work settles. A close that does not return within its bound is reported `unsettled` and cleanup is not claimed
complete. `async_status()["close"]` records the outcome; it stays readable after close (`describe()` includes the
same document while the bridge is open).

Seeding. `reset_kwargs` is an explicit signature: the bridge passes exactly those keywords and never retries with
others. Without `"seed"`, no seed capability is served, determinism is `none`, and the reset input `seed` remains only
for the class contract (described as not used; the output seed is 0), as the MuJoCo family does. Without `"options"`,
reset options are refused.

This profile does not combine with physics timing, JSON checkpoints or the dm_env profile. It provides no wall-clock
pacing, no remote cancellation primitive and no proof that a declared stop stops the remote system; the package's
source review and its deployment must establish that.

## dm_env and dm_control composer environments (`dm_env_v1`)

```python
dm_env_by_backend = {"sim": {"profile": "dm_env_v1", "source_refs": ["path/in/clone.py:50"]}}
```

The backend factory returns a `dm_env.Environment`; the bridge wraps it in `mhs.bridge.dm_env_adapter.DmEnvAdapter`:

- `reset()` must return a `FIRST` step; `step()` must return `MID` or `LAST`. `LAST` with discount 0 is `terminated`;
  `LAST` with a positive discount (any value in (0, 1]) is `truncated`, the dm_env convention for an episode that was
  cut. The discount of a `MID` step is informational: it is recorded in the step's info and never ends the episode. A
  `FIRST` from `step()` (an environment that restarted itself), a missing reward, a missing or out-of-range discount on
  `LAST`, or a step type that is not an exact integer FIRST, MID or LAST (a float or a string is refused, never
  converted) is a fault, never a guess.
- `action_spec()` gives the step envelope: a `BoundedArray` becomes a Box whose `minimum`/`maximum` are broadcast to
  its shape (per-element limits), a `DiscreteArray` a Discrete, an unbounded `Array` an unbounded Box (no limits).
  `observation_spec()` shapes the observation document. An integer or boolean dtype publishes integer action items, so
  a non-integral value is refused before any native call (and the adapter refuses it again rather than truncating).
  Actions are converted to the spec's dtype and shape and validated by the spec before the native call, after the
  bridge's envelope check.
- A dm_env reset takes no arguments: seeding happens when the environment is built, so no seed capability is served
  and no seeded determinism is claimed.
- The adapter's `unwrapped` is the dm_env environment, so `control_timestep()` gives the fidelity timestep.

Independently of the profile, the Gymnasium tuple path refuses any result that carries `step_type` and `discount` (a
`TimeStep` has four fields and would otherwise be read as `(observation, reward, done, info)`).

This profile does not combine with physics timing or JSON checkpoints.

## Environments built by a factory function (`native_factory`, gate G7)

Gate G7 checks a fake against an upstream class in the clone. Some suites never define their environment class: a
function of the clone composes the task and returns an instance of a class from another library (RoboPianist's
`robopianist.suite.load` returns `mujoco_utils.composer_utils.Environment`). Such a package names the function as
`native` and declares what it returns:

```python
native = "robopianist.suite:load"
native_factory = {"returns": "mujoco_utils.composer_utils.Environment",
                  "ref": "robopianist/suite/__init__.py:87-93"}
```

G7 (`mhs.driver.factory_check`) then checks, with `ast` only at the pinned commit: `native` is an undecorated,
synchronous module-level function of the clone (`FACTORY_NOT_FUNCTION`); every `return` of it is a call of exactly
`returns`, resolved through a module-level import of the function's file (`from mujoco_utils import composer_utils`;
a name the function binds itself or a relative import fails, `FACTORY_RETURN`); `ref` cites that file and covers
every return statement (`FACTORY_REF`); the class is not defined in the clone (`FACTORY_IN_CLONE`: then name the
class as `native`); and the fake implements, and the driver uses, nothing beyond the environment interface the
bridge holds such an object to (`NOT_UPSTREAM`): the dm_env interface (`reset`, `step`, `action_spec`,
`observation_spec`, `reward_spec`, `discount_spec`, `close` and dm_control's `control_timestep`) when the gate's
backend declares `dm_env_v1`, the Gymnasium environment interface otherwise. A `GymnasiumDriver` refuses the
declaration at definition unless it is exactly `{"returns": "package.module.Class", "ref": "path:LINE[-END]"}`; on
another family G7 fails `FACTORY_FAMILY`. The declaration changes no manifest or reference.

Not proven: that the external class really has that interface or behaves as the fake does, and the factory's keyword
arguments. A reviewer confirms them from the library (REVIEW.md item 7), as for every upstream class.

## Synchronous simulators and the e-stop

Every Gymnasium and MuJoCo bridge holds its mutation lock while a native step, reset or checkpoint call runs. While
one is in flight the bridge never reports the safe state achieved (`safety_status`, non-blocking). The endpoint's
e-stop attempt first gives such a bridge the rest of the e-stop budget to let the call end (`settle_native_work`: the
lock is only observed, nothing is cancelled, the wait is bounded and runs without the server lock, so the e-stop and
the call cannot deadlock). The endpoint consults only the SDK's own Gym and MuJoCo methods (compared by function
object; a package override or instance attribute is ignored), runs the call in a daemon thread joined for at most the
remaining budget, and ignores its result: a hook that raises or does not return counts as not settled. A checkpoint
restore is never waited for: while one owns the device the e-stop answers at once that the safe state is unachieved
(the restore refuses itself at its next check and its end re-asserts the stop path, which then confirms in the
background), so the e-stop never delays a restore's own cancellation or deadline. If the call ended, the e-stop is confirmed; otherwise it answers `SAFE_STATE_UNREACHED`,
keeps the latch and retries in the background until the call ends (SAFE-040). A native call already running is never
interrupted; a multi-tick command stops at the next tick, and a command cancelled while it waited for the environment
dispatches nothing, not even the implicit first reset. The same per-tick fence covers a synchronous command that has
no cancel event: an e-stop that lands between ticks raises `signals.Cancelled` before the next `env.step`, because
the call's e-stop epoch no longer matches. A direct caller that starts a step, world reset, seed or restore after the
e-stop is refused with `MHS.SAFETY.ESTOP_ENGAGED` until the safety reset clears the bridge latch. That reset clears
the latch only when no newer e-stop has engaged during the reset and the e-stop that set the latch has already
answered. When a newer e-stop has engaged, the reset returns without clearing the latch, so the endpoint can
reassert the stop. While that e-stop has not answered, including before its native stop is submitted and between a
hosted stop and its read-back, reset raises `MHS.SAFETY.RESET_REFUSED` with `reason` `stop_path_pending`. It does
not lift a host fence and does not clear the latch. Safety reset is also refused while a native call runs.

## Evidence boundary

Synthetic in-process peers exercise the owned loop, local timeouts, late settlement, e-stop ordering, close
deferral, TimeStep mapping and the stock server's receipts. They do not validate any remote simulator, dm_control,
MuJoCo, SAPIEN or hardware.
