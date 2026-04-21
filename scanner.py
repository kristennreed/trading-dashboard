import pandas as pd
import yfinance as yf
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime, timedelta
import anthropic
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

# ── Credentials ──────────────────────────────────────────────
ALPACA_API_KEY    = "YOUR_API_KEY"
ALPACA_SECRET_KEY = "YOUR_API_SECRET"
ANTHROPIC_API_KEY = "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"

# ── Clients ───────────────────────────────────────────────────
data_client    = StockHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY)
trading_client = TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=True)
claude         = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ── Stock Universe (S&P 500 + NASDAQ 100 combined) ────────────
SP500 = [
    "AAPL","MSFT","NVDA","AMZN","GOOGL","META","TSLA","BRK-B","JPM","V",
    "UNH","XOM","LLY","JNJ","MA","PG","HD","MRK","AVGO","CVX",
    "PEP","ABBV","KO","COST","ADBE","WMT","MCD","CRM","BAC","ACN",
    "LIN","TMO","CSCO","ABT","NFLX","DHR","AMD","CMCSA","NKE","NEE",
    "TXN","PM","WFC","BMY","INTC","ORCL","RTX","QCOM","HON","UPS",
    "LOW","AMGN","SBUX","GS","INTU","ELV","MDT","CAT","DE","SPGI",
    "AXP","PLD","BLK","GILD","ADI","ISRG","VRTX","REGN","SYK","ZTS",
    "NOW","PYPL","MO","CI","MMC","DUK","SO","BDX","AON","TGT",
    "ITW","CME","ATVI","APD","GE","USB","NSC","EMR","FCX","MCO",
    "UBER","ABNB","SNOW","PLTR","CRWD","DDOG","ZS","NET","MELI","SQ"
]

NASDAQ100 = [
    "AAPL","MSFT","NVDA","AMZN","META","TSLA","GOOGL","AVGO","ADBE","COST",
    "NFLX","AMD","QCOM","INTC","INTU","CMCSA","TXN","HON","AMGN","SBUX",
    "ISRG","VRTX","REGN","GILD","PYPL","MELI","LRCX","KLAC","SNPS","CDNS",
    "ORLY","ABNB","CTAS","PAYX","ROST","FTNT","MRVL","AEP","IDXX","BIIB",
    "FAST","MRNA","DXCM","KDP","EA","CTSH","VRSK","GEHC","FANG","EXC",
    "DLTR","XEL","PCAR","CPRT","ODFL","WBA","SGEN","TEAM","ZM","SPLK",
    "CRWD","DDOG","ZS","NET","SNOW","PLTR","UBER","LCID","RIVN","CEG"
]

# Combine and deduplicate
UNIVERSE = list(set(SP500 + NASDAQ100))
print(f"Total universe: {len(UNIVERSE)} stocks")

# ── Step 1: Pre-Filter ────────────────────────────────────────
print("\nScanning market for opportunities...")
candidates = []

for i, symbol in enumerate(UNIVERSE):
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="5d")
        if hist.empty or len(hist) < 2:
            continue

        latest_close  = hist["Close"].iloc[-1]
        prev_close    = hist["Close"].iloc[-2]
        price_change  = ((latest_close - prev_close) / prev_close) * 100
        avg_volume    = hist["Volume"].mean()
        latest_volume = hist["Volume"].iloc[-1]
        volume_spike  = latest_volume / avg_volume if avg_volume > 0 else 0

        # Filter criteria — strong movers with volume confirmation
        if (abs(price_change) >= 2.0 and
            volume_spike >= 1.5 and
            latest_close >= 10):

            candidates.append({
                "symbol":       symbol,
                "price":        round(latest_close, 2),
                "change_pct":   round(price_change, 2),
                "volume_spike": round(volume_spike, 2),
                "avg_volume":   int(avg_volume)
            })

        if i % 20 == 0:
            print(f"  Scanned {i}/{len(UNIVERSE)} stocks... ({len(candidates)} candidates so far)")

    except Exception as e:
        continue

# Sort by absolute price change, take top 10
candidates = sorted(candidates, key=lambda x: abs(x["change_pct"]), reverse=True)[:10]
print(f"\nTop {len(candidates)} candidates found:")
for c in candidates:
    print(f"  {c['symbol']}: {c['change_pct']:+.2f}% | Volume spike: {c['volume_spike']}x | Price: ${c['price']}")

if not candidates:
    print("No candidates found. Try running during market hours.")
    exit()

# ── Step 2: Enrich Each Candidate ────────────────────────────
print("\nEnriching candidate data...")
enriched = []

for c in candidates:
    symbol = c["symbol"]
    try:
        ticker = yf.Ticker(symbol)

        # News headlines
        try:
            news_items = ticker.news[:3]
            news = "\n".join([
                f"- {item['content']['title']}"
                for item in news_items
            ]) if news_items else "No recent news"
        except:
            news = "News unavailable"

        # Earnings
        try:
            calendar = ticker.calendar
            earnings = str(calendar) if calendar is not None and len(calendar) > 0 else "No upcoming earnings"
        except:
            earnings = "Earnings data unavailable"

        # Basic info
        try:
            info = ticker.info
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
        print(f"  Skipping {symbol}: {e}")
        continue

# ── Step 3: Claude Analysis ───────────────────────────────────
print("\nSending candidates to Claude for analysis...")

candidate_text = ""
for c in enriched:
    candidate_text += f"""
Stock: {c['symbol']}
Price: ${c['price']} | Change: {c['change_pct']:+.2f}% | Volume Spike: {c['volume_spike']}x
Sector: {c['sector']} | Market Cap: ${c['mkt_cap']:,} | P/E: {c['pe_ratio']}
Recent News:
{c['news']}
Earnings Info:
{c['earnings']}
---"""

prompt = f"""You are an expert stock trader and options analyst. I have scanned the S&P 500 and NASDAQ 100 and found the following stocks showing unusual activity today:

{candidate_text}

For each stock, analyze whether it represents a trading opportunity. Then provide:

1. TOP 3 STOCK TRADES: Best stocks to buy or sell right now with reasoning
2. TOP 2 OPTIONS PLAYS: Best options opportunities (specify calls or puts, rough strike/expiry)
3. AVOID LIST: Any stocks that look like traps despite the movement

Format your response clearly with sections for each. For each trade include:
- Action (BUY/SELL/CALL/PUT)
- Confidence (High/Medium/Low)  
- Entry price range
- Target price
- Stop loss level
- Key reasoning in 2-3 sentences"""

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

# ── Step 4: Auto-Execute Top Signal ──────────────────────────
print("\n" + "="*60)
print("AUTO-EXECUTION (PAPER TRADING)")
print("="*60)

# Parse top BUY signal from Claude's response
top_buy = None
for c in enriched:
    if c["change_pct"] > 0 and "BUY" in analysis and c["symbol"] in analysis:
        top_buy = c["symbol"]
        break

if top_buy:
    try:
        order = MarketOrderRequest(
            symbol=top_buy,
            qty=1,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.GTC
        )
        result = trading_client.submit_order(order)
        print(f"✓ Paper trade executed: BUY 1 share of {top_buy}")
        print(f"  Order ID: {result.id}")
        print(f"  Status: {result.status}")
    except Exception as e:
        print(f"Order failed: {e}")
else:
    print("No auto-execution — no clear BUY signal found or market is closed.")

print("\nScan complete!")
