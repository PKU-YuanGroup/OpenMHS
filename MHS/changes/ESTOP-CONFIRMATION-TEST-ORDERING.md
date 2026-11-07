OpenMHS is independent and is not affiliated with, endorsed by, or a reimplementation of Anthropic's MHS research preview.

# Observe one coherent e-stop attempt in the confirmation regression

The back-to-back e-stop regression now takes the server lock when checking that the background retry has completed. The retry can enter its native bridge before its newly created attempt is published; an unlocked observer could combine the previous completed attempt with the new bridge call count and start its next request too early. That request could legitimately share the still-pending successful retry, causing a false test failure.

A deterministic controlled schedule reproduces the mixed observation against the unchanged SDK, confirms that the locked predicate remains false until the new attempt is published and finished, and confirms that a request after real retirement still fails when the next native stop fails. The production e-stop state machine and every failure, latch, fresh-confirmation and retry assertion are unchanged. This changes test synchronization only and makes no hardware or physical-stop claim.
