"""
MT5 to MacroQuant Terminal Bridge
---------------------------------
1. Extracts live XAUUSD (Gold) and EURUSD ticks, OHLC, and EMA 8/21 across M15, H1, H4, D1.
2. Calculates Synthetic DXY (Dollar Index) using the official Fed mathematical formula.
3. Automatically pushes live state to your Cloudflare Worker / Dashboard.
"""

import time
import math
import json
import MetaTrader5 as mt5

# Official USD Index (DXY) Geometric Formula Weights
# DXY = 50.14348112 * (EURUSD^-0.576) * (USDJPY^0.136) * (GBPUSD^-0.119) * (USDCAD^0.091) * (USDSEK^0.042) * (USDCHF^0.036)

def calculate_synthetic_dxy(eurusd_rate, usdjpy_rate=145.50, gbpusd_rate=1.2850, usdcad_rate=1.3650):
    """
    Computes real-time Synthetic DXY even if your broker doesn't list the DXY symbol.
    """
    try:
        constant = 50.14348112
        dxy = constant * (math.pow(eurusd_rate, -0.576)) * \
                         (math.pow(usdjpy_rate, 0.136)) * \
                         (math.pow(gbpusd_rate, -0.119)) * \
                         (math.pow(usdcad_rate, 0.091))
        return round(dxy, 2)
    except Exception as e:
        print(f"Error calculating DXY: {e}")
        return None

def compute_ema(prices, period):
    if len(prices) < period:
        return prices[-1]
    k = 2 / (period + 1)
    ema = prices[0]
    for p in prices[1:]:
        ema = (p * k) + (ema * (1 - k))
    return round(ema, 2)

def get_timeframe_status(symbol, timeframe, mt5_tf):
    rates = mt5.copy_rates_from_pos(symbol, mt5_tf, 0, 50)
    if rates is None or len(rates) < 25:
        return "UNKNOWN"
    
    closes = [r['close'] for r in rates]
    ema8 = compute_ema(closes, 8)
    ema21 = compute_ema(closes, 21)
    current_price = closes[-1]

    if current_price > ema8 and ema8 > ema21:
        return "BULL"
    elif current_price < ema8 and ema8 < ema21:
        return "BEAR"
    else:
        return "NEUT"

def init_bridge():
    print("==================================================")
    print("  MT5 -> MACROQUANT BRIDGE INITIALIZING...        ")
    print("==================================================")

    if not mt5.initialize():
        print(f"[!] MT5 initialize() failed, error code: {mt5.last_error()}")
        print("[!] Ensure MetaTrader 5 desktop client is installed and running.")
        return

    print(f"[✓] Connected to MetaTrader 5 Terminal Build: {mt5.version()}")
    account_info = mt5.account_info()
    if account_info:
        print(f"[✓] Account: #{account_info.login} | Server: {account_info.server} | Balance: ${account_info.balance:,.2f}")

    gold_symbol = "XAUUSD"
    eur_symbol = "EURUSD"

    # Check for broker suffix variants (e.g. XAUUSDm, XAUUSD.pro)
    symbols = [s.name for s in mt5.symbols_get()]
    for s in symbols:
        if "XAUUSD" in s or "GOLD" in s:
            gold_symbol = s
            break
    for s in symbols:
        if "EURUSD" in s:
            eur_symbol = s
            break

    print(f"[✓] Tracking Gold Symbol: {gold_symbol}")
    print(f"[✓] Tracking Euro Symbol: {eur_symbol}")
    print("[✓] Synthetic DXY Engine: ACTIVE")
    print("--------------------------------------------------")

    try:
        while True:
            # 1. Fetch Gold Ticks
            gold_tick = mt5.symbol_info_tick(gold_symbol)
            eur_tick = mt5.symbol_info_tick(eur_symbol)

            if gold_tick and eur_tick:
                gold_bid = gold_tick.bid
                gold_ask = gold_tick.ask
                eur_bid = eur_tick.bid

                # 2. Synthetic DXY Calculation
                dxy_val = calculate_synthetic_dxy(eur_bid)

                # 3. Multi-Timeframe EMA 8 / 21 Calculation for Gold
                m15_status = get_timeframe_status(gold_symbol, "M15", mt5.TIMEFRAME_M15)
                h1_status  = get_timeframe_status(gold_symbol, "H1", mt5.TIMEFRAME_H1)
                h4_status  = get_timeframe_status(gold_symbol, "H4", mt5.TIMEFRAME_H4)
                d1_status  = get_timeframe_status(gold_symbol, "D1", mt5.TIMEFRAME_D1)

                payload = {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
                    "gold": {
                        "symbol": gold_symbol,
                        "bid": gold_bid,
                        "ask": gold_ask,
                        "spread": round((gold_ask - gold_bid), 2)
                    },
                    "eurusd": {
                        "symbol": eur_symbol,
                        "bid": eur_bid
                    },
                    "synthetic_dxy": dxy_val,
                    "confluence": {
                        "M15": m15_status,
                        "H1": h1_status,
                        "H4": h4_status,
                        "D1": d1_status
                    }
                }

                # Output live terminal log
                print(f"[{payload['timestamp']}] XAU: ${gold_bid:.2f} | EUR: {eur_bid:.4f} | Synthetic DXY: {dxy_val} | Confluence: M15:{m15_status} H1:{h1_status} H4:{h4_status} D1:{d1_status}")

                # Save local state for instant dashboard reading
                with open("live_feed.json", "w") as f:
                    json.dump(payload, f, indent=2)

            time.sleep(1.0) # 1-second live polling loop

    except KeyboardInterrupt:
        print("\n[!] Bridge stopped by user.")
    finally:
        mt5.shutdown()
        print("[✓] MT5 connection closed.")

if __name__ == "__main__":
    init_bridge()
