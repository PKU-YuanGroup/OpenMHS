OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Gym JSON checkpoints

`GymnasiumDriver` offers protocol snapshot/restore only with an explicit profile for the selected backend:

```python
checkpoint_by_backend = {
    "fake": {"profile": "json_state_v1", "getter": "get_state",
             "setter": "set_state", "max_bytes": 262144},
}
```

Direct `GymnasiumBridge` construction accepts the same object as `checkpoint=`. Public dotted paths resolve on the explicitly supplied environment. There is no implicit `unwrapped` or wrapper search. Configuration is copied; the selected instance cannot be projected as a backend with a different checkpoint profile.

The getter must synchronously return builtin JSON values. The setter must synchronously finish restoring the supplied JSON value and return `None`. Async/generator declarations and unavailable methods are refused. A setter returning an unsupported completion object produces an unknown outcome and permanently fences checkpoint capture, restore, ordinary world mutations and safety reset on that bridge, and e-stop/safe-state cannot acknowledge achieved safety; completion is not guessed from the returned object. This profile provides no async checkpoint lifecycle or hidden-worker cancellation. A backend that starts hidden work must not use this synchronous profile. Discarding or reopening an endpoint does not prove the old hidden worker stopped. If a setter returned an unsupported completion object, native cleanup remains withheld on that bridge even after endpoint close; this profile has no sound termination/reconciliation contract for that object. The retained environment is not reused.

The getter/setter pair must include all state needed by the backend's claimed continuation: wrapper counters, termination state, native RNG state and any subsequent-reset RNG state. Source evidence and package tests must establish that coverage. The SDK verifies only the represented state; a profile or method name does not prove hidden-state completeness or exact determinism. The derived determinism remains `seeded`. A source-reviewed package may declare a stronger claim separately only when justified.

Enabled instances add readonly `world.native_checkpoint` with `profile`, `configuration_digest`, `native_state`, `pending_seed`, and (with physics timing) `simulation_timing` and `physics_clock`. It is part of the served state and its normal hash, without exclusions. Snapshot `state`/`snapshot` are identical resource-document aliases. The endpoint validates envelope identities, alias agreement, both digests, exact resource keys and declared state schemas before native restore, then verifies the actual post-state. Partial native failures attempt verified rollback; failure without provable rollback is unknown. An intervening e-stop prevents a successful restore claim and reasserts stop.

The checkpoint retains public observation/reward/terminal flags/tick/episode/seed/info and pending seed. A normalized saved observation is adapter-owned until the next native reset/step; it is never guessed back into a native array or fed into the setter. The native JSON getter/setter supplies actual simulator continuity. Physics timing additionally verifies saved configuration, finite nonnegative clock, control-period-aligned tick, current timestep and the restored native clock. Existing timing faults still require a verified world reset or reopen; restore cannot clear them.

JSON values must have string object keys, finite numbers and exactly representable integers (magnitude at most `2**53-1`; larger values require explicit decimal-string codecs). Tuples, arrays, custom objects, cycles and invalid Unicode are refused. The complete served world document is bounded by `max_bytes`: default 256 KiB, configurable 1 KiB to 1 MiB. Maximum depth is 32 and traversal nodes 65,536. Validation precedes encoding/copy; the getter's internal allocation is outside this post-return bound. No pickle, file load, token or checkpoint cache is used.

Enabled world step/reset/seed bindings are exclusive, sharing the endpoint mutation lane with capture/restore. An explicit `exclusive=False` is refused. The endpoint also retains restore ownership before method-descriptor resolution, across validation, effects, postchecks and rollback. Its bridge context keeps the original e-stop epoch across nested rollback calls; a later safety reset cannot erase that history. A timed-out caller does not release an executing worker's lane; retries retain their command identity. Reads during native checkpoint work return busy rather than queue behind it. Independent e-stop remains available. Safety reset refuses while native checkpoint/step work owns the bridge lock.

Close sets an irreversible admission fence before native cleanup. Synchronous native ownership covers calls, checkpoint descriptors/getters/setters, resource reads and schema inspection; nested ownership keeps the environment alive through the outer restore context. Calls queued before close recheck the fence before mutation. Cleanup occurs exactly once after all admitted synchronous work exits; close does not cancel an already-running native call, and its late effect may still occur before deferred cleanup. Independent safety status remains unachieved while closing. The unsupported-completion case above deliberately withholds cleanup because termination is unknown.

The bridge's lifetime native-step budget is private admission state, not restorable world state. Each enabled native step dispatch consumes one unit, including a call that later raises; restore, rollback and reset never replenish it. Logical episode ticks can rewind while the lifetime budget remains consumed.

A backend may opt out explicitly: `{"profile": "none", "reason": "..."}` (a reason of 1 to 300 characters, no other keys). It configures nothing native; snapshot support stays false, the reason is appended to that backend's fidelity gaps, a `snapshot_restore=True` fidelity claim for that backend is a definition error, and a manifest for that backend cannot be projected from another backend's instance. Use it where the native state API is known to be incomplete (for example task, RNG or wrapper state missing), so the omission is recorded rather than implied.

Without a profile, public reads/actions and otherwise valid reference bytes remain unchanged. Derived snapshot support is false; method presence no longer infers exact determinism. An explicit `snapshot_restore=True` without a selected profile is a definition error with migration guidance. Old native-only Gym snapshot objects are unsupported protocol inputs.

The shared resource-schema guard also refuses structurally incompatible native-only MuJoCo snapshots before publication or native restore. It does not repair MuJoCo's separate representation mismatch or establish MuJoCo snapshot support. These changes have been tested with controlled peers, not a real Gym/MuJoCo runtime or physical hardware.
