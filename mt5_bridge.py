"""
================================================================================
MacroQuant MT5 Bridge -> Cloudflare Worker Pipeline (With King Levels & M15 Candlesticks)
================================================================================
Author: MacroQuant Fintech Engineering
Description:
    1. Extracts live XAUUSD (Gold), EURUSD, USDJPY, GBPUSD, and USDCAD ticks from MT5.
    2. Calculates official synthetic DXY (US Dollar Index) with robust fallbacks.
    3. Fetches the last 100 M15 candles, calculates EMA 8 and EMA 21 arrays, and
       extracts the 50-bar "King" High/Low structural levels.
    4. Securely pushes payloads to Cloudflare Worker (/api/update) via x-bridge-token.
================================================================================
"""

import time
import math
import json
import requests
import MetaTrader5 as mt5

# ------------------------------------------------------------------------------
# CONFIGURATION & CLOUDFLARE WORKER ENDPOINT
# ------------------------------------------------------------------------------
# Official USD Index (DXY) Geometric Formula Weights (Federal Reserve Standard):
# DXY = 50.14348112 * (EURUSD^-0.576) * (USDJPY^0.136) * (GBPUSD^-0.119) * (USDCAD^0.091) * (USDSEK^0.042) * (USDCHF^0.036)

CLOUDFLARE_WORKER_URL = "https://gold.cjhomebase.fun/api/update"
BRIDGE_AUTH_TOKEN = "macroquant_secret_token_2026_xyz"  # Must match Worker env secret
DXY_CONSTANT = 50.14348112

def calculate_synthetic_dxy(eurusd_rate, usdjpy_rate=145.50, gbpusd_rate=1.2850, usdcad_rate=1.3650, usdsek_rate=10.45, usdchf_rate=0.8420):
    """
    Computes real-time Synthetic DXY using Federal Reserve geometric weights.
    Safely calculates with fallback defaults if auxiliary feeds disconnect.
    """
    try:
        if not eurusd_rate or eurusd_rate <= 0:
            return None

        dxy = (
            DXY_CONSTANT
            * math.pow(eurusd_rate, -0.576)
            * math.pow(usdjpy_rate, 0.136)
            * math.pow(gbpusd_rate, -0.119)
            * math.pow(usdcad_rate, 0.091)
            * math.pow(usdsek_rate, 0.042)
            * math.pow(usdchf_rate, 0.036)
        )
        return round(dxy, 3)
    except Exception as exc:
        print(f"[!] Warning: Synthetic DXY math error: {exc}")
        return None

def compute_ema_series(prices, period):
    """Calculates a full EMA series array from an ordered price array."""
    if not prices or len(prices) == 0:
        return []
    
    k = 2.0 / (period + 1.0)
    ema_series = []
    ema = float(prices[0])
    for p in prices:
        ema = (float(p) * k) + (ema * (1.0 - k))
        ema_series.append(round(ema, 2))
    return ema_series

def get_timeframe_status(symbol, timeframe_label, mt5_tf):
    """
    Evaluates Multi-Timeframe EMA 8 / 21 Confluence:
    - BULL: Price > EMA 8 AND EMA 8 > EMA 21
    - BEAR: Price < EMA 8 AND EMA 8 < EMA 21
    - NEUT: Consolidation / Between EMAs
    """
    try:
        rates = mt5.copy_rates_from_pos(symbol, mt5_tf, 0, 50)
        if rates is None or len(rates) < 25:
            return "NEUT"
        
        closes = [float(r['close']) for r in rates]
        ema8_list = compute_ema_series(closes, 8)
        ema21_list = compute_ema_series(closes, 21)
        current_price = closes[-1]
        last_ema8 = ema8_list[-1]
        last_ema21 = ema21_list[-1]

        if current_price > last_ema8 and last_ema8 > last_ema21:
            return "BULL"
        elif current_price < last_ema8 and last_ema8 < last_ema21:
            return "BEAR"
        else:
            return "NEUT"
    except Exception as exc:
        print(f"[!] Error reading TF {timeframe_label} for {symbol}: {exc}")
        return "NEUT"

