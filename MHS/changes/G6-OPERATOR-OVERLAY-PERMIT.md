OpenMHS is independent and is not affiliated with, endorsed by, or a reimplementation of Anthropic's MHS research preview.

# Input-bound permits for the positive operator-overlay control

G6 used to reject a correctly declared action with both an operator-required input and a required permit: its positive overlay supplied the permitted input but omitted the permit. The positive simulated-endpoint control now obtains one bounded, exact-input, single-use permit through the stock server before sending the command. Missing and partial overlays still run without permits and must refuse before any actuation.

This changes only the local acceptance-test client. It does not change server authorization, issue hardware approvals, execute native factories, initialize a device, or turn a failed stop into success. The permit helper explicitly refuses a hardware-view session. Separate stock controls reproduce the old G6 false failure and preserve zero actuation for missing or reused permits.

This generic permit correction does not initialize a device or waive an initial-state, stop or native/device/license requirement. The separate finite SiLA fake prerequisite profile handles its explicit Connect through the stock session/permit/command path.
