"""Symbol registry and canonical symbol normalizer."""
from typing import Dict, Set, Optional

# Canonical list of 48 OTC pairs documented by the Quotex feed API
DEFAULT_CANONICAL_SYMBOLS = [
    "AUDCAD-OTC", "AUDCHF-OTC", "AUDJPY-OTC", "AUDNZD-OTC", "AUDUSD-OTC", "BRLUSD-OTC",
    "CADCHF-OTC", "CADJPY-OTC", "CHFJPY-OTC", "EURAUD-OTC", "EURCAD-OTC", "EURCHF-OTC",
    "EURGBP-OTC", "EURJPY-OTC", "EURNZD-OTC", "EURSGD-OTC", "EURUSD-OTC", "GBPAUD-OTC",
    "GBPCAD-OTC", "GBPCHF-OTC", "GBPJPY-OTC", "GBPNZD-OTC", "GBPUSD-OTC", "NZDCAD-OTC",
    "NZDCHF-OTC", "NZDJPY-OTC", "NZDUSD-OTC", "USDARS-OTC", "USDBDT-OTC", "USDCAD-OTC",
    "USDCHF-OTC", "USDCOP-OTC", "USDDZD-OTC", "USDEGP-OTC", "USDIDR-OTC", "USDINR-OTC",
    "USDJPY-OTC", "USDMXN-OTC", "USDPKR-OTC", "USDZAR-OTC", "AXP-OTC", "BOI-OTC",
    "FB-OTC", "INT-OTC", "JNJ-OTC", "MCD-OTC", "MSFT-OTC", "BTC-OTC"
]


class SymbolRegistry:
    def __init__(self, canonical_symbols=None):
        self._canonical: Set[str] = set(canonical_symbols or DEFAULT_CANONICAL_SYMBOLS)
        self._alias_map: Dict[str, str] = {}
        # Prepopulate known stream aliases (e.g. 'EURUSD-OTCq' -> 'EURUSD-OTC')
        for sym in self._canonical:
            self._alias_map[f"{sym}q"] = sym
            self._alias_map[sym.lower()] = sym
            self._alias_map[f"{sym.lower()}q"] = sym

    def normalize(self, raw_symbol: str) -> Optional[str]:
        """Convert raw/stream symbol to canonical API symbol."""
        if not raw_symbol:
            return None
        raw_clean = raw_symbol.strip()
        if raw_clean in self._canonical:
            return raw_clean
        if raw_clean in self._alias_map:
            return self._alias_map[raw_clean]
        # Check stripping trailing 'q'
        if raw_clean.endswith("q") and raw_clean[:-1] in self._canonical:
            self._alias_map[raw_clean] = raw_clean[:-1]
            return raw_clean[:-1]
        return None

    def is_canonical(self, symbol: str) -> bool:
        return symbol in self._canonical

    def get_all_canonical(self) -> Set[str]:
        return set(self._canonical)


symbol_registry = SymbolRegistry()
