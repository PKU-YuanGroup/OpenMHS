OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Explicit operation cancellation respects the admitted binding

The server previously signalled every running operation when a client called
`mhs.operations.cancel`, even when its capability declared `cancellable: false`
or omitted the flag. It now captures the resolved binding's cancellation flag
when starting the operation and returns `MHS.OPERATION.NOT_CANCELLABLE` before
changing a noncancellable operation's event, reason or receipt. Bindings remain
identified by capability and resource; later capability metadata does not grant
cancellation to work already admitted.

Session and principal visibility checks run first. Already finished operations
still return the retained final receipt, including completed work, without a
new cancellation request. Existing cancellation of cancellable operations,
execution-bound handling and protective emergency-stop/session cleanup paths
retain their distinct behavior. A refusal does not claim the operation or its
physical effect has stopped.

Twelve stock SDK regression tests cover false and omitted flags, ordinary and
long-running work, repeated requests, equal capability IDs on separate resources,
later metadata changes, retained terminal receipts, principal/session visibility,
the public client, bounded pending cancellation, execution bounds and emergency
stops. The unchanged SDK reproduces the noncancellable defect; the exact original
JobBridge probe passes after the repair with its cancellable positive control.
Post-integration validation on 2026-11-04 completed the full SDK suite: 2,763
tests, five skipped, with every executed test passing. All 409 SDK inputs and
1,034 dependency files were unchanged during the run. Two existing cancellation
tests now explicitly declare their cancellable precondition; their assertions
and the production cancellation contract remain unchanged. This supersedes the
earlier aggregate invocation count, which included a failed fixture setup and
a separate rerun rather than 696 distinct passing tests.