def fetch_m15_chart_payload(symbol):
    """
    Fetches the last 100 M15 candles from MT5, calculates EMA 8 and EMA 21 arrays,
    and extracts the 50-bar King High and Low structural levels.
    """
    try:
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 100)
        if rates is None or len(rates) == 0:
            return None, None, None, None

        candles = []
        closes = []
        for r in rates:
            c_time = int(r['time'])
            c_open = round(float(r['open']), 2)
            c_high = round(float(r['high']), 2)
            c_low = round(float(r['low']), 2)
            c_close = round(float(r['close']), 2)
            candles.append({
                "time": c_time,
                "open": c_open,
                "high": c_high,
                "low": c_low,
                "close": c_close
            })
            closes.append(c_close)

        # Compute full EMA arrays matched to timestamps
        ema8_raw = compute_ema_series(closes, 8)
        ema21_raw = compute_ema_series(closes, 21)

        ema8_series = [{"time": candles[i]["time"], "value": ema8_raw[i]} for i in range(len(candles))]
        ema21_series = [{"time": candles[i]["time"], "value": ema21_raw[i]} for i in range(len(candles))]

        # Calculate 50-bar "King" Structural High & Low
        last_50_candles = candles[-50:] if len(candles) >= 50 else candles
        king_high = max(c["high"] for c in last_50_candles)
        king_low  = min(c["low"] for c in last_50_candles)

        king_levels = {
            "high": round(king_high, 2),
            "low": round(king_low, 2),
            "label_high": "FA M15 KING HIGH",
            "label_low": "FA M15 KING LOW"
        }

        return candles, ema8_series, ema21_series, king_levels

    except Exception as exc:
        print(f"[!] Error building M15 chart payload: {exc}")
        return None, None, None, None

def fetch_tick_price(symbol, fallback_price):
    """Safely retrieves latest bid from MT5 or uses fallback."""
    try:
        tick = mt5.symbol_info_tick(symbol)
        if tick and tick.bid > 0:
            return round(float(tick.bid), 4)
    except Exception:
        pass
    return fallback_price

def post_payload_to_cloudflare(payload):
    """Pushes the real-time calculated payload to the Cloudflare Worker."""
    headers = {
        "Content-Type": "application/json",
        "x-bridge-token": BRIDGE_AUTH_TOKEN
    }
    try:
        resp = requests.post(CLOUDFLARE_WORKER_URL, json=payload, headers=headers, timeout=2.5)
        return resp.status_code == 200
    except requests.exceptions.RequestException as req_err:
        print(f"[!] Network error pushing to Cloudflare Worker: {req_err}")
        return False

