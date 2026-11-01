# Per-tool install cost (operating-cost line for the ADR)

Honest accounting. The kit ships no container image (devcontainers are not approved in
this org, and the pilot machine had no Docker). Every number below is the install step run
directly on the dev machine (Apple Silicon, warm network); CI runners pay the same steps
via `adlc-regress.yml`'s setup block.

| Step | Measured | Notes |
|---|---|---|
| openjdk@21 + maven + act (Homebrew) | not timed | ran as one background job with the failed dotnet cask; several minutes |
| .NET 8 SDK via dotnet-install.sh | not timed | background job; well under 2 min |
| Python 3.12 via `uv python install` | 6 s | |
| `graphifyy[leiden]==0.9.97` into a fresh venv, cold cache | 6 s | 15 tree-sitter wheels, all prebuilt for arm64 |
| Serena @ commit via `uvx` (first run, builds from git) | not timed precisely | background job; ~2 min order of magnitude |
| `serena download-ls-dependencies python typescript java csharp` | 12 s | jdtls 322 MB + typescript-language-server 25 MB downloaded; pyright is fetched lazily on first use; **csharp failed: needs .NET 10 runtime** (install it alongside the .NET 8 SDK) |
| `copilot` CLI | pre-installed | Homebrew cask 1.0.60 self-updated to 1.0.105 |

Per-language language-server cost (what a platform team actually pays per repo language):

| Language | Server (pinned by Serena commit) | Install | First activation |
|---|---|---|---|
| Python | pyright 1.1.403 | lazy, ~20 MB npm | ~5 s on kestrel gateway |
| TypeScript | typescript-language-server 5.1.3 | 25 MB | not yet measured |
| Java | eclipse-jdtls (VSIX) | 322 MB | not yet measured (jdtls indexes Maven deps on first start; expect minutes) |
| C# | roslyn-language-server 5.5.0 | needs .NET 10 runtime (~70 MB) | not yet measured |

On-disk footprint of the full toolchain ≈ 3–4 GB (JDK + two .NET versions + Node + jdtls). Not measured.
Rows marked "not yet measured" are filled in by `adlc eval --tier 2` which records
Serena start-up latency per language from the MCP connect timestamps.
