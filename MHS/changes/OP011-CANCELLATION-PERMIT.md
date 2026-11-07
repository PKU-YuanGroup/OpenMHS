OpenMHS is independent and is not affiliated with, endorsed by, or a reimplementation of Anthropic's MHS research preview.

# Required permit for the positive cancellation control

OP-011 previously sent its positive cancellable operation without a required permit, so a correctly declared permit-gated action failed before returning an operation handle. The control now resolves the selected capability and resource together, obtains the exact-input permit through the existing suite policy, and then runs the unchanged cancellation assertions. Missing, wrong-input and reused permits still return PERMIT_INVALID with zero native or bridge actuation. Ungated actions request no permit; hardware sessions without operator approvals receive none.

An independent stock thermostat counterfactual fails before and passes after this change. This changes conformance preparation only, not server authorization, operation cancellability, safety semantics or hardware admission.
