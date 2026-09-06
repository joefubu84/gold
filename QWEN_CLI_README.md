# Qwen CLI

A terminal-native CLI to interact with Alibaba **Qwen** models — whether running locally via **Ollama / vLLM / LMStudio** or through cloud APIs like **Alibaba DashScope (Official)**, **SiliconFlow**, **OpenRouter**, or custom OpenAI-compatible endpoints.

---

## ⚡ Quick Start

### 1. Interactive Chat (REPL)
Launch the rich interactive session:
```bash
python qwen_cli.py
# Or on Windows:
.\qwen.cmd
```

Inside the interactive chat:
- `/help` — Show available commands
- `/model <name>` — Switch active model dynamically (e.g. `/model qwen-max` or `/model qwen2.5-coder-32b-instruct`)
- `/provider <name>` — Switch provider (`dashscope`, `ollama`, `siliconflow`, `openrouter`, `custom`)
- `/file <path>` — Attach and load file contents directly into the chat context
- `/history` — View conversation turns
- `/save [file.md]` — Export conversation to Markdown
- `/copy` — Copy the last response to clipboard
- `/clear` — Reset conversation history
- `/exit` — Exit the REPL

---

### 2. Configuration & Setup
Run the interactive setup wizard to configure your preferred default provider, API key, and model:
```bash
python qwen_cli.py config
# or
.\qwen.cmd config
```

Settings are persisted in `~/.qwen/config.json`.

Alternatively, set environment variables:
```powershell
$env:DASHSCOPE_API_KEY="sk-xxxxxxxxxxxxxxxx"
# or
$env:QWEN_API_KEY="sk-xxxxxxxxxxxxxxxx"
```

---

### 3. One-Shot & File Context
```bash
# Ask a direct question
.\qwen.cmd "How do I implement a WebSocket server in Python?"

# Analyze or refactor local files
.\qwen.cmd -f mt5_bridge.py "Review this code for error handling and performance"

# Attach multiple files
.\qwen.cmd -f file1.py -f file2.py "Compare these two implementations"
```

---

### 4. Piped Input (Stdin)
```bash
# Pipe git diff or files directly into Qwen
git diff | .\qwen.cmd "Write a concise commit message for these changes"

# Pipe logs
Get-Content error.log | .\qwen.cmd "Analyze what went wrong in this trace"
```

---

### 5. Local Ollama Usage
If you have Ollama running locally with Qwen models:
```bash
.\qwen.cmd -u http://localhost:11434/v1 -m qwen2.5:7b "Hello Qwen"
```

---

### 6. CLI Options Reference

| Flag | Description |
|------|-------------|
| `-m, --model` | Specify model (e.g., `qwen-plus`, `qwen-max`, `qwen2.5-coder-32b-instruct`, `qwen2.5:7b`) |
| `-k, --api-key` | Provide API key inline |
| `-u, --base-url` | Custom API base URL endpoint |
| `-s, --system` | Custom system prompt |
| `-f, --file` | Path to file(s) to attach into the prompt context |
| `-t, --temperature` | Sampling temperature (`0.0` to `1.0`) |
| `--max-tokens` | Max response tokens |
| `--no-stream` | Disable streaming output |
| `--config`, `config` | Run configuration wizard |
| `--models`, `models` | List available models from endpoint |
