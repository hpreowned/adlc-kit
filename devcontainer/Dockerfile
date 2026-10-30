# ADLC devcontainer — every tool a repo's agent needs, pinned. Built and published by the
# kit's release workflow as ghcr.io/kestrel-freight/adlc-devcontainer:<kit version>.
# Pins come from adlc/pins.json; `adlc pins --check` fails the build if they drift.
FROM mcr.microsoft.com/devcontainers/base:ubuntu-24.04

ARG KIT_REF=v0.1.0
ARG COPILOT_CLI_VERSION=1.0.105
ARG GRAPHIFY_VERSION=0.9.97
ARG SERENA_COMMIT=ede329aaf0c824bea75455a2926f01420d7aa620

ENV DEBIAN_FRONTEND=noninteractive \
    GRAPHIFY_BACKEND=none GRAPHIFY_NO_TIPS=1 \
    DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1 \
    UV_TOOL_BIN_DIR=/usr/local/bin PATH=/opt/jdtls/bin:/usr/local/bin:$PATH

# --- base toolchains: Java 21, .NET 8, Node 22, Python 3.12 (via uv) --------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
      openjdk-21-jdk-headless maven ca-certificates curl git jq unzip \
    && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL https://dot.net/v1/dotnet-install.sh | bash -s -- --channel 8.0 --install-dir /usr/share/dotnet \
    && curl -fsSL https://dot.net/v1/dotnet-install.sh | bash -s -- --channel 10.0 --runtime dotnet --install-dir /usr/share/dotnet \
    && ln -s /usr/share/dotnet/dotnet /usr/local/bin/dotnet
# (.NET 8 SDK builds the pricing service; the .NET 10 *runtime* is required by Serena's Roslyn language server 5.5.x)
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && apt-get install -y nodejs && rm -rf /var/lib/apt/lists/*
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh && uv python install 3.12

# --- Copilot CLI, pinned, auto-update disabled (bundled == pinned) -----------------------
RUN npm install -g @github/copilot@${COPILOT_CLI_VERSION} \
    && printf '#!/bin/sh\nexec /usr/lib/node_modules/@github/copilot/bin/copilot --no-auto-update "$@"\n' > /usr/local/bin/copilot-pinned \
    && chmod +x /usr/local/bin/copilot-pinned

# --- the kit (brings graphifyy[leiden]==GRAPHIFY_VERSION as a locked dependency) --------
RUN uv tool install --python 3.12 "git+https://github.com/kestrel-freight/adlc-kit@${KIT_REF}" \
    && adlc --version && graphify --help >/dev/null

# --- Serena at a commit; warm the uvx cache so first MCP start is fast -------------------
RUN uvx --from "git+https://github.com/oraios/serena@${SERENA_COMMIT}" serena --help >/dev/null

# --- four language servers: pinned by Serena itself (solidlsp), pre-downloaded ---------
# pyright 1.1.403 · typescript-language-server 5.1.3 (+ typescript 5.9.3) · eclipse-jdtls VSIX
# (sha256-pinned in solidlsp) · roslyn-language-server 5.5.0-2.26078.4
RUN uvx --from "git+https://github.com/oraios/serena@${SERENA_COMMIT}" serena download-ls-dependencies python typescript java csharp

LABEL org.opencontainers.image.source="https://github.com/kestrel-freight/adlc-kit" \
      adlc.kit="${KIT_REF}" adlc.copilot="${COPILOT_CLI_VERSION}" adlc.graphify="${GRAPHIFY_VERSION}" adlc.serena="${SERENA_COMMIT}"
