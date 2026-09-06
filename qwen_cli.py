#!/usr/bin/env python3
"""
Qwen CLI - A powerful, interactive command-line interface for Alibaba Qwen models.
Supports DashScope API, Ollama, SiliconFlow, OpenRouter, and any OpenAI-compatible endpoint.
"""

import os
import sys
import json
import argparse
import time
from pathlib import Path
from typing import List, Dict, Any, Generator, Optional

# Attempt rich imports for enhanced terminal UI
try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.prompt import Prompt, Confirm
    from rich.syntax import Syntax
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    import urllib.request
    import urllib.error
    REQUESTS_AVAILABLE = False


CONFIG_DIR = Path.home() / ".qwen"
CONFIG_FILE = CONFIG_DIR / "config.json"

PROVIDER_DEFAULTS = {
    "dashscope": {
        "name": "Alibaba DashScope (Official)",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
        "env_key": "DASHSCOPE_API_KEY",
        "popular_models": [
            "qwen-turbo",
            "qwen-plus",
            "qwen-max",
            "qwen-max-latest",
            "qwen2.5-72b-instruct",
            "qwen2.5-32b-instruct",
            "qwen2.5-14b-instruct",
            "qwen2.5-7b-instruct",
            "qwen2.5-coder-32b-instruct",
            "qwen2.5-coder-7b-instruct",
            "qwen-vl-plus",
            "qwen-vl-max"
        ]
    },
    "ollama": {
        "name": "Ollama (Local)",
        "base_url": "http://localhost:11434/v1",
        "default_model": "qwen2.5:7b",
        "env_key": None,
        "popular_models": [
            "qwen2.5:7b",
            "qwen2.5:14b",
            "qwen2.5:32b",
            "qwen2.5-coder:7b",
            "qwen2.5-coder:14b",
            "qwen2.5-coder:32b",
            "qwen2.5:0.5b",
            "qwen2.5:1.5b",
            "qwen2.5:3b"
        ]
    },
    "siliconflow": {
        "name": "SiliconFlow",
        "base_url": "https://api.siliconflow.cn/v1",
        "default_model": "Qwen/Qwen2.5-72B-Instruct",
        "env_key": "SILICONFLOW_API_KEY",
        "popular_models": [
            "Qwen/Qwen2.5-72B-Instruct",
            "Qwen/Qwen2.5-32B-Instruct",
            "Qwen/Qwen2.5-14B-Instruct",
            "Qwen/Qwen2.5-7B-Instruct",
            "Qwen/Qwen2.5-Coder-32B-Instruct",
            "Qwen/Qwen2.5-Coder-7B-Instruct"
        ]
    },
    "openrouter": {
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "qwen/qwen-2.5-72b-instruct",
        "env_key": "OPENROUTER_API_KEY",
        "popular_models": [
            "qwen/qwen-2.5-72b-instruct",
            "qwen/qwen-2.5-coder-32b-instruct",
            "qwen/qwen-2.5-7b-instruct",
            "qwen/qwen-turbo",
            "qwen/qwen-plus",
            "qwen/qwen-max"
        ]
    },
    "custom": {
        "name": "Custom OpenAI-Compatible API",
        "base_url": "http://localhost:8000/v1",
        "default_model": "qwen2.5",
        "env_key": "CUSTOM_API_KEY",
        "popular_models": []
    }
}


