OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Fixed physics ticks for Gymnasium backends

An environment call may integrate several physics steps. With the optional
`GymnasiumDriver.timing_by_backend` declaration, the SDK accepts `ticks` in physics
units, runs the corresponding whole number of native control calls and records
observed progress in each command receipt. Configuration applies only to the
selected backend; existing undeclared backends retain their prior behavior.

The following is an illustrative declaration. Replace its source reference with
the exact pinned code and verify each assumption before enabling a backend:

```python
timing_by_backend = {
    "sim": {
        "mode": "physics_ticks_v1",
        "control_decimation": 5,
        "physics_timestep_attr": "model.opt.timestep",
        "physics_clock_attr": "data.time",
        "native_autoreset": False,
        "reset_advances_physics": False,
        "source_refs": ["path/to/environment.py:100-104"],
    }
}
```

The physics timestep is read from the constructed environment. It must be finite
and positive; the clock must be finite, non-negative and precise enough to resolve
each tick. Decimation is a fixed integer from 1 through 10,000. A step explicitly
requires both `ticks` and `action`; ticks must be a positive whole multiple of
decimation within the advertised maximum. Invalid requests are refused before
implicit reset or native step. Each control call holds the same supplied action.

For a 2 ms physics timestep and decimation 5, a request for 15 ticks makes three
native calls and, if all complete normally, reports 30 ms of simulated time.
Early termination, cancellation or failure can complete fewer ticks. Cancellation
is observed between opaque native calls; the SDK cannot interrupt their internal
physics loop. A response deadline alone does not cancel an operation. The
operation's execution bound, cancellation state and reconciliation receipt remain
separate from that deadline.

## Required backend behavior

Review native source and the deployment to establish all of the following:

- One successful native step advances exactly the declared decimation. Failed
  calls can expose measured partial advancement, but must not hide a clock reset.
- Only this bridge advances the clock; no external simulator thread or command
  does so. There is no wall-clock pacing.
- Native autoreset is disabled. Unless the declaration says otherwise (next
  section), reset does not integrate physics and restores the clock to zero.
  Bridge-managed autoreset can then keep per-command progress while resetting the
  episode counter.
- The timestep and action-space configuration remain stable for the manifest's
  lifetime. Reopen and regenerate the manifest after a configuration change.

Declaration flags and citation strings do not prove these properties. Runtime
checks detect observable violations, but cannot prove that a native call did not
advance and rewind its clock internally. Variable decimation, free-running
simulators and opaque autoreset need another adapter contract.

## Resets that integrate physics

Many tasks let objects settle during reset. Declare it explicitly:

```python
timing_by_backend = {
    "sim": {
        "mode": "physics_ticks_v1",
        "control_decimation": 25,
        "physics_timestep_attr": "sim_timestep",
        "physics_clock_attr": "physics_clock_s",
        "native_autoreset": False,
        "reset_advances_physics": True,
        "reset_clock": "continue",       # or "restart": the reset rewinds the clock to zero, then integrates
        "max_reset_ticks": 1250,         # 1..1,000,000 physics ticks per reset
        "source_refs": ["path/to/environment.py:302-316"],
    }
}
```

`reset_clock` and `max_reset_ticks` are refused unless `reset_advances_physics` is
true, and both are required when it is. Each reset (explicit, the implicit first
reset of a step, or a bridge-managed autoreset) is measured: with `restart` the
clock after the reset counts the integration from zero; with `continue` the
difference across the reset does. The count must lie on the timestep grid and
within `max_reset_ticks`; otherwise the reset is a timing fault, its tick count is
unresolved, and steps are refused until a verified reset. Reset ticks are never
episode ticks: the episode `tick` restarts at zero after the reset, and control
ticks continue from the settled clock. The `cap.world.reset.v1` binding then carries
the same `x-vendor.openmhs_simulation_timing` descriptor (with
`reset_advances_physics`, `reset_clock` and `max_reset_ticks`), and its receipts
report `reset_integrated_ticks`, `known_reset_integrated_ticks` and
`reset_integrated_duration_ms`; step receipts of such a backend report the reset
ticks of any reset inside the command the same way. Declarations without
`reset_advances_physics: true` produce byte-identical descriptors and receipts to
the original contract. JSON checkpoints remain available (the saved episode tick
stays a whole number of control periods); a backend whose native state is
incomplete can opt out explicitly ([gym-checkpoints.md](gym-checkpoints.md)).

## Published contract and receipts

The device profile's `operating_notes` and the step binding's
`x-vendor.openmhs_simulation_timing.notes` name the physics timestep and control
period. `fidelity.timestep_ms` must be the physics timestep. A conflicting backend
fidelity override or a claim of pacing is rejected. Timed fake/sim manifests must
come from their own constructed instances, not a projection of another backend.

Receipts use `x-vendor.openmhs_simulation_timing` for the requested count, exact
completed count when known, verified lower bound, simulated duration, control and
reset counts, in-flight state and explanatory notes. `progress.ticks` is the
verified lower bound for this command. The stable output's `tick` remains the
episode count; it may reset during an autoreset. `x-vendor.duration_ms` remains
elapsed wall-clock time.

While a native call or reset is unresolved, exact completed ticks and simulated
duration are null. Receipt generation reads a command-local ledger, not the
native clock from another thread. The original timeout receipt remains immutable;
a later final receipt carries the reconciliation link and updated evidence.

Native exceptions, invalid observations/results and timing faults retain measured
progress and prevent another step until a verified explicit reset or reopen.
Failed reset verification cannot clear that fault. Enabled snapshots include a
timing fingerprint and the verified clock sample. Restore refuses legacy or
mismatching timing snapshots before calling the native setter and cannot bypass a
latched timing fault.

## Evidence boundary

Synthetic peers exercise the stock server, timeout/reconciliation, partial
advancement, malformed results, reset failures and floating-clock accumulation.
These tests do not validate MuJoCo, Gazebo, a robot package or hardware. Existing
untimed behavior remains compatible; it is not retroactively certified against
FID-015. The pre-existing stock Gym snapshot/restore hash mismatch is tracked
separately; direct bridge snapshot tests are not a successful stock-server
round trip.
