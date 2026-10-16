"""Tests for market feed JSON parsing and symbol normalization."""
import json
from app.feed.symbol_registry import symbol_registry


def test_canonical_normalization():
    assert symbol_registry.normalize("EURUSD-OTC") == "EURUSD-OTC"
    assert symbol_registry.normalize("EURUSD-OTCq") == "EURUSD-OTC"
    assert symbol_registry.normalize("GBPUSD-OTCq") == "GBPUSD-OTC"
    assert symbol_registry.normalize("eurusd-otc") == "EURUSD-OTC"
    assert symbol_registry.normalize("UNKNOWN_PAIR") is None


def test_stream_tick_parsing():
    raw_payload = '{"symbol":"EURUSD-OTCq","timestamp":1792050374,"price":1.11228,"volume":1175848}'
    data = json.loads(raw_payload)
    assert data["symbol"] == "EURUSD-OTCq"
    assert data["timestamp"] == 1792050374
    assert data["price"] == 1.11228
    canonical = symbol_registry.normalize(data["symbol"])
    assert canonical == "EURUSD-OTC"


def test_rest_candle_parsing():
    raw_json = {
        "symbol": "EURUSD-OTC",
        "interval": "1m",
        "count": 2,
        "candles": [
            {"time": 1792050000, "open": 1.1120, "high": 1.1125, "low": 1.1118, "close": 1.1122, "volume": 1},
            {"time": 1792050060, "open": 1.1122, "high": 1.1130, "low": 1.1121, "close": 1.1129, "volume": 1}
        ]
    }
    assert len(raw_json["candles"]) == 2
    c0 = raw_json["candles"][0]
    assert c0["time"] == 1792050000
    assert c0["close"] > c0["open"]
