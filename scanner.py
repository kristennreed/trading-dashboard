import pandas as pd
import yfinance as yf
import ta
import json
import os
from datetime import datetime, timedelta
import anthropic
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

ALPACA_API_KEY    = "YOUR_ALPACA_KEY"
ALPACA_SECRET_KEY = "YOUR_ALPACA_SECRET"
ANTHROPIC_API_KEY = "YOUR_ANTHROPIC_KEY"
SIGNALS_FILE = os.path.expanduser("~/Desktop/trading-dashboard/signals.json")

trading_client = TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=True)
data_client    = StockHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY)
claude         = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SP500 = [
    "AAPL","MSFT","NVDA","AMZN","GOOGL","META","TSLA","JPM","V",
    "UNH","XOM","LLY","JNJ","MA","PG","HD","MRK","AVGO","CVX",
    "PEP","ABBV","KO","COST","ADBE","WMT","MCD","CRM","BAC","ACN",
    "LIN","TMO","CSCO","ABT","NFLX","DHR","AMD","CMCSA","NKE","NEE",
    "TXN","PM","WFC","BMY","INTC","ORCL","RTX","QCOM","HON","UPS",
    "LOW","AMGN","SBUX","GS","INTU","ELV","MDT","CAT","DE","SPGI",
    "AXP","PLD","BLK","GILD","ADI","ISRG","VRTX","REGN","SYK","ZTS",
    "NOW","PYPL","MO","CI","DUK","SO","BDX","AON","TGT",
    "ITW","CME","APD","GE","USB","NSC","EMR","FCX","MCO",
    "UBER","ABNB","SNOW","PLTR","CRWD","DDOG","ZS","NET","MELI"
]

NASDAQ100 = [
    "AAPL","MSFT","NVDA","AMZN","META","TSLA","GOOGL","AVGO","ADBE","COST",
    "NFLX","AMD","QCOM","INTC","INTU","CMCSA","TXN","HON","AMGN","SBUX",
    "ISRG","VRTX","REGN","GILD","PYPL","MELI","LRCX","KLAC","SNPS","CDNS",
    "ORLY","ABNB","CTAS","PAYX","ROST","FTNT","MRVL","AEP","IDXX","BIIB",
    "FAST","MRNA","DXCM","KDP","EA","CTSH","VRSK","GEHC","FANG","EXC",
    "DLTR","XEL","PCAR","CPRT","ODFL","CEG","TEAM","CRWD","DDOG","ZS",
    "NET","SNOW","PLTR","UBER","LCID","RIVN"
]

UNIVERSE = list(set(SP500 + NASDAQ100))
print(f"Total universe: {len(UNIVERSE)} stocks")

print("\nFetching market context...")
try:
    market_summary_parts = []
    for symbol in ["SPY", "QQQ", "XLK"]:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="5d")
        if not hist.empty and len(hist) >= 2:
            change = ((hist["Close"].iloc[-1] - hist["Open"].iloc[0]) / hist["Open"].iloc[0]) * 100
            latest = hist["Close"].iloc[-1]
            market_summary_parts.append(f"{symbol}: {change:+.2f}% over the period, latest close: ${latest:.2f}")
        else:
            market_summary_parts.append(f"{symbol}: No data available")
    market_summary = "\n".join(market_summary_parts)
    print(f"Market context fetched successfully")
except Exception as e:
    market_summary = "Market context unavailable"
    print(f"Market context error: {e}")

print("\nScanning market for opportunities...")
candidates = []

