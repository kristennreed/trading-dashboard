import streamlit as st
import json
import os
from datetime import datetime
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

ALPACA_API_KEY = "PKCYEN7OJAIXY2EN6RRMJVERYT"
ALPACA_SECRET_KEY = "GvRPp9vvZ5oRCceTpjVhWWYJmmMABHQbCenrB77d6j3q"
SIGNALS_FILE = os.path.expanduser("~/Desktop/signals.json")

trading_client = TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=True)

st.set_page_config(page_title="AI Trading Dashboard", page_icon="📈", layout="wide")
st.title("📈 AI Market Scanner Dashboard")
st.caption(f"Last refreshed: {datetime.now().strftime('%A %B %d, %Y %I:%M %p')}")

def load_signals():
    if os.path.exists(SIGNALS_FILE):
        with open(SIGNALS_FILE, "r") as f:
            return json.load(f)
    return []

def save_signals(signals):
    with open(SIGNALS_FILE, "w") as f:
        json.dump(signals, f, indent=2)

st.subheader("Account Overview")
try:
    account = trading_client.get_account()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Portfolio Value", f"${float(account.portfolio_value):,.2f}")
    col2.metric("Cash Available", f"${float(account.cash):,.2f}")
    col3.metric("Buying Power", f"${float(account.buying_power):,.2f}")
    col4.metric("Account Status", account.status)
except Exception as e:
    st.error(f"Could not load account: {e}")

st.divider()

st.subheader("Open Positions")
try:
    positions = trading_client.get_all_positions()
    if positions:
        for pos in positions:
            pl = float(pos.unrealized_pl)
            pl_pct = float(pos.unrealized_plpc) * 100
            col1, col2, col3, col4, col5 = st.columns([1,1,1,1,1])
            col1.metric("Symbol", pos.symbol)
            col2.metric("Shares", pos.qty)
            col3.metric("Avg Entry", f"${float(pos.avg_entry_price):,.2f}")
            col4.metric("Current Price", f"${float(pos.current_price):,.2f}")
            col5.metric("P&L", f"${pl:,.2f}", f"{pl_pct:+.2f}%", delta_color="normal" if pl >= 0 else "inverse")
    else:
        st.info("No open positions")
except Exception as e:
    st.error(f"Could not load positions: {e}")

st.divider()

st.subheader("Today's AI Opportunities")
signals = load_signals()

if not signals:
    st.warning("No signals loaded yet. Run scanner.py first or load sample signals below.")
else:
    st.success(f"{len(signals)} opportunities found today")
    tab1, tab2, tab3 = st.tabs(["All Signals", "Pending Approval", "Executed"])

    with tab1:
        for i, signal in enumerate(signals):
            icon = "🟢" if signal["action"] == "BUY" else "🔴"
            with st.expander(f"{icon} {signal['symbol']} — {signal['action']} | Confidence: {signal['confidence']} | Change: {signal['change_pct']:+.2f}%", expanded=signal["status"] == "pending"):
                col1, col2, col3 = st.columns(3)
                col1.metric("Current Price", f"${signal['price']}")
                col2.metric("Target Price", f"${signal.get('target', 'N/A')}")
                col3.metric("Stop Loss", f"${signal.get('stop_loss', 'N/A')}")
                st.markdown(f"**Reasoning:** {signal['reasoning']}")
                st.markdown(f"**Sector:** {signal.get('sector', 'N/A')} | **Volume Spike:** {signal['volume_spike']}x | **Status:** `{signal['status']}`")
                if signal["status"] == "pending":
                    col_a, col_b, col_c = st.columns([1,1,4])
                    with col_a:
                        if st.button("Approve", key=f"approve_{i}"):
                            try:
                                order = MarketOrderRequest(
                                    symbol=signal["symbol"],
                                    qty=1,
                                    side=OrderSide.BUY if signal["action"] == "BUY" else OrderSide.SELL,
                                    time_in_force=TimeInForce.GTC
                                )
                                result = trading_client.submit_order(order)
                                signals[i]["status"] = "executed"
                                signals[i]["order_id"] = str(result.id)
                                signals[i]["executed_at"] = datetime.now().isoformat()
                                save_signals(signals)
                                st.success(f"Order placed for {signal['symbol']}! Order ID: {result.id}")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Order failed: {e}")
                    with col_b:
                        if st.button("Skip", key=f"skip_{i}"):
                            signals[i]["status"] = "skipped"
                            save_signals(signals)
                            st.rerun()
                elif signal["status"] == "executed":
                    st.success(f"Executed | Order ID: {signal.get('order_id', 'N/A')}")
                elif signal["status"] == "skipped":
                    st.warning("Skipped")

    with tab2:
        pending = [s for s in signals if s["status"] == "pending"]
        st.write(f"{len(pending)} trades awaiting approval") if pending else st.info("No pending trades")

    with tab3:
        executed = [s for s in signals if s["status"] == "executed"]
        if executed:
            for s in executed:
                st.write(f"{s['symbol']} — {s['action']} | Executed at {s.get('executed_at', 'N/A')[:16]}")
        else:
            st.info("No executed trades yet")

st.divider()

if st.button("Refresh Signals"):
    st.rerun()

if st.button("Load Sample Signals"):
    sample = [
        {"symbol": "NFLX", "action": "BUY", "confidence": "Medium", "price": 97.31, "target": 115.00, "stop_loss": 88.50, "change_pct": -9.72, "volume_spike": 2.13, "sector": "Communication Services", "reasoning": "Post-earnings capitulation with smart money accumulation. Billionaire 1B buy-in noted. Strong streaming moat intact.", "status": "pending", "scanned_at": datetime.now().isoformat()},
        {"symbol": "ADI", "action": "BUY", "confidence": "Medium-High", "price": 371.45, "target": 395.00, "stop_loss": 355.00, "change_pct": 4.99, "volume_spike": 1.79, "sector": "Technology", "reasoning": "Institutional accumulation on satellite and industrial semiconductor boom. Clean technical window before May 21 earnings.", "status": "pending", "scanned_at": datetime.now().isoformat()},
        {"symbol": "LOW", "action": "BUY", "confidence": "Medium", "price": 251.72, "target": 272.00, "stop_loss": 238.00, "change_pct": 3.84, "volume_spike": 1.53, "sector": "Consumer Discretionary", "reasoning": "Breakout on competitor store closures. Dividend catalyst approaching May 5. Strong spring selling season setup.", "status": "pending", "scanned_at": datetime.now().isoformat()},
        {"symbol": "DLTR", "action": "BUY", "confidence": "Medium", "price": 105.93, "target": 118.00, "stop_loss": 98.00, "change_pct": 6.00, "volume_spike": 1.63, "sector": "Consumer Staples", "reasoning": "Defensive rotation into value retail. Strong volume on consumer safety trade.", "status": "pending", "scanned_at": datetime.now().isoformat()},
        {"symbol": "FANG", "action": "SELL", "confidence": "Medium", "price": 180.27, "target": 165.00, "stop_loss": 188.00, "change_pct": -3.42, "volume_spike": 1.52, "sector": "Energy", "reasoning": "Sector weakness while broader market strong. Wide earnings estimate range signals uncertainty.", "status": "pending", "scanned_at": datetime.now().isoformat()}
    ]
    save_signals(sample)
    st.success("Sample signals loaded!")
    st.rerun()
