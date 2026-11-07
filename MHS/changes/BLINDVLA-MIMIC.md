OpenMHS is not affiliated with, endorsed by, or a reimplementation of Anthropic's MHS research preview.

# BlindVLA mimic finger target

The Empty-v1 fake assigned the gripper target to one finger and its negative to the other. Pinned `06855fcb91d65c88ca351a2d45af0be860a91987`, `ManiSkill/mani_skill/agents/controllers/pd_joint_pos.py:84-86`, broadcasts the same absolute action target to both joints. The fake now follows that relation, and tests check both coordinates for positive, zero and negative normalized commands.

Nine stock-server package cases and the complete actual G1-G9 fake gate pass. The action envelope is unchanged. Updated fidelity prose explicitly retains the instantaneous target-to-position approximation, absent external Panda URDF joint-limit evidence, and unmodelled actuator/contact dynamics. A configured negative drive target is not evidence of a physically reached negative finger position. This closes the sign-relation part of handoff L09; external asset limits and physical fidelity remain unresolved.

Changed files are driver.py, fake.py, test_driver.py, facts.md, reference.json, REFERENCE.md, RESULT.json and check-report.json in the cognitiveaisystems/blindvla package. DeepSeek authorship and null human signature are unchanged. Originals, test output and integration hashes are under work/handoff-runs/mhs-build-20261102/development/blindvla-mimic/ and originals/blindvla-mimic-integration/. No upstream simulator, assets download or hardware was run.
