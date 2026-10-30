# Reusable workflows

GitHub only resolves `workflow_call` workflows from a repository's `.github/workflows/`,
so the five reusable workflows live in [`../.github/workflows/`](../.github/workflows/):

| Workflow | Trigger in a consuming repo | Enforces |
|---|---|---|
| `adlc-contract-lint.yml` | pull_request (required check) | AGENTS.md + adlc block valid; cited paths exist; pins match; single instruction source |
| `adlc-baseline.yml` | push to main | graph rebuilt, stamped, committed; project repo notified |
| `adlc-drift.yml` | nightly | artifact ≤ N commits behind HEAD, any level |
| `adlc-regress.yml` | weekly + tool bumps | smoke set on the winning arm, trend appended |
| `adlc-scorecard-upload.yml` | after regress | trend published for the org aggregator |
| `adlc-federate.yml` | repository_dispatch (project/org repos) | L1/L2 rebuilt on member change |

`adlc init` writes a 10-line `.github/workflows/adlc.yml` into the consuming repo that
`uses:` these at the kit's tagged ref. Local verification: `make workflow-test` runs the
contract-lint job with `act` against a fixture repo (see `tests/test_workflows.py`).
