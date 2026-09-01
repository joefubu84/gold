"""
================================================================================
MacroQuant Gold Desk - Model Context Protocol (MCP) Server
================================================================================
Author: MacroQuant Fintech & AI Engineering
Target AI: Qwen 2.5 / 3.8 Max, Claude, GPT, Antigravity
Description:
    Standard stdio Model Context Protocol (MCP) Server enabling Qwen to:
    1. Read real-time Gold, DXY, and MT5 multi-timeframe confluence telemetry.
    2. Dynamically update & write JSON trading configurations, risk limits,
       affiliate URLs, King level thresholds, and EMA settings for the dashboard.
================================================================================
"""

import sys
import json
import os
import requests

# ------------------------------------------------------------------------------
# CONFIGURATION & FILE PATHS
# ------------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE_PATH = os.path.join(BASE_DIR, "gold_config.json")
LIVE_FEED_FILE_PATH = os.path.join(BASE_DIR, "live_feed.json")
CLOUDFLARE_LIVE_URL = "https://gold.cjhomebase.fun/api/live"

DEFAULT_CONFIG = {
    "version": "1.0.0",
    "risk_management": {
        "max_risk_per_trade_percent": 1.5,
        "default_stop_loss_dollars": 10.0,
        "contract_size_oz": 100.0,
        "max_daily_drawdown_percent": 4.0
    },
    "technical_parameters": {
        "fast_ema_period": 8,
        "slow_ema_period": 21,
        "king_levels_lookback_bars": 50,
        "timeframe": "M15"
    },
    "affiliate_monetization": {
        "preferred_broker": "Vantage",
        "vantage_affiliate_url": "https://www.vantagemarkets.com/",
        "exness_affiliate_url": "https://www.exness.com/",
        "enable_cta_pulse_animations": True
    },
    "trading_rules": {
        "buy_dip_confluence": "H4/D1 == BULL and M15 == BEAR",
        "short_breakdown_confluence": "M15 == BEAR and H1 == BEAR and H4 == BEAR",
        "prohibit_trading_on_neutral": True
    }
}

def ensure_config_file():
    """Initializes the gold_config.json file if it does not exist."""
    if not os.path.exists(CONFIG_FILE_PATH):
        with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)

def read_config():
    """Reads the current gold_config.json configuration."""
    ensure_config_file()
    try:
        with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {"error": f"Failed to read configuration: {str(e)}"}

def update_config(new_config_dict):
    """Deep merges or replaces configuration keys in gold_config.json."""
    ensure_config_file()
    try:
        current = read_config()
        if isinstance(new_config_dict, dict):
            current.update(new_config_dict)
            with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(current, f, indent=2)
            return {"status": "success", "updated_config": current}
        else:
            return {"error": "Invalid payload. Must be a JSON object."}
    except Exception as e:
        return {"error": f"Failed to update configuration: {str(e)}"}

def get_live_market_telemetry():
    """Fetches live Gold, DXY, and Confluence data from Cloudflare Worker or local cache."""
    try:
        resp = requests.get(CLOUDFLARE_LIVE_URL, timeout=2.0)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass

    # Fallback to local live_feed.json
    if os.path.exists(LIVE_FEED_FILE_PATH):
        try:
            with open(LIVE_FEED_FILE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    return {"status": "standby", "message": "Telemetry bridge initializing..."}

# ------------------------------------------------------------------------------
# MCP PROTOCOL RPC HANDLER (JSON-RPC 2.0 OVER STDIO)
# ------------------------------------------------------------------------------
TOOLS = [
    {
        "name": "get_gold_config",
        "description": "Retrieve the current JSON configuration parameters for the MacroQuant Gold Desk (Risk limits, EMA periods, King lookback, Affiliate URLs).",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "update_gold_config",
        "description": "Update and modify the JSON trading settings, risk thresholds, EMA periods, or affiliate parameters for the Gold Desk.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "config": {
                    "type": "object",
                    "description": "JSON object containing updated settings (e.g. risk_management, technical_parameters, affiliate_monetization, trading_rules)."
                }
            },
            "required": ["config"]
        }
    },
    {
        "name": "get_gold_market_telemetry",
        "description": "Retrieve real-time live Gold price ticks, synthetic DXY index value, Multi-Timeframe EMA confluence (M15, H1, H4, D1), and 50-bar King structural levels.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
]

def handle_rpc_request(req):
    req_id = req.get("id")
    method = req.get("method")
    params = req.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "macroquant-gold-mcp",
                    "version": "1.0.0"
                }
            }
        }

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": TOOLS
            }
        }

    elif method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})

        if tool_name == "get_gold_config":
            result_data = read_config()
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result_data, indent=2)}]
                }
            }

        elif tool_name == "update_gold_config":
            new_conf = args.get("config", {})
            result_data = update_config(new_conf)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result_data, indent=2)}]
                }
            }

        elif tool_name == "get_gold_market_telemetry":
            telemetry = get_live_market_telemetry()
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(telemetry, indent=2)}]
                }
            }

        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Tool '{tool_name}' not found."}
            }

    elif method == "notifications/initialized":
        return None

    else:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method '{method}' not found."}
        }

def main():
    ensure_config_file()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            res = handle_rpc_request(req)
            if res is not None:
                sys.stdout.write(json.dumps(res) + "\n")
                sys.stdout.flush()
        except Exception as e:
            err_res = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {str(e)}"}
            }
            sys.stdout.write(json.dumps(err_res) + "\n")
            sys.stdout.flush()

if __name__ == "__main__":
    main()