class QwenConfig:
    def __init__(self):
        self.provider = "dashscope"
        self.base_url = PROVIDER_DEFAULTS["dashscope"]["base_url"]
        self.model = PROVIDER_DEFAULTS["dashscope"]["default_model"]
        self.api_keys = {
            "dashscope": "",
            "siliconflow": "",
            "openrouter": "",
            "custom": ""
        }
        self.system_prompt = "You are Qwen, a helpful, intelligent, and precise AI assistant created by Alibaba Cloud."
        self.temperature = 0.7
        self.top_p = 0.8
        self.max_tokens = 4096
        self.load()

    def load(self):
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.provider = data.get("provider", self.provider)
                    self.base_url = data.get("base_url", PROVIDER_DEFAULTS.get(self.provider, {}).get("base_url", self.base_url))
                    self.model = data.get("model", self.model)
                    self.api_keys = data.get("api_keys", self.api_keys)
                    self.system_prompt = data.get("system_prompt", self.system_prompt)
                    self.temperature = data.get("temperature", self.temperature)
                    self.top_p = data.get("top_p", self.top_p)
                    self.max_tokens = data.get("max_tokens", self.max_tokens)
            except Exception as e:
                pass

    def save(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "provider": self.provider,
            "base_url": self.base_url,
            "model": self.model,
            "api_keys": self.api_keys,
            "system_prompt": self.system_prompt,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.max_tokens
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def get_api_key(self, provider: Optional[str] = None) -> str:
        p = provider or self.provider
        # Check environment variable first
        env_var = PROVIDER_DEFAULTS.get(p, {}).get("env_key")
        if env_var and os.environ.get(env_var):
            return os.environ[env_var]
        if os.environ.get("QWEN_API_KEY"):
            return os.environ["QWEN_API_KEY"]
        if os.environ.get("DASHSCOPE_API_KEY") and p == "dashscope":
            return os.environ["DASHSCOPE_API_KEY"]
        if os.environ.get("OPENAI_API_KEY"):
            return os.environ["OPENAI_API_KEY"]
        # Then check config file
        return self.api_keys.get(p, "")


class QwenClient:
    def __init__(self, config: QwenConfig, base_url: Optional[str] = None, api_key: Optional[str] = None, model: Optional[str] = None):
        self.config = config
        self.base_url = (base_url or config.base_url).rstrip("/")
        self.api_key = api_key if api_key is not None else config.get_api_key()
        self.model = model or config.model

    def stream_chat(self, messages: List[Dict[str, str]], temperature: Optional[float] = None, max_tokens: Optional[int] = None) -> Generator[str, None, None]:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "temperature": temperature if temperature is not None else self.config.temperature,
            "top_p": self.config.top_p,
            "max_tokens": max_tokens if max_tokens is not None else self.config.max_tokens
        }

        if REQUESTS_AVAILABLE:
            try:
                response = requests.post(url, json=payload, headers=headers, stream=True, timeout=60)
                if response.status_code != 200:
                    try:
                        err = response.json()
                        err_msg = err.get("error", {}).get("message") or str(err)
                    except Exception:
                        err_msg = response.text
                    raise RuntimeError(f"HTTP {response.status_code} Error: {err_msg}")

                for line in response.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue
            except requests.exceptions.ConnectionError as e:
                raise RuntimeError(f"Cannot connect to {self.base_url}. Please check if the server is running or if the URL is correct.\nDetails: {e}")
        else:
            # Fallback with urllib
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    for line_b in resp:
                        line = line_b.decode("utf-8").strip()
                        if line.startswith("data: "):
                            data_str = line[6:].strip()
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                delta = chunk.get("choices", [{}])[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                            except json.JSONDecodeError:
                                continue
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="ignore")
                raise RuntimeError(f"HTTP {e.code} Error: {err_body}")
            except urllib.error.URLError as e:
                raise RuntimeError(f"Connection failed: {e.reason}")

    def list_models(self) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/models"
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        if REQUESTS_AVAILABLE:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("data", [])
            else:
                raise RuntimeError(f"Failed to fetch models: HTTP {resp.status_code} {resp.text}")
        else:
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("data", [])


