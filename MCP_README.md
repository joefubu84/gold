# MacroQuant Gold Desk - Model Context Protocol (MCP) Server

This MCP server provides standard **JSON-RPC 2.0 stdio tools** for **Qwen 2.5 / 3.8 Max**, Claude, Cursor, Antigravity, or any LLM-enabled IDE to interact with the Gold Desk terminal.

---

## 🛠️ Available MCP Tools for Qwen

| Tool Name | Description |
| :--- | :--- |
| **`get_gold_config`** | Reads the active `gold_config.json` containing risk limits, EMA settings, affiliate URLs, and rules. |
| **`update_gold_config`** | Allows Qwen to dynamically update or inject new JSON trading parameters directly into `gold_config.json`. |
| **`get_gold_market_telemetry`** | Returns live market prices (Gold, DXY, EURUSD), Multi-Timeframe EMA confluence (M15, H1, H4, D1), and King structural levels. |

---

## 🔌 Connecting to Qwen / Claude Desktop / Antigravity / Cursor

Add this block to your **MCP client configuration file** (e.g. `claude_desktop_config.json` or Qwen Agent Settings):

```json
{
  "mcpServers": {
    "macroquant-gold": {
      "command": "python",
      "args": [
        "C:\\Users\\joefubu05\\Downloads\\gold\\mcp_server.py"
      ]
    }
  }
}
```

---

## 💡 Example Prompt for Qwen 3.8 Max

> *"Qwen, check the current Gold Desk configuration using `get_gold_config`. Then update the maximum risk per trade to 2.0% and set the fast EMA period to 9 using `update_gold_config`."*

Qwen will call the tool and instantly rewrite the configuration in real time!
