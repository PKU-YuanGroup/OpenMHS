OpenMHS is an independent project, not affiliated with, endorsed by, or a reimplementation of Anthropic's MHS research preview.

# Bounded rosbridge text fragment reconstruction

Controlled ROS2 PointCloud2 packets containing 12582912 raw bytes exceed the deployed rosbridge server's ten-million
character fragment limit after base64 encoding. Small endian controls passed, but the complete sample previously
failed when the first `fragment` envelope reached the bridge. The live WebSocket transport now reconstructs bounded
text fragments before routing their original JSON. Default transport and artifact limits are unchanged.

Partial messages share one byte budget and bounded ID/part counts, retain a fixed assembly deadline across short
receive slices, and are discarded on close or protocol failure. Interleaved ordinary responses and concurrent sends
remain possible. Invalid order, conflicting totals, oversized aggregates, nested/compressed data and expired partial
messages fail closed. Existing bridge command, subscription and artifact publication checks remain in place.

Controlled wire tests cover the complete two-fragment base64 payload, exact reconstructed bytes, interleaving, ID
reuse, deadlines, budgets, malformed messages and close/send concurrency. Real Docker validation and physical/native
device compatibility are separate evidence; this change itself makes no physical sensor or native PCL ABI claim.
