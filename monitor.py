import time
import json
import os
from datetime import datetime
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

ALPACA_API_KEY    = "YOUR_API_KEY"
ALPACA_SECRET_KEY = "YOUR_API_SECRET"
SIGNALS_FILE      = os.path.expanduser("~/Desktop/signals.json")
LOG_FILE          = os.path.expanduser("~/Desktop/trade_log.txt")

STOP_LOSS_PCT   = 0.05
TAKE_PROFIT_PCT = 0.08

trading_client = TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=True)

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def load_signals():
    if os.path.exists(SIGNALS_FILE):
        with open(SIGNALS_FILE, "r") as f:
            return json.load(f)
    return []

def save_signals(signals):
    with open(SIGNALS_FILE, "w") as f:
        json.dump(signals, f, indent=2)

def is_market_open():
    clock = trading_client.get_clock()
    return clock.is_open

def check_positions():
    try:
        positions = trading_client.get_all_positions()
        signals   = load_signals()
        if not positions:
            log("No open positions to monitor")
            return
        for pos in positions:
            symbol    = pos.symbol
            entry     = float(pos.avg_entry_price)
            current   = float(pos.current_price)
            pl_pct    = (current - entry) / entry
            pl_dollar = float(pos.unrealized_pl)
            log(f"Checking {symbol}: Entry=${entry:.2f} Current=${current:.2f} P&L={pl_pct*100:+.2f}% (${pl_dollar:+.2f})")
            signal      = next((s for s in signals if s["symbol"] == symbol), None)
            take_profit = TAKE_PROFIT_PCT
            stop_loss   = STOP_LOSS_PCT
            if signal:
                if signal.get("target") and entry > 0:
                    take_profit = (float(signal["target"]) - entry) / entry
                if signal.get("stop_loss") and entry > 0:
                    stop_loss = (entry - float(signal["stop_loss"])) / entry
            if pl_pct >= take_profit:
                log(f"TAKE PROFIT triggered for {symbol} at {pl_pct*100:+.2f}%")
                sell(symbol, pos.qty, "take_profit", signals)
            elif pl_pct <= -stop_loss:
                log(f"STOP LOSS triggered for {symbol} at {pl_pct*100:+.2f}%")
                sell(symbol, pos.qty, "stop_loss", signals)
            else:
                log(f"{symbol} holding — target: +{take_profit*100:.1f}% | stop: -{stop_loss*100:.1f}%")
    except Exception as e:
        log(f"Error checking positions: {e}")

def sell(symbol, qty, reason, signals):
    try:
        order = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.SELL,
            time_in_force=TimeInForce.GTC
        )
        result = trading_client.submit_order(order)
        log(f"SOLD {qty} {symbol} — Reason: {reason} | Order ID: {result.id}")
        for s in signals:
            if s["symbol"] == symbol:
                s["status"]  = f"sold_{reason}"
                s["sold_at"] = datetime.now().isoformat()
        save_signals(signals)
    except Exception as e:
        log(f"Failed to sell {symbol}: {e}")

def run_monitor():
    log("Position monitor started")
    log(f"Stop loss: {STOP_LOSS_PCT*100}% | Take profit: {TAKE_PROFIT_PCT*100}%")
    while True:
        now = datetime.now()
        if now.weekday() < 5:
            if is_market_open():
                log("--- Running position check ---")
                check_positions()
            else:
                log("Market closed — waiting")
        else:
            log("Weekend — market closed")
        log("Next check in 15 minutes")
        time.sleep(900)

if __name__ == "__main__":
    run_monitor()
