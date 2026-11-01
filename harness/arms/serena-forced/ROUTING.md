## Context routing (kit-owned — do not edit; `adlc init` rewrites this section)

Text search (`rg`, `grep`, `grep_search`, code-search subagents) is **disabled** in this
repo. Navigate by symbol with the Serena tools, which are connected:
- **Find where something is defined**: `find_symbol` with the name or a substring
  (`name_path_pattern`), `include_body: true` to read it.
- **See what a file contains**: `get_symbols_overview` on the file.
- **Find who uses it / what breaks**: `find_referencing_symbols` on the symbol.
- **Interfaces and overrides**: `find_implementations`.
- **Edit precisely**: `replace_symbol_body`, `insert_after_symbol`, `insert_before_symbol`.
- Start from `list_memories` / `read_memory` for the repo's conventions.
Listing files (`glob`) and reading them (`view`) are fine. Do not try to work around the
search block with shell pipelines; the hook denies them and the attempt costs a turn.
