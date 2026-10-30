# Adoption test assets (Phase 8)

`tasks/` is a separate task root for the distribution test on a repo the kit has never
seen (`kestrel-notify`). It is deliberately not part of `harness/tasks/` so the main set
keeps its ≥10-per-repo rule. Run: `adlc eval --adoption-test repos/kestrel-notify --tasks
adlc-kit/harness/adoption/tasks --task nfy-001 --results results`.
