"""Formatting and exporting backtest evaluation reports."""
from typing import Dict, Any


def generate_backtest_summary_text(report: Dict[str, Any]) -> str:
    """Format human-readable backtest summary report."""
    sym = report.get("symbol", "UNKNOWN")
    total = report.get("total_trades", 0)
    wins = report.get("wins", 0)
    losses = report.get("losses", 0)
    draws = report.get("draws", 0)
    wr = report.get("win_rate", 0.0)
    max_dd_losses = report.get("max_consecutive_losses", 0)

    lines = [
        f"════════════════════════════════════════════",
        f"        BACKTEST REPORT: {sym}",
        f"════════════════════════════════════════════",
        f"Bars Evaluated:        {report.get('candles_analyzed', 0)} (M1)",
        f"Total Qualified Signals: {total}",
        f"Wins:                  {wins}",
        f"Losses:                {losses}",
        f"Draws:                 {draws}",
        f"Decisive Win Rate:     {wr}%",
        f"Max Consecutive Loss:  {max_dd_losses}",
        f"════════════════════════════════════════════"
    ]
    return "\n".join(lines)
