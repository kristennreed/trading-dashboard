import streamlit as st
import json
import os
from datetime import datetime, timedelta
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
import requests

ALPACA_API_KEY = st.secrets["ALPACA_API_KEY"]
ALPACA_SECRET_KEY = st.secrets["ALPACA_SECRET_KEY"]

trading_client = TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=True)

st.set_page_config(
    page_title="Reed's Reads",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600&display=swap');
html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif !important; }
.stApp { background: white !important; }
[data-testid="stMetricValue"] { font-family: 'Plus Jakarta Sans', sans-serif !important; }
[data-testid="stExpander"] { border: 0.5px solid rgba(0,0,0,0.1) !important; border-radius: 12px !important; }
.stButton button { border-radius: 20px !important; font-family: 'Plus Jakarta Sans', sans-serif !important; font-size: 12px !important; }
[data-testid="stTabs"] button { font-family: 'Plus Jakarta Sans', sans-serif !important; font-size: 12px !important; }
</style>
""", unsafe_allow_html=True)


def load_signals():
    if 'signals' in st.session_state:
        return st.session_state['signals']
    try:
        url = "https://raw.githubusercontent.com/kristennreed/trading-dashboard/main/signals.json"
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        return []
    except:
        return []

def save_signals(signals):
    try:
        import base64
        token = st.secrets["GITHUB_TOKEN"]
        url = "https://api.github.com/repos/kristennreed/trading-dashboard/contents/signals.json"
        headers = {"Authorization": f"token {token}"}
        r = requests.get(url, headers=headers)
        sha = r.json()["sha"]
        content = base64.b64encode(json.dumps(signals, indent=2).encode()).decode()
        requests.put(url, headers=headers, json={
            "message": "Update signal status",
            "content": content,
            "sha": sha
        })
        st.session_state['signals'] = signals
    except Exception as e:
        st.error(f"Failed to save: {e}")
        st.session_state['signals'] = signals

def load_active_trades():
    try:
        url = "https://raw.githubusercontent.com/kristennreed/trading-dashboard/main/active_trades.json"
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        return []
    except:
        return []

def get_stock_history(symbol):
    try:
        import urllib.request
        end = datetime.now()
        start = end - timedelta(days=30)
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&period1={int(start.timestamp())}&period2={int(end.timestamp())}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        closes = data['chart']['result'][0]['indicators']['quote'][0]['close']
        return [c for c in closes if c is not None]
    except:
        return []

def make_sparkline(closes, color):
    if not closes or len(closes) < 2:
        return ""
    mn, mx = min(closes), max(closes)
    rng = mx - mn if mx != mn else 1
    w, h = 80, 38
    pts = []
    for i, c in enumerate(closes):
        x = i / (len(closes) - 1) * w
        y = h - 4 - ((c - mn) / rng) * (h - 8)
        pts.append(f"{x:.1f},{y:.1f}")
    poly_pts = pts + [f"{w},38", "0,38"]
    return f"""<svg width="80" height="38" viewBox="0 0 80 38" preserveAspectRatio="none">
      <defs><linearGradient id="g_{symbol_safe(color)}" x1="0" x2="0" y1="0" y2="1">
        <stop offset="0%" stop-color="{color}" stop-opacity="0.25"/>
        <stop offset="100%" stop-color="{color}" stop-opacity="0"/>
      </linearGradient></defs>
      <polygon points="{' '.join(poly_pts)}" fill="url(#g_{symbol_safe(color)})"/>
      <polyline points="{' '.join(pts)}" fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>"""

def symbol_safe(s):
    return s.replace('#','').replace('/','')

def position_color(current, stop, target):
    try:
        total = float(target) - float(stop)
        if total <= 0: return "#FF9F00"
        pct = (float(current) - float(stop)) / total
        if pct >= 0.60: return "#00C853"
        if pct >= 0.25: return "#FF9F00"
        return "#FF1744"
    except:
        return "#FF9F00"


# ── Header ─────────────────────────────────────────────────────────────────────
col1, col2 = st.columns([3,1])
with col1:
    st.markdown("<h1 style='font-family:Plus Jakarta Sans,sans-serif; font-size:24px; font-weight:600; letter-spacing:-0.5px; margin-bottom:0;'>Reed's <span style=\"font-weight:300; color:#888;\">Reads</span></h1>", unsafe_allow_html=True)
with col2:
    st.markdown(f"<p style='text-align:right; color:#888; font-size:12px; padding-top:16px;'>{datetime.now().strftime('%b %d, %Y · %I:%M %p')}</p>", unsafe_allow_html=True)

st.divider()

# ── Account Overview ───────────────────────────────────────────────────────────
try:
    account = trading_client.get_account()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Portfolio Value", f"${float(account.portfolio_value):,.2f}")
    col2.metric("Cash Available", f"${float(account.cash):,.2f}")
    col3.metric("Buying Power", f"${float(account.buying_power):,.2f}")
    col4.metric("Status", account.status.upper())
except Exception as e:
    st.error(f"Could not load account: {e}")

st.divider()

# ── Open Positions ─────────────────────────────────────────────────────────────
st.markdown("<p style='font-size:11px; font-weight:500; color:#888; letter-spacing:0.6px; text-transform:uppercase; margin-bottom:8px;'>Open Positions</p>", unsafe_allow_html=True)

try:
    positions = trading_client.get_all_positions()
    active_trades = load_active_trades()

    if positions:
        for pos in positions:
            pl = float(pos.unrealized_pl)
            pl_pct = float(pos.unrealized_plpc) * 100
            current = float(pos.current_price)
            entry = float(pos.avg_entry_price)
            symbol = pos.symbol

            trade = next((t for t in active_trades if t['symbol'] == symbol and t['status'] == 'open'), None)
            target = float(trade['target']) if trade else None
            stop = float(trade['stop_loss']) if trade else None

            color = position_color(current, stop, target) if (stop and target) else ("#00C853" if pl >= 0 else "#FF1744")

            closes = get_stock_history(symbol)
            spark = make_sparkline(closes, color)

            badge_color = color
            pl_sign = "+" if pl >= 0 else ""

            stop_line = f"Stop ${stop:,.2f} → Target ${target:,.2f}" if (stop and target) else ""
            st.markdown(f"""
            <div style="display:flex; align-items:center; padding:10px 0; border-bottom:0.5px solid #f0f0f0; gap:12px; font-family:'Plus Jakarta Sans',sans-serif;">
              <div style="flex:1; min-width:0;">
                <div style="font-size:15px; font-weight:600; color:#111;">{symbol}</div>
                <div style="font-size:11px; color:#888; margin-top:2px;">{pos.qty} shares · Entry ${entry:,.2f}</div>
                <div style="font-size:10px; color:#aaa; margin-top:2px;">{stop_line}</div>
              </div>
              {spark}
              <div style="text-align:right; flex-shrink:0; min-width:90px;">
                <div style="font-size:15px; font-weight:500; color:#111;">${current:,.2f}</div>
                <div style="display:inline-block; font-size:11px; font-weight:600; padding:3px 8px; border-radius:6px; margin-top:4px; background:{badge_color}; color:#fff; min-width:70px; text-align:center;">{pl_sign}${abs(pl):,.2f}</div>
              </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No open positions")
