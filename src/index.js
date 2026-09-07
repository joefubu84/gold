/**
 * ============================================================================
 * MacroQuant Gold & DXY Institutional Desk - Cloudflare Worker Engine
 * ============================================================================
 * Architecture:
 *  - Serves zero-spam, institutional terminal frontend (HTML)
 *  - POST /api/update: Receives JSON ticks from MT5 bridge, validates x-bridge-token, caches to KV
 *  - GET /api/live: Serves JSON real-time telemetry to frontend with CORS enabled
 * ============================================================================
 */

import htmlContent from '../index.html';

// CORS response helper headers
const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, x-bridge-token',
  'Cache-Control': 'no-cache, no-store, must-revalidate, max-age=0'
};

// Fallback seed data in case KV is empty during initial cold-start
const DEFAULT_SEED_DATA = {
  timestamp: new Date().toUTCString(),
  gold: {
    symbol: "XAUUSD",
    bid: 4448.20,
    ask: 4448.45,
    spread: 0.25
  },
  currencies: {
    eurusd: 1.1582,
    usdjpy: 144.65,
    gbpusd: 1.2850,
    usdcad: 1.3650,
    usdchf: 0.8420
  },
  synthetic_dxy: 99.605,
  confluence: {
    M15: "BEAR",
    H1: "NEUT",
    H4: "BULL",
    D1: "BULL"
  },
  m15_indicators: {
    dxy: "UP (FLY)",
    eurusd: "DOWN (DROP)",
    usdjpy: "DOWN (YEN UP)",
    usdchf: "DOWN (CHF UP)"
  },
  daily_pivot: {
    pivot: 4445.50,
    r1: 4458.20,
    r2: 4468.50,
    r3: 4480.00,
    s1: 4432.80,
    s2: 4420.00,
    s3: 4408.50
  }
};

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // 1. Handle CORS Preflight OPTIONS requests
    if (request.method === 'OPTIONS') {
      return new Response(null, {
        status: 204,
        headers: corsHeaders
      });
    }

    // 2. ROUTE: POST /api/update (Ingestion from Python MT5 Bridge)
    if (url.pathname === '/api/update') {
      if (request.method !== 'POST') {
        return new Response(JSON.stringify({ error: 'Method Not Allowed' }), {
          status: 405,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        });
      }

      // Security check: validate x-bridge-token secret
      const clientToken = request.headers.get('x-bridge-token');
      const expectedToken = env.BRIDGE_TOKEN || 'macroquant_secret_token_2026_xyz';

      if (!clientToken || clientToken !== expectedToken) {
        return new Response(JSON.stringify({ error: 'Unauthorized: Invalid x-bridge-token' }), {
          status: 401,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        });
      }

      try {
        const payload = await request.json();
        
        // Validate core payload keys
        if (!payload || !payload.gold || typeof payload.gold.bid !== 'number') {
          return new Response(JSON.stringify({ error: 'Bad Request: Malformed payload' }), {
            status: 400,
            headers: { ...corsHeaders, 'Content-Type': 'application/json' }
          });
        }

        // Store payload in Cloudflare KV (key: "LATEST_DATA")
        if (env.MACRO_KV) {
          await env.MACRO_KV.put('LATEST_DATA', JSON.stringify(payload), {
            // Keep in KV with 1-day TTL expiration
            expirationTtl: 86400
          });
        }

        return new Response(JSON.stringify({ status: 'success', timestamp: payload.timestamp }), {
          status: 200,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        });
      } catch (err) {
        return new Response(JSON.stringify({ error: 'JSON Parse Error', details: err.message }), {
          status: 400,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        });
      }
    }

    // 3. ROUTE: GET /api/live (Frontend Telemetry Feed)
    if (url.pathname === '/api/live') {
      let liveData = null;

      if (env.MACRO_KV) {
        const stored = await env.MACRO_KV.get('LATEST_DATA');
        if (stored) {
          try {
            liveData = JSON.parse(stored);
          } catch (e) {
            liveData = null;
          }
        }
      }

      // Fallback to default seed if KV has not yet received a tick
      if (!liveData) {
        liveData = {
          ...DEFAULT_SEED_DATA,
          timestamp: new Date().toUTCString() + " (Seed)"
        };
      }

      return new Response(JSON.stringify(liveData), {
        status: 200,
        headers: {
          ...corsHeaders,
          'Content-Type': 'application/json'
        }
      });
    }

    // 4. ROUTE: GET / (Institutional Dashboard Frontend)
    // Strips away ad scripts, ensures instant non-cached delivery
    return new Response(htmlContent, {
      status: 200,
      headers: {
        'Content-Type': 'text/html;charset=UTF-8',
        'Cache-Control': 'no-cache, no-store, must-revalidate, max-age=0'
      }
    });
  }
};
