OpenMHS is independent and is not affiliated with, endorsed by, or a reimplementation of Anthropic's MHS research preview.

# Gate digests of sixteen code-less records re-recorded

Sixteen records that hold no driver code (eight `skip-proposed` with `NOT_A_DEVICE`, seven `blocked` with
`HELPER_MISSING` and one `blocked` with `NO_HARDWARE_FREE_PATH`) carried a gate digest that no longer matched the gate's
output, or no gate entry at all. On 2026-11-06 the orchestrator, Claude (claude-opus-5-5, a model and not a human), re-ran
the gate of each in the project's validation environment and recorded what it reports: the gate fails G1, G2, G3 and G9
because no driver exists, and `gate.digest` is the stable digest of that run. Twelve digests were stale (the gate's
findings for a missing driver changed with earlier SDK releases, before 2026-11-05) and four records had no gate entry.

Status, `blocked_on`, notes and every other field are unchanged, no passing record is touched, and `reviewed_by` stays
null. `collect.py --strict` covers passing records only, so these digests are informational; they now let a full
re-gate of every record (all 842 `done` cards) reproduce without exception. The packages: samueldeleglise/pyivi,
thinksrs/srsgui, usnistgov/labbench, aayustark007/gym-webots, aau-cns/ardupilot_multiagent_simulation,
applied-ai-lab/ramp, ardupilot/ardupilot_gazebo, ctu-vras/husky_nav, gazebosim/gz-sensors, keerthanx9/bot_sim_ros2,
ncbdrck/uniros, optimaero/optimaeropx4sil, px4/px4-sitl_gazebo-classic, tesseract-robotics/tesseract,
vincekurtz/quadruped_drake and xwavex/py-flex-assembly.