except Exception as e:
    st.error(f"Could not load positions: {e}")

st.divider()

# ── Signals ────────────────────────────────────────────────────────────────────
st.markdown("<p style='font-size:11px; font-weight:500; color:#888; letter-spacing:0.6px; text-transform:uppercase; margin-bottom:8px;'>Today's Signals</p>", unsafe_allow_html=True)

signals = load_signals()

if not signals:
    st.warning("No signals loaded. Run scanner.py first.")
else:
    pending_count = len([s for s in signals if s["status"] == "pending"])
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Signals", len(signals))
    col2.metric("Pending", pending_count)
    col3.metric("BUY Signals", len([s for s in signals if s["action"] == "BUY"]))

    tab1, tab2, tab3 = st.tabs(["All Signals", "Pending Approval", "Executed"])

    with tab1:
        for i, signal in enumerate(signals):
            action = signal["action"]
            status = signal["status"]
            price = float(signal.get('price', 0))
            target = signal.get('target')
            stop_loss = signal.get('stop_loss')
            rr = signal.get('reward_risk', 'N/A')

            sig_color = "#00C853" if action == "BUY" else "#FF1744"
            closes = get_stock_history(signal['symbol'])
            spark = make_sparkline(closes, sig_color if status != "skipped" else "#aaa")

            opacity = "0.4" if status == "skipped" else "1"

            st.markdown(f"""
            <div style="display:flex; align-items:center; padding:10px 0; border-bottom:0.5px solid #f0f0f0; gap:12px; font-family:'Plus Jakarta Sans',sans-serif; opacity:{opacity};">
              <div style="flex:1; min-width:0;">
                <div style="font-size:15px; font-weight:600; color:#111;">{signal['symbol']}</div>
                <div style="font-size:11px; color:#888; margin-top:2px;">${price:,.2f} · Stop ${stop_loss} · Target ${target} · R/R {rr}</div>
              </div>
              {spark}
              <div style="text-align:right; flex-shrink:0; min-width:80px;">
                <div style="font-size:13px; font-weight:500; color:#111;">{signal['change_pct']:+.2f}%</div>
                <div style="display:inline-block; font-size:11px; font-weight:600; padding:3px 10px; border-radius:6px; margin-top:4px; background:{'#00C853' if action == 'BUY' else '#f0f0f0'}; color:{'#fff' if action == 'BUY' else '#888'}; min-width:60px; text-align:center;">{'BUY' if action == 'BUY' else status.upper()}</div>
              </div>
            </div>
            """, unsafe_allow_html=True)

            if status == "pending":
                col_a, col_b, col_c = st.columns([1, 1, 4])
                with col_a:
                    if action == "SELL":
                        st.warning("⚠️ Short selling disabled")
                    elif st.button("✅ Approve", key=f"approve_{i}"):
                        try:
                            acct = trading_client.get_account()
                            portfolio_value = float(acct.portfolio_value)
                            stop_distance = abs(price - float(stop_loss)) if stop_loss else price * 0.05
                            max_risk = portfolio_value * 0.02
                            shares = int(max_risk / stop_distance) if stop_distance > 0 else 1
                            max_alloc = int((portfolio_value * 0.10) / price)
                            shares = max(1, min(shares, max_alloc))
                            order = MarketOrderRequest(
                                symbol=signal["symbol"],
                                qty=shares,
                                side=OrderSide.BUY,
                                time_in_force=TimeInForce.GTC
                            )
                            result = trading_client.submit_order(order)
                            signals[i]["status"] = "executed"
                            signals[i]["order_id"] = str(result.id)
                            signals[i]["executed_at"] = datetime.now().isoformat()
                            save_signals(signals)
                            st.success(f"✅ {signal['symbol']} — {shares} shares @ ${price:.2f} | Risk: ${shares * stop_distance:.0f}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Order failed: {e}")
                with col_b:
                    if st.button("⏭ Skip", key=f"skip_{i}"):
                        signals[i]["status"] = "skipped"
                        st.session_state['signals'] = signals
                        save_signals(signals)
                        st.rerun()

    with tab2:
        pending = [s for s in signals if s["status"] == "pending"]
        if pending:
            for s in pending:
                st.markdown(f"**{s['symbol']}** — {s['action']} @ ${s['price']} | Target: ${s.get('target','N/A')} | Stop: ${s.get('stop_loss','N/A')}")
        else:
            st.info("No pending trades")

    with tab3:
        executed = [s for s in signals if s["status"] == "executed"]
        if executed:
            for s in executed:
                st.write(f"✅ {s['symbol']} — {s.get('executed_at','N/A')[:16]}")
        else:
            st.info("No executed trades yet")

st.divider()

col1, col2 = st.columns([1,1])
with col1:
    if st.button("🔄 Refresh Signals"):
        if 'signals' in st.session_state:
            del st.session_state['signals']
        st.rerun()
with col2:
    if st.button("🧪 Load Sample"):
        sample = [
            {"symbol": "NFLX", "action": "BUY", "confidence": "Medium", "price": 97.31, "target": 115.00, "stop_loss": 88.50, "change_pct": -9.72, "volume_spike": 2.13, "sector": "Communication Services", "reasoning": "Post-earnings capitulation.", "status": "pending", "scanned_at": datetime.now().isoformat()},
            {"symbol": "FANG", "action": "SELL", "confidence": "Medium", "price": 180.27, "target": 165.00, "stop_loss": 188.00, "change_pct": -3.42, "volume_spike": 1.52, "sector": "Energy", "reasoning": "Sector weakness.", "status": "pending", "scanned_at": datetime.now().isoformat()}
        ]
        save_signals(sample)
        st.rerun()

st.markdown(f"<p style='text-align:center; color:#bbb; font-size:11px; margin-top:20px;'>Reed's Reads · Paper Mode · {datetime.now().strftime('%B %d, %Y')}</p>", unsafe_allow_html=True)