for i, symbol in enumerate(UNIVERSE):
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="20d")
        if hist.empty or len(hist) < 10:
            continue

        closes  = hist["Close"]
        highs   = hist["High"]
        lows    = hist["Low"]
        volumes = hist["Volume"]

        latest_close  = closes.iloc[-1]
        prev_close    = closes.iloc[-2]
        price_change  = ((latest_close - prev_close) / prev_close) * 100
        avg_volume    = volumes.iloc[:-1].mean()
        latest_volume = volumes.iloc[-1]
        volume_spike  = latest_volume / avg_volume if avg_volume > 0 else 0

        rsi = ta.momentum.RSIIndicator(closes, window=14).rsi().iloc[-1]

        macd_ind    = ta.trend.MACD(closes)
        macd_line   = macd_ind.macd().iloc[-1]
        macd_signal = macd_ind.macd_signal().iloc[-1]
        macd_cross  = "bullish" if macd_line > macd_signal else "bearish"

        bb          = ta.volatility.BollingerBands(closes)
        bb_upper    = bb.bollinger_hband().iloc[-1]
        bb_lower    = bb.bollinger_lband().iloc[-1]
        bb_position = "above_upper" if latest_close > bb_upper else "below_lower" if latest_close < bb_lower else "middle"

        if (abs(price_change) >= 2.0 and
            volume_spike >= 1.5 and
            latest_close >= 10):

            candidates.append({
                "symbol":       symbol,
                "price":        round(latest_close, 2),
                "change_pct":   round(price_change, 2),
                "volume_spike": round(volume_spike, 2),
                "avg_volume":   int(avg_volume),
                "rsi":          round(rsi, 1),
                "macd":         macd_cross,
                "bb_position":  bb_position,
                "bb_upper":     round(bb_upper, 2),
                "bb_lower":     round(bb_lower, 2)
            })

        if i % 20 == 0:
            print(f"  Scanned {i}/{len(UNIVERSE)} stocks... ({len(candidates)} candidates so far)")

    except Exception as e:
        continue

candidates = sorted(candidates, key=lambda x: abs(x["change_pct"]), reverse=True)[:10]
print(f"\nTop {len(candidates)} candidates found:")
for c in candidates:
    print(f"  {c['symbol']}: {c['change_pct']:+.2f}% | RSI: {c['rsi']} | MACD: {c['macd']} | BB: {c['bb_position']} | Vol: {c['volume_spike']}x")

if not candidates:
    print("No candidates found. Try running during market hours.")
    exit()

print("\nEnriching candidate data...")
enriched = []

for c in candidates:
    symbol = c["symbol"]
    try:
        ticker = yf.Ticker(symbol)

        try:
            news_items = ticker.news[:3]
            news = "\n".join([
                f"- {item['content']['title']}"
                for item in news_items
            ]) if news_items else "No recent news"
        except:
            news = "News unavailable"

        try:
            calendar = ticker.calendar
            earnings = str(calendar) if calendar is not None and len(calendar) > 0 else "No upcoming earnings"
        except:
            earnings = "Earnings data unavailable"

        try:
            info     = ticker.info
            sector   = info.get("sector", "Unknown")
            mkt_cap  = info.get("marketCap", 0)
            pe_ratio = info.get("trailingPE", "N/A")
        except:
            sector   = "Unknown"
            mkt_cap  = 0
            pe_ratio = "N/A"

        enriched.append({
            **c,
            "sector":   sector,
            "mkt_cap":  mkt_cap,
            "pe_ratio": pe_ratio,
            "news":     news,
            "earnings": earnings
        })
        print(f"  Enriched {symbol}")

    except Exception as e:
        enriched.append({
            **c,
            "sector":   "Unknown",
            "mkt_cap":  0,
            "pe_ratio": "N/A",
            "news":     "Unavailable",
            "earnings": "Unavailable"
        })
        continue
