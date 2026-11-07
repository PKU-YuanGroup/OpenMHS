OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Retained Python native execution

PythonObjectBridge previously treated the caller's timeout as the end of a nested synchronous setter. A stock
server reproduction returned UNKNOWN, then reported a successful e-stop and safety reset while the setter was
still blocked. Releasing it changed the output after two stop calls. The runtime now retains the whole native
completion chain, including Status/Future/awaitable returns and cancellation cleanup. A deadline bounds the
caller; it does not prove native termination.

Ordinary effectful admission is fenced while work is active or uncertain. Safety calls can run independently,
but cannot acknowledge safety until earlier executions have really settled. Recovery needs a fresh successful
native stop followed by explicit safety reset. Native reset is itself retained and checked against intervening
activity. Closing is irreversible and owned cleanup is deferred until active work settles. Declared reads,
snapshots and interlocks remain observational; a package must not hide effects in those bindings.

The first private repair passed its scoped suite but failed independent review: a Status returned by cancellation
could raise from wait while still pending, and unknown done/success flags could be mistaken for completion.
Version two uses the same conservative terminal resolver for primary and cancellation-return chains. Both exact
counterexamples now keep stop unachieved and reset rejected until terminal settlement. The original late setter
can still execute; this repair prevents false safety claims and premature reuse, not arbitrary native effects.

Validation before integration: 287 bridge tests pass with one skip; 23 family tests pass. Independent stock-server
replays cover the original defect and both v1 counterexamples; 39 independent retention/safety tests pass.
The integrated bridge/family run and complete SDK/corpus checks are recorded separately. No native dependency,
upstream driver, ROS graph, device or hardware execution is claimed. A forever-running native task may keep its
bridge fenced indefinitely; no thread is forcibly killed. This change applies to PythonObjectBridge, not arbitrary
direct Driver implementations, and does not by itself implement the remaining object helper families.
