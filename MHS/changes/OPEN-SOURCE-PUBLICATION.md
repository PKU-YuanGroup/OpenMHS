# Open-source publication and device catalog

OpenMHS is the open-source Model Hardware Standard at https://mhs.openai4s.org.
Schema identifiers now use `/schema/0.9/` on that domain. The SDK still reads the earlier placeholder and legacy
identifiers, so existing 0.9 documents continue to work. Wire revision and SDK version are unchanged.

Remove the mandatory README/page disclaimers, the publication checks banning Chinese text and CNAME files,
and the CI rule limiting each driver pull request to a single package. Retain license files, clean-clone
validation, private-path checks, device limits, interlocks, access control, emergency stops and evidence integrity.

Missing registry data and broken installed SDK imports produce errors instead of silent success or generated
placeholder records. Playground includes every passing adaptation, with optional upstream checkouts on demand.
Historical `publish_review` labels do not exclude passing packages from this owner-authorized publication.