# Load trade history for self-learning
print("Loading trade history for self-learning...")
journal_file = os.path.expanduser("~/Desktop/trading-dashboard/trade_journal.json")
performance_context = ""
try:
    if os.path.exists(journal_file):
        with open(journal_file, "r") as f:
            journal = json.load(f)
        
        closed_trades = [t for t in journal if t.get("status") == "closed" and t.get("pl_dollar") is not None]
        
        if closed_trades:
            wins = [t for t in closed_trades if t.get("outcome") == "win"]
            losses = [t for t in closed_trades if t.get("outcome") == "loss"]
            win_rate = len(wins) / len(closed_trades) * 100
            avg_win = sum(t["pl_pct"] for t in wins) / len(wins) if wins else 0
            avg_loss = sum(t["pl_pct"] for t in losses) / len(losses) if losses else 0
            total_pl = sum(t["pl_dollar"] for t in closed_trades)

            # RSI performance
            rsi_oversold = [t for t in closed_trades if isinstance(t.get("rsi_at_entry"), (int, float)) and t["rsi_at_entry"] < 30]
            rsi_neutral = [t for t in closed_trades if isinstance(t.get("rsi_at_entry"), (int, float)) and 30 <= t["rsi_at_entry"] <= 70]
            rsi_overbought = [t for t in closed_trades if isinstance(t.get("rsi_at_entry"), (int, float)) and t["rsi_at_entry"] > 70]

            def win_rate_str(trades):
                if not trades:
                    return "no data"
                w = len([t for t in trades if t.get("outcome") == "win"])
                return f"{w}/{len(trades)} ({w/len(trades)*100:.0f}% win rate)"

            performance_context = f"""
## Historical Performance Context (Learn From This)
Total closed trades: {len(closed_trades)}
Overall win rate: {win_rate:.1f}%
Average win: +{avg_win:.2f}%
Average loss: {avg_loss:.2f}%
Total P&L: ${total_pl:.2f}

RSI Performance Breakdown:
- RSI below 30 (oversold entries): {win_rate_str(rsi_oversold)}
- RSI 30-70 (neutral entries): {win_rate_str(rsi_neutral)}
- RSI above 70 (overbought entries): {win_rate_str(rsi_overbought)}

Recent losing trades to avoid repeating:
{chr(10).join([f"- {t['symbol']}: entered at RSI {t.get('rsi_at_entry','N/A')}, MACD {t.get('macd_at_entry','N/A')}, lost {t['pl_pct']:.1f}%" for t in losses[-3:]])}

Recent winning trades to replicate:
{chr(10).join([f"- {t['symbol']}: entered at RSI {t.get('rsi_at_entry','N/A')}, MACD {t.get('macd_at_entry','N/A')}, gained {t['pl_pct']:.1f}%" for t in wins[-3:]])}
"""
            print(f"Loaded {len(closed_trades)} closed trades for learning context")
        else:
            performance_context = "No closed trades yet — this is early stage learning."
            print("No closed trades yet for learning")
    else:
        performance_context = "No trade journal found yet."
except Exception as e:
    performance_context = "Trade history unavailable."
    print(f"Could not load journal: {e}")

print("\nSending candidates to Claude for analysis...")

candidate_text = ""
for c in enriched:
    candidate_text += f"""
Stock: {c['symbol']}
Price: ${c['price']} | Change: {c['change_pct']:+.2f}% | Volume Spike: {c['volume_spike']}x
RSI: {c.get('rsi', 'N/A')} | MACD: {c.get('macd', 'N/A')} | Bollinger: {c.get('bb_position', 'N/A')}
BB Upper: ${c.get('bb_upper', 'N/A')} | BB Lower: ${c.get('bb_lower', 'N/A')}
Sector: {c['sector']} | Market Cap: ${c['mkt_cap']:,} | P/E: {c['pe_ratio']}
Recent News:
{c['news']}
Earnings Info:
{c['earnings']}
---"""

prompt = f"""You are an expert stock trader and options analyst with deep knowledge of technical analysis. You are also a self-learning trading system that improves based on historical performance data.

{performance_context}

Based on the historical performance above, adjust your recommendations accordingly. If oversold RSI entries have been winning, favor those setups. If certain patterns have been losing, avoid recommending them.

RSI Guide: Below 30 = oversold (potential buy), Above 70 = overbought (potential sell), 30-70 = neutral
MACD Guide: Bullish cross = upward momentum, Bearish cross = downward momentum
Bollinger Bands: Above upper band = overbought/breakout, Below lower band = oversold/breakdown

Market Context:
{market_summary}

Candidates:
{candidate_text}

For each stock analyze the combination of price action, volume, AND technical indicators. Factor in the historical performance data above to weight your recommendations.

Provide your response in this EXACT format for each trade:

SIGNAL: [SYMBOL] | ACTION: [BUY/SELL] | CONFIDENCE: [High/Medium/Low]
ENTRY: $[price range]
TARGET: $[specific price]
STOP: $[specific price]
REASONING: [2-3 sentences including RSI, MACD, BB context and how historical performance supports this]
---

After all signals provide:
TOP OPTIONS PLAY: [symbol, strategy, strike, expiry, reasoning]
AVOID: [symbols to avoid and why]"""