class QwenCLI:
    def __init__(self):
        self.config = QwenConfig()
        self.console = Console() if RICH_AVAILABLE else None

    def print_msg(self, text: str, style: str = ""):
        if self.console:
            self.console.print(text, style=style)
        else:
            print(text)

    def print_panel(self, text: str, title: str = "", border_style: str = "cyan"):
        if self.console:
            self.console.print(Panel(text, title=title, border_style=border_style))
        else:
            print(f"=== {title} ===\n{text}\n{'='*len(title)}")

    def run_setup(self):
        """Interactive setup wizard."""
        self.print_panel("Welcome to Qwen CLI Configuration Wizard", title="Setup", border_style="green")
        
        providers = list(PROVIDER_DEFAULTS.keys())
        self.print_msg("\n[bold]Select your preferred Qwen provider:[/bold]" if self.console else "\nSelect your provider:")
        for idx, p in enumerate(providers, 1):
            info = PROVIDER_DEFAULTS[p]
            current_marker = " (current)" if p == self.config.provider else ""
            self.print_msg(f"  [{idx}] {info['name']} ({p}){current_marker}")

        choice = input(f"\nSelect provider [1-{len(providers)}] (default current: {self.config.provider}): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(providers):
            self.config.provider = providers[int(choice) - 1]
            self.config.base_url = PROVIDER_DEFAULTS[self.config.provider]["base_url"]
            self.config.model = PROVIDER_DEFAULTS[self.config.provider]["default_model"]

        p_info = PROVIDER_DEFAULTS.get(self.config.provider, {})
        
        # Base URL
        url_input = input(f"Base URL [{self.config.base_url}]: ").strip()
        if url_input:
            self.config.base_url = url_input

        # API Key
        curr_key = self.config.api_keys.get(self.config.provider, "")
        key_display = f"{curr_key[:6]}...{curr_key[-4:]}" if len(curr_key) > 10 else (curr_key or "None")
        key_prompt = f"API Key for {self.config.provider} [{key_display}]: "
        key_input = input(key_prompt).strip()
        if key_input:
            self.config.api_keys[self.config.provider] = key_input

        # Model selection
        popular = p_info.get("popular_models", [])
        if popular:
            self.print_msg("\n[bold]Popular models for this provider:[/bold]" if self.console else "\nPopular models:")
            for m in popular:
                self.print_msg(f"  • {m}")
        
        model_input = input(f"\nDefault Model [{self.config.model}]: ").strip()
        if model_input:
            self.config.model = model_input

        # System prompt
        sys_input = input(f"System Prompt (leave blank to keep current):\n> ").strip()
        if sys_input:
            self.config.system_prompt = sys_input

        self.config.save()
        self.print_msg(f"\n[green]✓ Configuration saved to {CONFIG_FILE}[/green]" if self.console else f"\n✓ Configuration saved to {CONFIG_FILE}")

    def one_shot(self, prompt: str, args: argparse.Namespace):
        client = QwenClient(
            self.config,
            base_url=args.base_url,
            api_key=args.api_key,
            model=args.model
        )

        # Build context from files if provided
        file_contexts = []
        if args.file:
            for fpath in args.file:
                p = Path(fpath)
                if p.exists() and p.is_file():
                    try:
                        content = p.read_text(encoding="utf-8", errors="replace")
                        file_contexts.append(f"--- File: {p.name} ---\n```{p.suffix.lstrip('.')}\n{content}\n```")
                    except Exception as e:
                        print(f"Warning: Could not read file {fpath}: {e}", file=sys.stderr)
                else:
                    print(f"Warning: File {fpath} not found.", file=sys.stderr)

        # Check piped stdin
        stdin_content = ""
        if not sys.stdin.isatty():
            try:
                stdin_content = sys.stdin.read().strip()
            except Exception:
                pass

        user_content_parts = []
        if file_contexts:
            user_content_parts.extend(file_contexts)
        if stdin_content:
            user_content_parts.append(f"--- Piped Input ---\n{stdin_content}")
        if prompt:
            user_content_parts.append(prompt)

        full_user_content = "\n\n".join(user_content_parts)

        messages = [
            {"role": "system", "content": args.system or self.config.system_prompt},
            {"role": "user", "content": full_user_content}
        ]

        if args.no_stream:
            # Non-streaming mode
            chunks = []
            try:
                for chunk in client.stream_chat(messages, temperature=args.temperature, max_tokens=args.max_tokens):
                    chunks.append(chunk)
                full_resp = "".join(chunks)
                if self.console and sys.stdout.isatty():
                    self.console.print(Markdown(full_resp))
                else:
                    print(full_resp)
            except Exception as e:
                print(f"Error: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            # Streaming mode
            try:
                if self.console and sys.stdout.isatty():
                    # Stream raw text directly for responsiveness
                    full_resp = ""
                    for chunk in client.stream_chat(messages, temperature=args.temperature, max_tokens=args.max_tokens):
                        sys.stdout.write(chunk)
                        sys.stdout.flush()
                        full_resp += chunk
                    print()  # Newline at end
                else:
                    for chunk in client.stream_chat(messages, temperature=args.temperature, max_tokens=args.max_tokens):
                        sys.stdout.write(chunk)
                        sys.stdout.flush()
                    print()
            except Exception as e:
                print(f"\nError: {e}", file=sys.stderr)
                sys.exit(1)

    def interactive_chat(self, args: argparse.Namespace):
        client = QwenClient(
            self.config,
            base_url=args.base_url,
            api_key=args.api_key,
            model=args.model
        )

        banner = (
            f"[bold cyan]Qwen CLI - Interactive Assistant[/bold cyan]\n"
            f"[dim]Provider:[/dim] [green]{self.config.provider}[/green] | "
            f"[dim]Model:[/dim] [yellow]{client.model}[/yellow] | "
            f"[dim]Endpoint:[/dim] {client.base_url}\n"
            f"[dim]Type [bold]/help[/bold] for commands, [bold]/exit[/bold] or [bold]Ctrl+C[/bold] to quit.[/dim]"
        ) if self.console else (
            f"=== Qwen CLI - Interactive Assistant ===\n"
            f"Provider: {self.config.provider} | Model: {client.model}\n"
            f"Type /help for commands, /exit to quit.\n"
        )

        if self.console:
            self.console.print(Panel(banner, border_style="cyan"))
        else:
            print(banner)

        history: List[Dict[str, str]] = [
            {"role": "system", "content": args.system or self.config.system_prompt}
        ]

        last_assistant_response = ""

        while True:
            try:
                if self.console:
                    prompt_str = "\n[bold green]You[/bold green] [dim]>[/dim] "
                    user_input = self.console.input(prompt_str).strip()
                else:
                    user_input = input("\nYou > ").strip()
            except (KeyboardInterrupt, EOFError):
                self.print_msg("\n[yellow]Goodbye![/yellow]" if self.console else "\nGoodbye!")
                break

            if not user_input:
                continue

            # Command Handling
            if user_input.startswith("/"):
                cmd_parts = user_input.split(maxsplit=1)
                cmd = cmd_parts[0].lower()
                arg = cmd_parts[1].strip() if len(cmd_parts) > 1 else ""

                if cmd in ["/exit", "/quit", "/q"]:
                    self.print_msg("[yellow]Goodbye![/yellow]" if self.console else "Goodbye!")
                    break

                elif cmd in ["/help", "/h", "/?"]:
                    help_text = (
                        "Commands:\n"
                        "  /help                 Show this help message\n"
                        "  /clear, /reset        Reset current conversation history\n"
                        "  /model [name]         View or change active model\n"
                        "  /provider [name]      Switch provider (dashscope, ollama, siliconflow, openrouter, custom)\n"
                        "  /system [prompt]      View or update system prompt\n"
                        "  /file <path>          Load file contents into conversation\n"
                        "  /history              Display conversation turns\n"
                        "  /save [path]          Save conversation to markdown file\n"
                        "  /copy                 Copy last response to clipboard\n"
                        "  /config               Run interactive setup\n"
                        "  /exit, /quit          Exit the chat session"
                    )
                    self.print_panel(help_text, title="Help & Commands", border_style="blue")
                    continue

                elif cmd in ["/clear", "/reset"]:
                    history = [{"role": "system", "content": args.system or self.config.system_prompt}]
                    self.print_msg("[green]✓ Chat history cleared.[/green]" if self.console else "✓ Chat history cleared.")
                    continue

                elif cmd == "/model":
                    if arg:
                        client.model = arg
                        self.print_msg(f"[green]✓ Switched model to:[/green] [yellow]{arg}[/yellow]" if self.console else f"✓ Switched model to: {arg}")
                    else:
                        self.print_msg(f"Current model: [yellow]{client.model}[/yellow]" if self.console else f"Current model: {client.model}")
                    continue

                elif cmd == "/provider":
                    if arg in PROVIDER_DEFAULTS:
                        self.config.provider = arg
                        self.config.base_url = PROVIDER_DEFAULTS[arg]["base_url"]
                        self.config.model = PROVIDER_DEFAULTS[arg]["default_model"]
                        client = QwenClient(self.config)
                        self.print_msg(f"[green]✓ Switched provider to {arg} ({client.base_url}) - model: {client.model}[/green]" if self.console else f"✓ Switched provider to {arg}")
                    else:
                        self.print_msg(f"[red]Unknown provider '{arg}'. Options: {', '.join(PROVIDER_DEFAULTS.keys())}[/red]" if self.console else f"Unknown provider. Options: {', '.join(PROVIDER_DEFAULTS.keys())}")
                    continue

                elif cmd == "/system":
                    if arg:
                        self.config.system_prompt = arg
                        if history and history[0]["role"] == "system":
                            history[0]["content"] = arg
                        else:
                            history.insert(0, {"role": "system", "content": arg})
                        self.print_msg("[green]✓ System prompt updated.[/green]" if self.console else "✓ System prompt updated.")
                    else:
                        sys_prompt = history[0]["content"] if history and history[0]["role"] == "system" else "None"
                        self.print_panel(sys_prompt, title="Current System Prompt", border_style="magenta")
                    continue

                elif cmd == "/file":
                    if not arg:
                        self.print_msg("[yellow]Usage: /file <path_to_file>[/yellow]" if self.console else "Usage: /file <path_to_file>")
                        continue
                    p = Path(arg)
                    if not p.exists() or not p.is_file():
                        self.print_msg(f"[red]File not found: {arg}[/red]" if self.console else f"File not found: {arg}")
                        continue
                    try:
                        fcontent = p.read_text(encoding="utf-8", errors="replace")
                        injected = f"--- Attached File: {p.name} ---\n```{p.suffix.lstrip('.')}\n{fcontent}\n```"
                        history.append({"role": "user", "content": injected})
                        history.append({"role": "assistant", "content": f"I have received and loaded `{p.name}` ({len(fcontent)} characters). How would you like to proceed with this file?"})
                        self.print_msg(f"[green]✓ Attached `{p.name}` ({len(fcontent)} chars) into conversation.[/green]" if self.console else f"✓ Attached {p.name} ({len(fcontent)} chars).")
                    except Exception as e:
                        self.print_msg(f"[red]Error reading file: {e}[/red]" if self.console else f"Error reading file: {e}")
                    continue

                elif cmd == "/history":
                    if self.console:
                        table = Table(title="Conversation History", border_style="dim")
                        table.add_column("#", style="dim", width=4)
                        table.add_column("Role", style="bold", width=12)
                        table.add_column("Snippet", style="white")
                        for idx, h in enumerate(history):
                            snippet = h["content"][:80].replace("\n", " ") + ("..." if len(h["content"]) > 80 else "")
                            role_color = "magenta" if h["role"] == "system" else ("green" if h["role"] == "user" else "cyan")
                            table.add_row(str(idx), f"[{role_color}]{h['role']}[/{role_color}]", snippet)
                        self.console.print(table)
                    else:
                        for idx, h in enumerate(history):
                            print(f"[{idx}] {h['role'].upper()}: {h['content'][:80]}...")
                    continue

                elif cmd == "/save":
                    out_path = Path(arg) if arg else Path(f"qwen_chat_{int(time.time())}.md")
                    try:
                        md_lines = ["# Qwen Chat Session", f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}", f"Model: {client.model}", ""]
                        for h in history:
                            if h["role"] == "system":
                                md_lines.append(f"**System**: {h['content']}\n")
                            elif h["role"] == "user":
                                md_lines.append(f"### User:\n{h['content']}\n")
                            elif h["role"] == "assistant":
                                md_lines.append(f"### Qwen:\n{h['content']}\n")
                        out_path.write_text("\n".join(md_lines), encoding="utf-8")
                        self.print_msg(f"[green]✓ Chat session exported to {out_path.resolve()}[/green]" if self.console else f"✓ Exported to {out_path.resolve()}")
                    except Exception as e:
                        self.print_msg(f"[red]Failed to save session: {e}[/red]" if self.console else f"Failed to save: {e}")
                    continue

                elif cmd == "/copy":
                    if not last_assistant_response:
                        self.print_msg("[yellow]No recent response to copy.[/yellow]" if self.console else "No recent response to copy.")
                        continue
                    try:
                        # Windows / cross platform clipboard copy
                        import subprocess
                        if sys.platform == "win32":
                            process = subprocess.Popen("clip", stdin=subprocess.PIPE, shell=True)
                            process.communicate(last_assistant_response.encode("utf-8"))
                        elif sys.platform == "darwin":
                            process = subprocess.Popen("pbcopy", stdin=subprocess.PIPE)
                            process.communicate(last_assistant_response.encode("utf-8"))
                        else:
                            process = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE)
                            process.communicate(last_assistant_response.encode("utf-8"))
                        self.print_msg("[green]✓ Copied last response to clipboard.[/green]" if self.console else "✓ Copied to clipboard.")
                    except Exception as e:
                        self.print_msg(f"[red]Could not access clipboard: {e}[/red]" if self.console else f"Clipboard error: {e}")
                    continue

                elif cmd == "/config":
                    self.run_setup()
                    client = QwenClient(self.config)
                    continue

                else:
                    self.print_msg(f"[yellow]Unknown command '{cmd}'. Type /help for available commands.[/yellow]" if self.console else f"Unknown command '{cmd}'. Type /help")
                    continue

            # Standard chat interaction
            history.append({"role": "user", "content": user_input})
            if self.console:
                self.console.print("[bold cyan]Qwen[/bold cyan] [dim]>[/dim] ", end="")
            else:
                print("Qwen > ", end="")

            response_accum = []
            try:
                for chunk in client.stream_chat(history):
                    sys.stdout.write(chunk)
                    sys.stdout.flush()
                    response_accum.append(chunk)
                print()  # newline
                last_assistant_response = "".join(response_accum)
                history.append({"role": "assistant", "content": last_assistant_response})
            except Exception as e:
                self.print_msg(f"\n[bold red]Error:[/bold red] {e}" if self.console else f"\nError: {e}")
                # Remove last user prompt if request failed completely
                if not response_accum and history and history[-1]["role"] == "user":
                    history.pop()

    def list_models_cmd(self, args: argparse.Namespace):
        client = QwenClient(self.config, base_url=args.base_url, api_key=args.api_key)
        self.print_msg(f"Fetching models from [cyan]{client.base_url}[/cyan]..." if self.console else f"Fetching models from {client.base_url}...")
        try:
            models = client.list_models()
            if self.console:
                table = Table(title=f"Models available at {client.base_url}", border_style="cyan")
                table.add_column("ID", style="bold yellow")
                table.add_column("Owned By", style="dim")
                for m in models:
                    m_id = m.get("id") or m.get("name", "unknown")
                    owned = m.get("owned_by", "")
                    table.add_row(m_id, owned)
                self.console.print(table)
            else:
                for m in models:
                    m_id = m.get("id") or m.get("name", "unknown")
                    print(f"- {m_id}")
        except Exception as e:
            self.print_msg(f"[red]Error listing models: {e}[/red]" if self.console else f"Error: {e}")
            # Show fallback popular models
            p_info = PROVIDER_DEFAULTS.get(self.config.provider, {})
            popular = p_info.get("popular_models", [])
            if popular:
                self.print_msg(f"\n[dim]Known popular models for provider '{self.config.provider}':[/dim]" if self.console else f"\nKnown models for {self.config.provider}:")
                for m in popular:
                    self.print_msg(f"  • {m}")


def main():
    parser = argparse.ArgumentParser(
        prog="qwen",
        description="Qwen CLI - Interact with Alibaba Qwen AI models (DashScope, Ollama, SiliconFlow, OpenRouter, etc.)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  qwen                             # Start interactive chat REPL
  qwen "Write a Python script"     # One-shot question
  qwen -f main.py "Code review"    # Pass file context
  cat data.csv | qwen "Analyze"    # Pipe input from stdin
  qwen config                      # Interactive configuration wizard
  qwen models                      # List models on provider
  qwen -m qwen-max "Hello"         # Specify model directly
  qwen -u http://localhost:11434/v1 -m qwen2.5:7b  # Connect to local Ollama
        """
    )

    parser.add_argument("prompt", nargs="*", default=[], help="Prompt text for one-shot execution")
    parser.add_argument("-m", "--model", help="Specify Qwen model name (e.g. qwen-plus, qwen-turbo, qwen-max, qwen2.5:7b)")
    parser.add_argument("-k", "--api-key", help="API key for provider (or set DASHSCOPE_API_KEY/QWEN_API_KEY env)")
    parser.add_argument("-u", "--base-url", help="API base URL (default: DashScope or provider endpoint)")
    parser.add_argument("-s", "--system", help="Custom system prompt")
    parser.add_argument("-f", "--file", action="append", help="Attach one or more files as context")
    parser.add_argument("-t", "--temperature", type=float, help="Sampling temperature (0.0 to 1.0)")
    parser.add_argument("--max-tokens", type=int, help="Max tokens in response")
    parser.add_argument("--no-stream", action="store_true", help="Disable streaming output")
    parser.add_argument("--setup", "--config", action="store_true", help="Launch interactive configuration wizard")
    parser.add_argument("--models", "-l", action="store_true", help="List available models from provider")

    args = parser.parse_args()

    cli = QwenCLI()

    # Handle sub-actions
    if args.setup:
        cli.run_setup()
        return

    if args.models:
        cli.list_models_cmd(args)
        return

    # Check prompt vs positional command
    prompt_str = " ".join(args.prompt).strip()

    if prompt_str.lower() in ["config", "setup", "init"]:
        cli.run_setup()
        return
    elif prompt_str.lower() in ["models", "list"]:
        cli.list_models_cmd(args)
        return

    # If prompt or piped stdin or files provided -> one-shot mode
    has_piped_stdin = not sys.stdin.isatty()
    if prompt_str or has_piped_stdin or args.file:
        cli.one_shot(prompt_str, args)
    else:
        # Interactive mode
        cli.interactive_chat(args)


if __name__ == "__main__":
    main()
