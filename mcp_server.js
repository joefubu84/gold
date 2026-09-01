#!/usr/bin/env node

/**
 * ============================================================================
 * MacroQuant Gold Desk - Node.js stdio MCP Server (Compatible with npx)
 * ============================================================================
 * Author: MacroQuant Fintech & AI Engineering
 * Target: Qwen 3.8 Max / Claude / Cursor / Antigravity via `npx`
 * ============================================================================
 */

const fs = require('fs');
const path = require('path');
const https = require('https');
const readline = require('readline');

// File paths
const CONFIG_FILE = path.join(__dirname, 'gold_config.json');
const LIVE_FEED_FILE = path.join(__dirname, 'live_feed.json');
const CLOUDFLARE_URL = 'https://gold.cjhomebase.fun/api/live';

const DEFAULT_CONFIG = {
  version: "1.0.0",
  risk_management: {
    max_risk_per_trade_percent: 1.5,
    default_stop_loss_dollars: 10.0,
    contract_size_oz: 100.0,
    max_daily_drawdown_percent: 4.0
  },
  technical_parameters: {
    fast_ema_period: 8,
    slow_ema_period: 21,
    king_levels_lookback_bars: 50,
    timeframe: "M15"
  },
  affiliate_monetization: {
    preferred_broker: "Vantage",
    vantage_affiliate_url: "https://www.vantagemarkets.com/",
    exness_affiliate_url: "https://www.exness.com/",
    enable_cta_pulse_animations: true
  },
  trading_rules: {
    buy_dip_confluence: "H4/D1 == BULL and M15 == BEAR",
    short_breakdown_confluence: "M15 == BEAR and H1 == BEAR and H4 == BEAR",
    prohibit_trading_on_neutral: true
  }
};

function ensureConfig() {
  if (!fs.existsSync(CONFIG_FILE)) {
    fs.writeFileSync(CONFIG_FILE, JSON.stringify(DEFAULT_CONFIG, null, 2), 'utf-8');
  }
}

function readConfig() {
  ensureConfig();
  try {
    const raw = fs.readFileSync(CONFIG_FILE, 'utf-8');
    return JSON.parse(raw);
  } catch (err) {
    return { error: `Failed to read config: ${err.message}` };
  }
}

function updateConfig(newConfig) {
  ensureConfig();
  try {
    let current = readConfig();
    if (typeof newConfig === 'object' && newConfig !== null) {
      current = { ...current, ...newConfig };
      fs.writeFileSync(CONFIG_FILE, JSON.stringify(current, null, 2), 'utf-8');
      return { status: "success", updated_config: current };
    }
    return { error: "Payload must be a JSON object" };
  } catch (err) {
    return { error: `Failed to update config: ${err.message}` };
  }
}

function fetchLiveTelemetry() {
  return new Promise((resolve) => {
    https.get(CLOUDFLARE_URL, (res) => {
      let data = '';
      res.on('data', (chunk) => data += chunk);
      res.on('end', () => {
        try {
          resolve(JSON.parse(data));
        } catch (e) {
          resolve(readLocalTelemetry());
        }
      });
    }).on('error', () => {
      resolve(readLocalTelemetry());
    });
  });
}

function readLocalTelemetry() {
  if (fs.existsSync(LIVE_FEED_FILE)) {
    try {
      return JSON.parse(fs.readFileSync(LIVE_FEED_FILE, 'utf-8'));
    } catch (e) {}
  }
  return { status: "standby", message: "Telemetry feed connecting..." };
}

// ----------------------------------------------------------------------------
// MCP PROTOCOL RPC DEFINITION
// ----------------------------------------------------------------------------
const TOOLS = [
  {
    name: "get_gold_config",
    description: "Retrieve active JSON configuration (Risk limits, EMA periods, King lookback, Affiliate URLs) for the Gold Desk terminal.",
    inputSchema: {
      type: "object",
      properties: {},
      required: []
    }
  },
  {
    name: "update_gold_config",
    description: "Modify or inject new JSON trading parameters, risk settings, or affiliate links for the Gold Desk.",
    inputSchema: {
      type: "object",
      properties: {
        config: {
          type: "object",
          description: "JSON object containing updated settings."
        }
      },
      required: ["config"]
    }
  },
  {
    name: "get_gold_market_telemetry",
    description: "Get real-time Gold prices, synthetic DXY, Multi-Timeframe EMA confluence (M15, H1, H4, D1), and 50-bar King High/Low levels.",
    inputSchema: {
      type: "object",
      properties: {},
      required: []
    }
  }
];

async function handleRpc(req) {
  const { id, method, params } = req;

  if (method === "initialize") {
    return {
      jsonrpc: "2.0",
      id,
      result: {
        protocolVersion: "2024-11-05",
        capabilities: { tools: {} },
        serverInfo: { name: "macroquant-gold-mcp", version: "1.0.0" }
      }
    };
  }

  if (method === "tools/list") {
    return {
      jsonrpc: "2.0",
      id,
      result: { tools: TOOLS }
    };
  }

  if (method === "tools/call") {
    const { name, arguments: args } = params || {};

    if (name === "get_gold_config") {
      const cfg = readConfig();
      return {
        jsonrpc: "2.0",
        id,
        result: { content: [{ type: "text", text: JSON.stringify(cfg, null, 2) }] }
      };
    }

    if (name === "update_gold_config") {
      const res = updateConfig(args?.config || {});
      return {
        jsonrpc: "2.0",
        id,
        result: { content: [{ type: "text", text: JSON.stringify(res, null, 2) }] }
      };
    }

    if (name === "get_gold_market_telemetry") {
      const data = await fetchLiveTelemetry();
      return {
        jsonrpc: "2.0",
        id,
        result: { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] }
      };
    }

    return {
      jsonrpc: "2.0",
      id,
      error: { code: -32601, message: `Tool '${name}' not found` }
    };
  }

  if (method === "notifications/initialized") return null;

  return {
    jsonrpc: "2.0",
    id,
    error: { code: -32601, message: `Method '${method}' not found` }
  };
}

// Stdio JSON-RPC interface
const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout,
  terminal: false
});

rl.on('line', async (line) => {
  if (!line.trim()) return;
  try {
    const req = JSON.parse(line);
    const res = await handleRpc(req);
    if (res !== null) {
      console.log(JSON.stringify(res));
    }
  } catch (err) {
    console.log(JSON.stringify({
      jsonrpc: "2.0",
      id: null,
      error: { code: -32700, message: `Parse error: ${err.message}` }
    }));
  }
});
