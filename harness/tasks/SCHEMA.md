# Golden task schema (`harness/tasks/<repo>/<id>.yaml`)

```yaml
id: web-004                      # <repo-short>-<nnn>; unique across the kit
repo: kestrel-web                # consuming repo the task runs in (working copy root)
cwd: .                           # subdir to run in (polyglot repos: booking/, pricing/, gateway/)
category: trace                  # locate | literal | trace | archaeology | cross-repo | cross-project | edit
languages: [typescript]          # python | typescript | java | csharp | docs
tier: 1                          # 1 python+ts, 2 java+c#, 3 kb/federated/both
prompt: |                        # exactly what a developer would type; no hints about tools
  Which components end up calling roundMoney, directly or indirectly?
expected: |                      # the answer a human expert gives (hidden from the agent)
  formatMoney/sumMoney/parseMoneyInput in src/lib/money.ts, MoneyText component, QuoteBreakdown, QuotePage.
rubric: |                        # what the judge scores 0/1/2 against (arm never shown)
  2 = names money.ts callers AND the MoneyText/QuoteBreakdown UI path; 1 = only money.ts; 0 = wrong/none.
judge: rubric                    # rubric | tests
test_command: null               # edit tasks: command that must exit 0 in the working copy after the edit
federated: false                 # true if the task needs `adlc query --level project|org`
grep_bait: ["roundMoney"]        # literals a naive grep would try; lint rejects tasks a single grep answers
                                 #   unless category == literal (where grep SHOULD win)
```

Rules enforced by `adlc eval --lint`:
- required keys present, enum values valid, `tier` matches languages (1: python/typescript only; 2: java/csharp; 3: docs/federated/both).
- `judge: tests` ⇔ `category: edit` ⇔ `test_command` set.
- no task is answerable from its prompt alone: `expected` must not be a substring of `prompt`.
- second-pass grep rule: for non-`literal` tasks, every `grep_bait` string run through
  `rg -l` in the repo must NOT by itself produce the files named in `expected`
  (i.e. one obvious grep must not be the whole answer).
- per repo ≥ 10 tasks; every category present at least once across the set; `cross-project`
  tasks must set `federated: true`.
