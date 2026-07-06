# AI Clone Engine of Charles-Earl-Lipshay · lippytm · lippytmai

> **Version 2.0 — Engine Edition**
> Upgraded from AI Clone → AI Clone Engine

---

## Overview

The **AI Clone Engine of Charles-Earl-Lipshay** (`lippytmai`) is a modular, extensible AI personality engine that simulates the thoughts, communication style, knowledge base, and responses of **Charles Earl Lipshay** ([@lippytm](https://github.com/lippytm)).

Unlike a static "AI Clone," the **Engine** provides:

| Feature | AI Clone (v1) | AI Clone Engine (v2) |
|---|---|---|
| Static responses | ✅ | ✅ |
| Dynamic conversation memory | ❌ | ✅ |
| Personality profile config | ❌ | ✅ |
| Pluggable LLM backends | ❌ | ✅ |
| REST / CLI API | ❌ | ✅ |
| Session context | ❌ | ✅ |
| Knowledge base injection | ❌ | ✅ |

---

## Project Structure

```
AI-Clone-Engine-lippytmai/
├── engine/
│   ├── __init__.py          # Engine package
│   ├── core.py              # CloneEngine — main orchestrator
│   ├── personality.py       # Personality traits & style rules
│   ├── memory.py            # Conversation & long-term memory
│   └── responses.py         # Response generation & formatting
├── config/
│   ├── engine_config.json   # Engine runtime settings
│   └── personality_profile.json  # Charles Earl Lipshay personality data
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

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the interactive chat

```bash
python main.py
```

### 3. Use programmatically

```python
from engine.core import CloneEngine

engine = CloneEngine()
response = engine.chat("What do you think about AI?")
print(response)
```

### 4. CLI flags

```bash
python main.py --session my_session   # Named session (persistent memory)
python main.py --reset                # Clear all session memory
python main.py --profile              # Print current personality profile
```

---

## Configuration

Edit `config/engine_config.json` to tune the engine:

```json
{
  "backend": "openai",          // "openai" | "ollama" | "mock"
  "model": "gpt-4o",
  "temperature": 0.85,
  "max_tokens": 512,
  "memory_window": 20,
  "session_persist": true
}
```

Edit `config/personality_profile.json` to update the personality model.

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
                        ▼
               LLM Backend (OpenAI / Ollama / Mock)
                        │
                        ▼
                  Final Response
```

---

## License

GNU General Public License v3.0 — see [LICENSE](LICENSE).

---

*AI Clone Engine of Charles-Earl-Lipshay · lippytmai · © lippytm*