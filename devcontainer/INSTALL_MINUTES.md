# Per-tool install cost (operating-cost line for the ADR)

Measured on the pilot dev machine (Apple Silicon, 2026-10-30), wall-clock, warm network.
Docker was not available on the pilot machine, so the image build itself was NOT timed;
the per-step numbers below are from installing the same pins directly.

| Step | Minutes | Notes |
|---|---|---|
| openjdk@21 + maven (brew) | 2.1 | |
| .NET 8 SDK (dotnet-install.sh) | 1.4 | cask needed sudo; script does not |
| uv + Python 3.12 | 0.2 | |
| graphifyy[leiden]==0.9.97 into a venv | 0.6 | 15 tree-sitter wheels |
| Serena @ commit via uvx (first run) | 1.9 | builds from git; cached after |
| Serena python LS (pyright, downloaded by Serena on first use) | 0.5 | into ~/.serena cache |
| basedpyright 1.29.5 | 0.2 | |
| typescript-language-server 4.3.4 | 0.3 | |
| jdtls 1.43.0 tarball | 0.8 | ~110 MB |
| csharp-ls 0.18.0 | 0.9 | dotnet tool |
| **Total** | **~9 min** | image size estimate ≈ 3.5 GB (JDK + .NET + Node) |
