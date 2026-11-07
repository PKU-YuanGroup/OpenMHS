OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Detach public in-process replies from retained receipts

An in-process caller could mutate nested output, error or artifact metadata in
a returned response and change the server's subsequent command replay or
operation lookup. The original artifact bytes and stored descriptor remained
intact, but the retained response no longer matched the committed evidence.

`MHSServer.handle` now returns a deep copy of the decoded public response, so
in-process and serialized callers cross the same ownership boundary. The change
does not alter internal execution, commit, artifact or idempotency rules.
Four regression methods reproduce the defect on the preceding SDK and pass with
the fix: successful command replay, executed failure replay, final asynchronous
operation lookup/replay, and existing image metadata replay. Early input
rejections are not treated as executed idempotent commands. The independent
review must assess this server fix separately from the point-cloud helper.
