OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Finite ROS image sources and per-capture headers

A single ROS driver package previously exposed one fixed image stream and omitted the source header. The opt-in `cameras` declaration now selects among a finite set of static, source-checked image subscriptions through the existing `camera` input. Each capture retains complete pixels and the exact validated ROS1 or ROS2 header in its scoped artifact descriptor. The stable four-field image output and legacy flat subscription behavior stay unchanged; no synchronized capture, producer freshness or physical-camera validation is claimed.

Artifact descriptor extensions are bounded detached JSON. Store grants, MCP routes and receipt replay retain their own metadata while enforcing the original session, expiry, byte budgets and cleanup. Every image source participates in G7; conversion and selector policy participates in G3 integrity checks. No native admission or human-signature rule changes.

Controlled validation passed 448 relevant SDK tests with one unavailable external interoperability test skipped. Twenty-two new methods include all pixels at 1920x1080 color and 512x424 depth/IR geometry through stock MCP, malformed headers, source association, bounded metadata, cancellation and gate integrity. The synthetic full package gate retains its explicit synthetic-source and no-actuating-limit warnings. Legacy and counterfactual controls preserve the old behavior and demonstrate the metadata/policy repairs. This change does not itself author or accept a Kinect2 package or validate a native camera.
