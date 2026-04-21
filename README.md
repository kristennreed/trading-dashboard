# AI Market Scanner & Trading Dashboard

An automated AI-powered stock trading system that scans the S&P 500 and NASDAQ 100 daily, generates buy/sell signals using Claude AI, and executes paper trades through Alpaca's brokerage API. Built in Python with a Streamlit web dashboard accessible from any device.

---

## What This Does

This system runs a full trading pipeline automatically every weekday:

1. **Scans** the S&P 500 and NASDAQ 100 for unusual price and volume activity
2. **Enriches** each candidate with news sentiment, earnings dates, sector data, and market context
3. **Analyzes** all candidates using Claude AI and ranks them by opportunity quality
4. **Presents** the top opportunities on a web dashboard with approve/skip buttons
5. **Executes** approved trades via Alpaca's paper trading API
6. **Monitors** open positions every 15 minutes and auto-sells at target or stop loss

---

## Repository Structure

```
trading-dashboard/
│
├── scanner.py          # Market scanner — runs at 9:30am CT daily
├── monitor.py          # Position monitor — runs every 15 min during market hours
├── dashboard.py        # Streamlit web dashboard — approve/skip trades, view P&L
├── signals.json        # Auto-generated — stores today's trading signals
├── trade_log.txt       # Auto-generated — full log of all monitor activity
├── requirements.txt    # Python package dependencies
└── README.md           # This file
```

---

## How Each Script Works

### `scanner.py` — The Brain
Runs automatically at 9:30am CT every weekday via cron scheduler.

- Loads a universe of ~136 stocks from the S&P 500 and NASDAQ 100
- Pre-filters using Python for stocks with 2%+ price movement and 1.5x+ volume spike
- Enriches each candidate with news headlines, earnings calendar, sector, P/E ratio, and market cap via yfinance
- Pulls broader market context (SPY, QQQ, XLK) from Alpaca
- Sends all enriched candidates to Claude AI for deep analysis
- Claude returns ranked opportunities with entry price, target, stop loss, and reasoning
- Saves top signals to `signals.json` for the dashboard to read

### `monitor.py` — The Risk Manager
Runs automatically at 8:30am CT every weekday and checks positions every 15 minutes.

- Connects to your Alpaca paper trading account
- Checks every open position against its target price and stop loss level
- Auto-sells when take profit is hit (default: +8%) to lock in gains
- Auto-sells when stop loss is hit (default: -5%) to limit losses
- Uses signal-specific targets from `signals.json` when available
- Logs every decision to `trade_log.txt` with timestamps

### `dashboard.py` — The Control Center
A Streamlit web app you can open in any browser or on your iPhone.

- Shows live account balance, buying power, and cash
- Displays all open positions with real-time P&L
- Lists today's AI-generated opportunities with full Claude reasoning
- Approve button executes the trade immediately via Alpaca
- Skip button dismisses the signal
- Tabs for All Signals, Pending Approval, and Executed trades
- Refresh button to pull latest signals

---

## Data Sources

| Source | What It Provides | Cost |
|--------|-----------------|------|
| Alpaca API | Real-time prices, trade execution, account data | Free |
| yfinance | News headlines, earnings dates, fundamentals | Free |
| Anthropic Claude | AI analysis and signal generation | Pay per use (~$0.01/scan) |
| SPY / QQQ / XLK | Broader market context via Alpaca | Free |

---

## Signal Filtering Criteria

The pre-filter looks for stocks that meet ALL of the following:

- Price moved **2% or more** in the last trading day
- Volume was **1.5x or higher** than the 5-day average
- Stock price is **above $10** (filters out penny stocks)

This typically narrows 136 stocks down to 5-15 high-quality candidates per day.

---

## Risk Controls

| Control | Default | Description |
|---------|---------|-------------|
| Take profit | +8% | Auto-sells when position gains 8% |
| Stop loss | -5% | Auto-sells when position loses 5% |
| Signal targets | Variable | Uses Claude's specific price targets when available |
| Paper trading | Enabled | All trades execute in paper mode by default |

---

## Automation Schedule (Mac Cron)

```
8:30am CT (Mon-Fri)   →  monitor.py starts up
9:30am CT (Mon-Fri)   →  scanner.py runs full market scan
Every 15 minutes      →  monitor.py checks all open positions
```

---

## Tech Stack

- **Python 3.11**
- **Streamlit** — web dashboard UI
- **alpaca-py** — brokerage API for data and trade execution
- **yfinance** — market data, news, earnings
- **anthropic** — Claude AI for signal analysis
- **pandas** — data processing

---

## Setup Instructions

### 1. Clone the repository
```bash
git clone https://github.com/yourusername/trading-dashboard.git
cd trading-dashboard
```

### 2. Install dependencies
```bash
python3.11 -m pip install -r requirements.txt
```

### 3. Add your API keys
Open each script and replace the placeholder values:
```python
ALPACA_API_KEY    = "YOUR_ALPACA_KEY"
ALPACA_SECRET_KEY = "YOUR_ALPACA_SECRET"
ANTHROPIC_API_KEY = "YOUR_ANTHROPIC_KEY"
```

> **Important:** Never commit real API keys to GitHub. Use environment variables in production.

### 4. Run the dashboard
```bash
python3.11 -m streamlit run dashboard.py
```

### 5. Run the scanner manually
```bash
python3.11 scanner.py
```

### 6. Run the position monitor
```bash
python3.11 monitor.py
```

---

## Roadmap

- [ ] Email and SMS alerts when trades execute or stop loss triggers
- [ ] Options trading signals (calls and puts)
- [ ] Expanded stock universe (Russell 1000)
- [ ] Automated deployment to PythonAnywhere for always-on operation
- [ ] Mobile-optimized dashboard UI
- [ ] Performance analytics and trade history charts
- [ ] Multiple portfolio strategies running simultaneously

---

## Disclaimer

This system is for educational and paper trading purposes only. It is not financial advice. All trades execute in paper trading mode by default. Past performance of signals does not guarantee future results. Always do your own research before trading with real money.
