# AI Clone Engine of Charles-Earl-Lipshay · lippytm · lippytmai

> **Version 2.1 — Full-Stack Edition**
> Added: Anthropic Claude Fable 5, Nous-Hermes, OpenRouter, complete Computer Software / Blockchain / Linux language library & ecosystem knowledge base

---

## Overview

The **AI Clone Engine of Charles-Earl-Lipshay** (`lippytmai`) is a modular, extensible AI personality engine that simulates the thoughts, communication style, knowledge base, and responses of **Charles Earl Lipshay** ([@lippytm](https://github.com/lippytm)).

| Feature | v1 Clone | v2.0 Engine | v2.1 Full-Stack |
|---|---|---|---|
| Static responses | ✅ | ✅ | ✅ |
| Dynamic conversation memory | ❌ | ✅ | ✅ |
| Personality profile config | ❌ | ✅ | ✅ |
| Pluggable LLM backends | ❌ | ✅ | ✅ |
| Anthropic Claude Fable 5 | ❌ | ❌ | ✅ |
| Nous-Hermes (local & cloud) | ❌ | ❌ | ✅ |
| OpenRouter cloud routing | ❌ | ❌ | ✅ |
| Computer Software lang libraries | ❌ | ❌ | ✅ |
| Blockchain lang libraries | ❌ | ❌ | ✅ |
| Linux system libraries | ❌ | ❌ | ✅ |
| Full ecosystem & env knowledge | ❌ | ❌ | ✅ |
| CLI API | ❌ | ✅ | ✅ |
| Session context | ❌ | ✅ | ✅ |

---

## Project Structure

```
AI-Clone-Engine-lippytmai/
├── engine/
│   ├── __init__.py          # Engine package (v2.1.0)
│   ├── core.py              # CloneEngine — main orchestrator
│   ├── personality.py       # Personality traits & style rules
│   ├── memory.py            # Conversation & long-term memory
│   └── responses.py         # Response generation & formatting
├── config/
│   ├── engine_config.json   # Engine runtime settings (all backends listed)
│   └── personality_profile.json  # Full language/blockchain/Linux knowledge base
├── api/
│   ├── __init__.py
│   └── chat.py              # CLI & programmatic chat interface
├── main.py                  # Entry point
├── requirements.txt
├── setup.py
└── LICENSE                  # GNU GPL v3
```

---

## Quick Start

### 1. Install (core — no external deps, uses mock backend)

```bash
pip install -r requirements.txt
python main.py
```

### 2. Install with a specific backend

```bash
# Anthropic Claude Fable 5
pip install -e ".[anthropic]"
export ANTHROPIC_API_KEY=your_key

# OpenAI
pip install -e ".[openai]"
export OPENAI_API_KEY=your_key

# Nous-Hermes via Ollama (local, free)
pip install -e ".[hermes]"
ollama pull nous-hermes2   # or: ollama pull hermes3

# OpenRouter (cloud — access Hermes 3 405B, Fable 5, GPT-4o, and 200+ models)
pip install -e ".[openrouter]"
export OPENROUTER_API_KEY=your_key

# Everything
pip install -e ".[all]"
```

### 3. Use programmatically

```python
from engine.core import CloneEngine

engine = CloneEngine()
response = engine.chat("What's your take on Solidity vs Rust for smart contracts?")
print(response)
```

### 4. CLI flags

```bash
python main.py --session my_session   # Named session (persistent memory)
python main.py --reset                # Clear all session memory
python main.py --profile              # Print current personality profile
python main.py --version              # Print engine version
```

---

## LLM Backends

| Backend | Key | Default Model | Requires |
|---|---|---|---|
| Mock (offline) | `mock` | — | nothing |
| OpenAI | `openai` | `gpt-4o` | `OPENAI_API_KEY` |
| **Anthropic Fable 5** | `anthropic` | `claude-fable-5` | `ANTHROPIC_API_KEY` |
| **Nous-Hermes (local)** | `hermes` | `nous-hermes2` | Ollama running |
| Ollama (generic) | `ollama` | `llama3` | Ollama running |
| **OpenRouter (cloud)** | `openrouter` | `nousresearch/hermes-3-llama-3.1-405b` | `OPENROUTER_API_KEY` |

### Switching backends

Edit `config/engine_config.json`:

```json
{
  "backend": "anthropic",
  "model": "claude-fable-5",
  "temperature": 0.85,
  "max_tokens": 512,
  "memory_window": 20,
  "session_persist": true
}
```

Or for Hermes 3 via OpenRouter:

```json
{
  "backend": "openrouter",
  "model": "nousresearch/hermes-3-llama-3.1-405b"
}
```

---

## Knowledge Base

The personality profile (`config/personality_profile.json`) covers:

### Computer Software Languages
Systems: C, C++, Rust, Zig, Go, Assembly (x86-64/ARM/RISC-V), D  
General-purpose: Python, Java, Kotlin, Scala, Swift, C#, F#, Haskell, OCaml, Erlang, Elixir  
Scripting: JavaScript, TypeScript, Ruby, PHP, Perl, Lua  
Data/Scientific: R, Julia, Fortran, Clojure, Racket, Scheme  
Web: HTML5, CSS3, WebAssembly (WASM/WASI), SQL, GraphQL  
Mobile: Dart/Flutter, React Native, Kotlin Multiplatform  
Emerging: Nim, Crystal, V, Odin, Carbon, Mojo, Gleam, Elm, PureScript, Idris

### Blockchain & Smart Contract Languages
EVM: Solidity, Vyper, Yul/Yul+, Huff, Fe  
Solana: Rust + Anchor framework  
Polkadot: Rust + Ink! (Wasm), Substrate SDK  
Aptos/Sui: Move language, Move Prover  
StarkNet: Cairo, Sierra IR, Scarb  
Tezos: Michelson, LIGO (CameLIGO/JsLIGO), SmartPy  
Cardano: Plutus (Haskell), Marlowe  
Stacks/Bitcoin: Clarity  
Algorand: TEAL, PyTEAL  
Cosmos: CosmWasm (Rust), IBC protocol  
NEAR: AssemblyScript  
Flow: Cadence  

Tooling: Hardhat, Foundry, Truffle, Brownie, Anchor CLI, OpenZeppelin, Ethers.js, viem, The Graph, Chainlink, Slither, Echidna

### Linux System Libraries
C runtimes: glibc, musl, POSIX APIs  
Threading/IPC: libpthread, librt, dbus-1/GDBus, libsystemd  
Security: libssl/OpenSSL, GnuTLS, libseccomp, libcap, libpam  
Networking: libcurl, libssh2, libevent, libuv, libpcap, nghttp2  
Graphics/UI: GTK4, Qt6, SDL2/SDL3, Mesa/OpenGL, Vulkan, X11, Wayland, DRM/KMS  
Audio: ALSA, PulseAudio, PipeWire  
Compression: zlib, lz4, zstd, bzip2/xz  
Databases: SQLite, libpq, hiredis, librocksdb, liblmdb  
Kernel/eBPF: libbpf/eBPF, liburing (io_uring), libfuse, libnl, libelf  
Parsing: libxml2, libwebsockets, GLib/GObject

### Package Ecosystems & Environments
Python (pip/conda/poetry/uv), Node.js (npm/yarn/pnpm/Bun/Deno),  
Rust (cargo/crates.io), JVM (Maven/Gradle/sbt/GraalVM),  
.NET (NuGet/dotnet), Ruby (Gems/Bundler), PHP (Composer),  
Go (modules), C/C++ (CMake/Conan/vcpkg), Haskell (Stack/Cabal),  
OCaml (OPAM/Dune), Erlang/Elixir (Hex/Mix), Scala (sbt/Mill),  
Swift (SPM), Dart (pub.dev), R (CRAN), Julia (Pkg.jl),  
Containers (Docker/Podman/K8s/Helm), Cloud SDKs (AWS/GCP/Azure),  
CI/CD (GitHub Actions/GitLab CI/ArgoCD),  
Linux distros (Ubuntu/Debian, RHEL/Fedora, Arch/AUR, NixOS, Gentoo, Alpine),  
Shells (Bash/Zsh/Fish/nushell), Build systems (Bazel/Buck2/Nix/Guix),  
Virtualization (QEMU/KVM/Firecracker), Observability (Prometheus/Grafana/OTel/eBPF)

---

## Architecture

```
User Input
    │
    ▼
 api/chat.py  ──►  CloneEngine (engine/core.py)
                        │
              ┌─────────┼──────────┐
              ▼         ▼          ▼
        memory.py  personality.py  responses.py
              │         │          │
              └─────────┴──────────┘
                        │
              ┌─────────▼──────────────────────────┐
              │         LLM Backends                │
              │  mock · openai · anthropic(Fable 5) │
              │  hermes(Ollama) · ollama · openrouter│
              └─────────────────────────────────────┘
                        │
                        ▼
                  Final Response
```

---

## License

GNU General Public License v3.0 — see [LICENSE](LICENSE).

---

*AI Clone Engine of Charles-Earl-Lipshay · lippytmai · v2.1 · © lippytm*
