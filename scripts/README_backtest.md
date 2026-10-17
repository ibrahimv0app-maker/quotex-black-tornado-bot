README: Backtest script

scripts/backtest_historical.py

Usage example:
  python scripts/backtest_historical.py --symbols EURUSD-OTC --from 2026-09-01 --to 2026-09-07

Outputs:
  - backtest_trades.csv
  - backtest_summary.json

Notes:
- Ensure your database (settings.DATABASE_URL) contains candle data in table 'candles'.
- Run with PAPER_MODE enabled to avoid sending real Telegram messages (or ensure TELEGRAM_BOT_TOKEN is unset to produce dry-run logs).