def init_bridge():
    print("==========================================================")
    print("  MACROQUANT DESK -> MT5 TO CLOUDFLARE BRIDGE INITIATING ")
    print("==========================================================")

    if not mt5.initialize():
        print(f"[!] MT5 initialize() failed, error code: {mt5.last_error()}")
        print("[!] Ensure MetaTrader 5 desktop terminal is running.")
        return

    print(f"[✓] Connected to MT5 Build: {mt5.version()}")
    account_info = mt5.account_info()
    if account_info:
        print(f"[✓] Account: #{account_info.login} | Server: {account_info.server} | Balance: ${account_info.balance:,.2f}")

    all_symbols = [s.name for s in mt5.symbols_get()] if mt5.symbols_get() else []
    
    def find_symbol(base_name, candidates):
        for s in all_symbols:
            for cand in candidates:
                if cand.lower() in s.lower():
                    return s
        return base_name

    gold_symbol = find_symbol("XAUUSD", ["XAUUSD", "GOLD"])
    eur_symbol  = find_symbol("EURUSD", ["EURUSD"])
    jpy_symbol  = find_symbol("USDJPY", ["USDJPY"])
    gbp_symbol  = find_symbol("GBPUSD", ["GBPUSD"])
    cad_symbol  = find_symbol("USDCAD", ["USDCAD"])
    chf_symbol  = find_symbol("USDCHF", ["USDCHF"])

    print(f"[✓] Active Gold Symbol  : {gold_symbol}")
    print(f"[✓] Active Euro Symbol  : {eur_symbol}")
    print(f"[✓] Target Worker URL   : {CLOUDFLARE_WORKER_URL}")
    print("----------------------------------------------------------")

    try:
        while True:
            gold_tick = mt5.symbol_info_tick(gold_symbol)
            eur_bid = fetch_tick_price(eur_symbol, 1.1582)
            jpy_bid = fetch_tick_price(jpy_symbol, 144.65)
            gbp_bid = fetch_tick_price(gbp_symbol, 1.2850)
            cad_bid = fetch_tick_price(cad_symbol, 1.3650)
            chf_bid = fetch_tick_price(chf_symbol, 0.8420)

            if gold_tick and gold_tick.bid > 0:
                gold_bid = round(float(gold_tick.bid), 2)
                gold_ask = round(float(gold_tick.ask), 2)
                gold_spread = round((gold_ask - gold_bid), 2)

                # 1. Compute Official Synthetic DXY
                dxy_val = calculate_synthetic_dxy(
                    eurusd_rate=eur_bid,
                    usdjpy_rate=jpy_bid,
                    gbpusd_rate=gbp_bid,
                    usdcad_rate=cad_bid,
                    usdchf_rate=chf_bid
                )

                # 2. Multi-Timeframe EMA Confluence
                m15_status = get_timeframe_status(gold_symbol, "M15", mt5.TIMEFRAME_M15)
                h1_status  = get_timeframe_status(gold_symbol, "H1", mt5.TIMEFRAME_H1)
                h4_status  = get_timeframe_status(gold_symbol, "H4", mt5.TIMEFRAME_H4)
                d1_status  = get_timeframe_status(gold_symbol, "D1", mt5.TIMEFRAME_D1)

                # 3. M15 Tactical Badges
                dxy_m15_state = "UP (FLY)" if (dxy_val and dxy_val > 99.50) else "DOWN (DROP)"
                eur_m15_state = "DOWN (DROP)" if eur_bid < 1.1600 else "UP (FLY)"
                jpy_m15_state = "DOWN (YEN UP)" if jpy_bid < 145.00 else "UP (YEN WEAK)"
                chf_m15_state = "DOWN (CHF UP)" if chf_bid < 0.8450 else "UP (USD STRONG)"

                # 4. Fetch last 100 M15 Candlesticks, EMA 8/21 Series, and King Levels
                candles, ema8_series, ema21_series, king_levels = fetch_m15_chart_payload(gold_symbol)

                payload = {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
                    "gold": {
                        "symbol": gold_symbol,
                        "bid": gold_bid,
                        "ask": gold_ask,
                        "spread": gold_spread
                    },
                    "currencies": {
                        "eurusd": eur_bid,
                        "usdjpy": jpy_bid,
                        "gbpusd": gbp_bid,
                        "usdcad": cad_bid,
                        "usdchf": chf_bid
                    },
                    "synthetic_dxy": dxy_val,
                    "confluence": {
                        "M15": m15_status,
                        "H1": h1_status,
                        "H4": h4_status,
                        "D1": d1_status
                    },
                    "m15_indicators": {
                        "dxy": dxy_m15_state,
                        "eurusd": eur_m15_state,
                        "usdjpy": jpy_m15_state,
                        "usdchf": chf_m15_state
                    },
                    "chart_data": {
                        "candles": candles,
                        "ema8": ema8_series,
                        "ema21": ema21_series,
                        "king_levels": king_levels
                    }
                }

                cf_ok = post_payload_to_cloudflare(payload)
                cf_flag = "[CF: ✓]" if cf_ok else "[CF: ✗]"

                king_high_str = f"${king_levels['high']}" if king_levels else "N/A"
                king_low_str = f"${king_levels['low']}" if king_levels else "N/A"

                print(f"{cf_flag} [{payload['timestamp']}] XAU: ${gold_bid:.2f} | DXY: {dxy_val} | King:[H:{king_high_str} L:{king_low_str}] | Conf: M15:{m15_status} H1:{h1_status} H4:{h4_status} D1:{d1_status}")

                try:
                    with open("live_feed.json", "w") as f:
                        json.dump(payload, f, indent=2)
                except Exception:
                    pass

            time.sleep(2.0)  # 2-second heartbeat loop

    except KeyboardInterrupt:
        print("\n[!] Bridge interrupted. Shutting down...")
    finally:
        mt5.shutdown()
        print("[✓] MT5 connection closed.")

if __name__ == "__main__":
    init_bridge()