message = claude.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=2000,
    messages=[{"role": "user", "content": prompt}]
)

analysis = message.content[0].text
print("\n" + "="*60)
print("AI MARKET SCANNER REPORT")
print("="*60)
print(analysis)

print("\nSaving signals...")
signals = []
for c in enriched[:10]:
    symbol = c["symbol"]
    action = "BUY"

    analysis_upper = analysis.upper()
    symbol_index = analysis_upper.find(symbol)
    if symbol_index != -1:
        context = analysis_upper[symbol_index:symbol_index+200]
        if "SELL" in context or "PUT" in context or "AVOID" in context:
            action = "SELL"
        elif "BUY" in context or "CALL" in context:
            action = "BUY"
        else:
            action = "BUY" if c["change_pct"] > 0 else "SELL"

    # Try to extract Claude's specific target and stop loss
    target_price = round(c["price"] * 1.08, 2)
    stop_price   = round(c["price"] * 0.95, 2)
    confidence   = "Medium"

    try:
        import re
        sym_section = analysis[analysis.upper().find(symbol):]
        sym_section = sym_section[:500]

        target_match = re.search(r'TARGET:\s*\$?([\d,]+\.?\d*)', sym_section, re.IGNORECASE)
        stop_match   = re.search(r'STOP:\s*\$?([\d,]+\.?\d*)', sym_section, re.IGNORECASE)
        conf_match   = re.search(r'CONFIDENCE:\s*(High|Medium|Low)', sym_section, re.IGNORECASE)

        if target_match:
            target_price = float(target_match.group(1).replace(',', ''))
        if stop_match:
            stop_price = float(stop_match.group(1).replace(',', ''))
        if conf_match:
            confidence = conf_match.group(1).capitalize()
    except:
        pass

    signals.append({
        "symbol":       symbol,
        "action":       action,
        "confidence":   confidence,
        "price":        c["price"],
        "target":       target_price,
        "stop_loss":    stop_price,
        "change_pct":   c["change_pct"],
        "volume_spike": c["volume_spike"],
        "rsi":          c.get("rsi", "N/A"),
        "macd":         c.get("macd", "N/A"),
        "bb_position":  c.get("bb_position", "N/A"),
        "sector":       c.get("sector", "Unknown"),
        "reasoning":    f"RSI: {c.get('rsi', 'N/A')} | MACD: {c.get('macd', 'N/A')} | BB: {c.get('bb_position', 'N/A')} | Volume spike {c['volume_spike']}x with {c['change_pct']:+.2f}% price move.",
        "status":       "pending",
        "scanned_at":   datetime.now().isoformat()
    })

with open(SIGNALS_FILE, "w") as f:
    json.dump(signals, f, indent=2)
print(f"Saved {len(signals)} signals to {SIGNALS_FILE}")

print("\n" + "="*60)
print("SIGNALS SAVED — Approve trades in your dashboard")
print("="*60)
print("Visit kristennreed.pythonanywhere.com to review and approve trades")
print("\nScan complete!")
# Push signals to GitHub so Streamlit dashboard can read them
try:
    import subprocess
    repo_path = os.path.expanduser("~/Desktop/trading-dashboard")
    subprocess.run(["git", "-C", repo_path, "add", "signals.json"], check=True)
    subprocess.run(["git", "-C", repo_path, "commit", "-m", f"Update signals {datetime.now().strftime('%Y-%m-%d %H:%M')}"], check=True)
    subprocess.run(["git", "-C", repo_path, "pull", "--rebase", "origin", "main"], check=True)
    subprocess.run(["git", "-C", repo_path, "push", "origin", "main"], check=True)
    print("Signals pushed to GitHub successfully")
except Exception as e:
    print(f"GitHub push note: {e}")