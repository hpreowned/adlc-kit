# Copilot CLI `events.jsonl` — observed schema (CLI 1.0.73)

Location: `$COPILOT_HOME/session-state/<session-id>/events.jsonl`. One JSON object per
line: `{type, data, id, timestamp, parentId, [ephemeral]}`. Undocumented upstream; this
file records what `harness/events.py` relies on, derived from 22 real sessions on the
pilot machine plus the harness smoke runs. Re-verify on every Copilot CLI bump
(`adlc-regress` runs the parser tests against a fresh fixture).

## Events the parser consumes

| type | fields used | metric |
|---|---|---|
| `session.start` | `data.sessionId`, `data.copilotVersion`, `data.context.{cwd,branch,headCommit}` | identity, freshness at start |
| `session.auto_mode_resolved` | `data.chosenModel`, `data.candidateModels` | model stratification (auto mode) |
| `assistant.turn_start` | `data.turnId`, `data.model` | turns, models seen |
| `tool.execution_start` | `data.toolCallId`, `data.toolName`, `data.arguments` | tool calls by name; MCP tools appear as `<server>-<tool>` |
| `tool.execution_complete` | `data.toolCallId`, `data.success`, `data.toolTelemetry.metrics.{resultLength,resultForLlmLength,result_token_count}` | bytes-read proxy (read-ish tools only) |
| `session.usage_record` | `data.usage.{model,inputTokens,outputTokens,cacheReadTokens,cacheWriteTokens,reasoningTokens,cost,duration,isAuto}` | per-model-call accounting; `cost` is the premium multiplier for that call |
| `skill.invoked` | `data.name`, `data.source` (`project`/`personal`) | skill usage (e.g. `/graphify`) |
| `session.shutdown` | `data.totalPremiumRequests`, `data.tokenDetails.{input,cache_read,cache_write,output}.tokenCount`, `data.modelMetrics.<model>.usage.*`, `data.totalApiDurationMs`, `data.codeChanges.{linesAdded,linesRemoved,filesModified}` | PRIMARY totals |

## Cross-checks
- stdout (`--output-format json`) ends with `{"type":"result","sessionId","exitCode",
  "usage":{premiumRequests,totalApiDurationMs,sessionDurationMs,codeChanges}}`. The
  harness stores it beside events.jsonl and flags any disagreement with `session.shutdown`.
- `sum(usage_record.cost)` should equal `totalPremiumRequests`; a mismatch is reported,
  not silently resolved. Known upstream undercount: github/copilot-cli#1582 (`/usage`).
- Premium requests were observed as `0` for some auto-selected models and `1` for
  others on the same prompt; the scorecard therefore reports premium requests per
  resolved model, never pooled across models.

## Events observed but ignored
`session.model_change`, `session.usage_checkpoint` (`totalNanoAiu`), `session.tools_updated`,
`session.mcp_server_status_changed`, `session.mcp_servers_loaded`, `session.mcp_server_tools_loaded`
(useful: `data.toolCount` per server), `session.skills_loaded` (first launch only),
`system.message` (full system prompt — scrubbed from fixtures), `user.message`,
`assistant.message{_start,_delta}`, `assistant.turn_end`, `assistant.idle`, `model.call_start`,
`model.call_finished`, `skill.context_delivered_ref`.

## Scrubbing
Fixtures and raw logs committed under `results/` have `system.message.content`,
`reasoningOpaque`, request ids, absolute temp paths and anything matching `gh[opsu]_…`
removed (`harness/scrub.py`).
