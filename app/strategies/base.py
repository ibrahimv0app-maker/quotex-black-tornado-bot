"""Base strategy interface and candidate signal definition."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class StrategySignal:
    strategy_name: str
    symbol: str
    direction: str  # "CALL" or "PUT"
    score: float    # 0.0 to 100.0
    reason: str
    indicators: Dict[str, Any] = field(default_factory=dict)
    confirmations: List[str] = field(default_factory=list)


class BaseStrategy(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def evaluate(
        self,
        symbol: str,
        closed_candles: List[Dict[str, Any]],
        forming_candle: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[StrategySignal]:
        """
        Evaluate candle data and return a qualified StrategySignal or None.
        Must not introduce lookahead bias.
        """
        pass
