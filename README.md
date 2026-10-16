# Quotex M1 Signal Bot (Railway 24/7 Production Engine)

A production-grade, asynchronous quantitative trading signal bot engineered specifically for Quotex 1-minute (M1) OTC binary pairs, deployed as a persistent 24/7 service on Railway.

> **Crucial Disclaimer**: This application is strictly an informational and quantitative signal generation system. It does **not** execute automated trades, does not store broker account passwords, and evaluates outcomes transparently against live market-data streams without fabricated win rates or repainting.

---

## Architecture Overview

```
                      ┌──────────────────────────────────────┐
                      │    Quotex Public Feed API            │
                      │    https://quotexfeed.lovable.app     │
                      └───────────────┬──────────────────────┘
                                      │ REST Candles (History)
                                      │ Multi-Worker SSE/WS (Ticks)
                                      ▼
                      ┌──────────────────────────────────────┐
                      │    Async Feed Manager (In-Memory)    │
                      │    - Tick Normalization (-OTCq -> OTC)│
                      │    - Candle Aggregator (M1 Bars)     │
                      │    - Data Freshness & Health Monitor │
                      └───────────────┬──────────────────────┘
                                      │
            ┌─────────────────────────┴─────────────────────────┐
            ▼                                                   ▼
┌───────────────────────────┐                       ┌───────────────────────────┐
│     5 Trading Strategies  │                       │   Regime & Quality Filter │
│ 1. Trend Pullback (EMA/RSI│                       │ - Normalized ATR (NATR)   │
│ 2. Momentum Continuation  │                       │ - Rejection Wick Analysis │
│ 3. Range Mean Reversion   │                       │ - Stale Tick Quarantine   │
│ 4. Support/Resistance S/R │                       │ - Multi-Timeframe M1/M5   │
│ 5. Squeeze Breakout (BB)  │                       └─────────────┬─────────────┘
└─────────────┬─────────────┘                                     │
              └───────────────────────┬───────────────────────────┘
                                      ▼
                      ┌──────────────────────────────────────┐
                      │ Volatility-Aware Candidate Scorer    │
                      │ - Evaluates All Active Pairs Every 1s│
                      │ - Ranks 0–100 Setup Composite Score  │
                      │ - Selects at most ONE Winner (>=75)  │
                      └───────────────┬──────────────────────┘
                                      │
                                      ▼
                      ┌──────────────────────────────────────┐
                      │ Precision Clock Scheduler (:45s-:50s)│
                      │ - Target Entry: :00s boundary        │
                      │ - Lead Time: 10–15s prior to entry   │
                      │ - Atomic DB Lock (One-Signal Lock)   │
                      └───────┬──────────────────────┬───────┘
                              │                      │
             CALL / PUT Alert │                      │ Settlement at Expiry
                              ▼                      ▼
               ┌──────────────────────┐    ┌─────────────────────────┐
               │ Telegram Dispatcher  │    │ 1-Minute Outcome Tracker│
               │ (HTML Format, PKT tz)│    │ - Captures Entry Quote  │
               └──────────────────────┘    │ - Captures Expiry Quote │
                                           │ - WIN / LOSS / DRAW /   │
                                           │   UNVERIFIED            │
                                           │ - Releases DB Lock      │
                                           └─────────────────────────┘
```

---

## 1. Verified Market Data API Findings

Prior to implementation, the live data endpoints at `https://quotexfeed.lovable.app` were tested and empirically verified:

1. **REST Candles (`GET /api/public/candles?symbol={sym}&interval=1m&limit=2001`)**:
   - Accepts canonical symbol names like `EURUSD-OTC`.
   - Rejects the `q` suffix (e.g. `EURUSD-OTCq` returns HTTP 400 `Unknown symbol`).
   - Timestamps are integer Unix seconds spaced strictly 60 seconds apart.
   - Tested 48 documented pairs: 39 return active continuous candle history, while 9 equity OTC symbols (`AXP-OTC`, `BOI-OTC`, `FB-OTC`, `INT-OTC`, `JNJ-OTC`, `MCD-OTC`, `MSFT-OTC`, `BTC-OTC`, `EURSGD-OTC`) currently return 0 bars and are automatically filtered into quarantine until populated.

2. **Real-time Live Tick Stream (`GET /api/public/stream?symbols=...`)**:
   - Transmits Server-Sent Events (SSE) with `Content-Type: text/event-stream`.
   - The stream transmits ticks with a trailing alias suffix (e.g., `EURUSD-OTCq`).
   - The bot features an automated **Canonical Symbol Normalizer** (`symbol_registry.py`) that maps ticks back to their canonical identifiers before candle aggregation.
   - Stream connections are divided into manageable worker pools (maximum 8 symbols per stream) to prevent packet congestion.

---

## 2. Five Independent Trading Strategies

Each strategy operates as an isolated, testable quantitative module without indicator overlap:

1. **Strategy A — Trend Pullback**:
   - Detects alignment between EMA 9, EMA 21, and EMA 50.
   - Triggers when price pulls back to the EMA 9 dynamic zone during a verified trend with RSI between 40 and 65 (bullish) or 35 and 60 (bearish).
2. **Strategy B — Momentum Continuation**:
   - Confirms directional impulse using MACD Line crossing Signal line and positive/negative Histogram expansion.
   - Validates recent candle body size against local ATR to reject exhausted impulses.
3. **Strategy C — Range Mean Reversion**:
   - Deploys Bollinger Bands (20 period, 2.0 deviation) and RSI extremes (< 28 or > 72).
   - Requires price rejection at the band extreme (lower/upper shadow > 35% of total bar range).
