# UR3 native admission remains closed

At commit10f96dc362a7700b14e4a2469c8025134ef3e4f7, `controllers.py:482-489` sends asynchronously after clearing its result/handle; `493-498` cancels only a known handle without awaiting it; `500-515` waits up to15seconds. `arm.py:578-579` dereferences the result even when unavailable. An earlier remote action can remain capable of effects after a local timeout/error. Dashboard acknowledgement does not retire that owner.

`ur_services.py:71-75` calls a synchronous ROS client without a wait bound. retry=False at147-159 avoids reconnect side effects but does not bound the call. The former package factory initialized ROS, created a node/executor/thread, then constructed Arm without failure unwind or teardown. No source-proven owned shutdown policy exists in that implementation.

The current connect function refuses before importing ROS or creating a thread. It does not become live merely because a human signature is later added. Enablement requires separately reviewed owned construction/unwind/shutdown, bounded transport and explicit retirement/fresh-stop evidence, followed by authorized native validation. No such validation occurred here.