4. **Strategy D — Support/Resistance Rejection**:
   - Scans trailing 30 bars for swing highs and swing lows.
   - Enforces pinbar / engulfing rejection patterns occurring within 0.05% of the key structural level.
5. **Strategy E — Volatility Squeeze Breakout**:
   - Computes Bollinger Band Width percentile over 30 bars.
   - Requires band expansion coupled with high directional close outside the bandwidth.

---

## 3. Global Selection, Lead Timing & Signal Lock

- **Evaluation Frequency**: Evaluates all healthy pairs every second.
- **Lead Window Timing**: For an entry scheduled at `HH:MM:00`, the bot evaluates candidates between `:45s` and `:50s` of the previous minute (10 to 15 seconds lead time).
- **Setup Scoring**: Candidates are scored on a scale of 0 to 100 based on setup quality, trend alignment, and normalized volatility (NATR). Only candidates meeting or exceeding `MIN_SETUP_SCORE` (default `75.0`) are eligible.
- **One-Signal Lock**: The system enforces a strict persistent global lock in PostgreSQL (or SQLite). While a signal is active throughout its 1-minute lifecycle, **no new signals can be generated** across any pair.
- **Honest Outcome Tracking**: At `:00s` of the entry and `:00s` of expiry, exact quotes are captured. If feed latency delays the tick beyond tolerance, the signal is honestly marked `UNVERIFIED` rather than guessing a win/loss.

---

## 4. Telegram Notification Templates

### Signal Alert (Sent ~12s before entry)
```
🚨 QUOTEX M1 SIGNAL | #M1_1792050900_EURUSD

Pair: EURUSD-OTC
Direction: CALL 🟢
Timeframe: 1 Minute
Expiry: 1 Minute

📍 Intended Entry: 17:15:00 PKT
⏳ Signal Sent: 17:14:48 PKT
⌛ Expiry Time: 17:16:00 PKT

Setup Score: 82.5/100
Strategy: Trend Pullback
Data Status: Fresh

Confirmation:
• M1 EMA alignment confirmed
• Healthy pullback to EMA9 zone
• Stable ATR volatility

⚠️ Manual entry only. Ranking score is not a guaranteed win probability. Outcome evaluated automatically via market data stream.
```

### Result Notification (Sent at 1-minute expiry)
```
📊 SIGNAL RESULT | #M1_1792050900_EURUSD

Pair: EURUSD-OTC
Direction: CALL
Expiry: 1 Minute

Outcome: ✅ WIN — FEED-ESTIMATED
Entry Quote: 1.11200
Expiry Quote: 1.11235
Price Movement: +0.00035

Entry Time: 17:15:00 PKT
Expiry Time: 17:16:00 PKT
Strategy: Trend Pullback

Note: Feed-estimated result; not independently confirmed against Quotex trade record.
```

---

## 5. Local Setup & Testing

### Prerequisites
- Python 3.10+
- Git

### 1. Clone & Install Dependencies
```bash
git clone https://github.com/YOUR_USERNAME/quotex-m1-signal-bot.git
cd quotex-m1-signal-bot
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID
```

### 3. Run Automated Tests
```bash
pytest tests/ -v
```

### 4. Run Diagnostics CLI
```bash
# Discover live pair status and REST latencies:
python diagnostic.py

# Run chronological backtest on historical candles:
python diagnostic.py backtest EURUSD-OTC
```

### 5. Start the Application Locally
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## 6. Railway 24/7 Deployment Guide

### Step 1: Push Code to GitHub
1. Create a new private repository on GitHub (e.g. `quotex-m1-signal-bot`).
2. Run in your terminal:
   ```bash
   git init
   git add .
   git commit -m "feat: complete production Quotex M1 signal bot"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/quotex-m1-signal-bot.git
   git push -u origin main
   ```

### Step 2: Create a Project on Railway
1. Log in to [Railway](https://railway.app/).
2. Click **+ New Project** -> **Deploy from GitHub repo**.
3. Select your `quotex-m1-signal-bot` repository.

### Step 3: Add PostgreSQL Database
1. In your Railway project canvas, click **+ New** -> **Database** -> **Add PostgreSQL**.
2. Railway creates a managed PostgreSQL instance and automatically exposes `DATABASE_URL`.

### Step 4: Configure Variables in Railway
Navigate to your service's **Variables** tab and set:
| Variable Name | Recommended Value | Description |
| :--- | :--- | :--- |
| `API_BASE_URL` | `https://quotexfeed.lovable.app` | Market data URL |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` | Auto-linked Railway PostgreSQL |
| `TELEGRAM_BOT_TOKEN` | *Your bot token from @BotFather* | Telegram Bot API Token |
| `TELEGRAM_CHAT_ID` | `-1003501100081` | Destination chat or channel ID |
| `DISPLAY_TIMEZONE` | `Asia/Karachi` | Local timezone in alerts |
| `MIN_SETUP_SCORE` | `75.0` | Minimum score to publish |
| `SIGNAL_LEAD_SECONDS`| `12` | Dispatch lead window |
| `EXPIRY_SECONDS` | `60` | Trade expiry |
| `KILL_SWITCH_ACTIVE` | `false` | Emergency kill switch |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

### Step 5: Verification & Endpoints
Once Railway builds the Docker image and reports "Active":
- `GET /health`: Health check report, worker counts, uptime.
- `GET /health/feeds`: Live tick freshness and candle counts for all pairs.
- `GET /stats`: Real-time win rate, total signals, win/loss/draw breakdown.
- `POST /kill-switch/toggle`: Instantly pause or resume signals without restart.
