"""
BLACK TORNADO v1.0 adaptive composite market-intelligence engine.

Directional domains (each on [-100, 100]):
  technical = 20% trend + 15% momentum + 10% DMI direction + 5% oscillator transition.
  behavior  = 15% market structure + 10% candle pressure + 10% break/reclaim +
              5% structural rejection + 5% exhaustion/divergence + 5% closed M5 context.
BT_DIRECTION = 0.5 * technical + 0.5 * behavior.
Weights are design hypotheses, not empirically validated performance claims.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Sequence, Tuple
import math
import statistics

from app.indicators.technical import calculate_ema, calculate_rsi, calculate_macd
from app.indicators.volatility import calculate_atr, calculate_normalized_atr
from app.indicators.patterns import analyze_candle_structure
from app.indicators.dmi import calculate_dmi


def _clamp(value: float, low: float = -100.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


def _last(values: Sequence[float], default: float = 0.0) -> float:
    return float(values[-1]) if values else default


def _signed_ratio(value: float, scale: float) -> float:
    if scale <= 0:
        return 0.0
    return _clamp(100.0 * value / scale)


def _candles_valid(candles: Sequence[Dict[str, Any]]) -> bool:
    if len(candles) < 60:
        return False
    previous = None
    for c in candles:
        try:
            t, o, h, l, close = int(c['time']), float(c['open']), float(c['high']), float(c['low']), float(c['close'])
        except (KeyError, TypeError, ValueError):
            return False
        if not all(math.isfinite(x) for x in (o, h, l, close)) or h < max(o, close) or l > min(o, close) or h < l:
            return False
        if previous is not None and t <= previous:
            return False
        previous = t
    return True


def aggregate_closed_m5(m1: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Aggregate only complete, aligned 5-minute groups of closed M1 candles."""
    groups: Dict[int, List[Dict[str, Any]]] = {}
    for candle in m1:
        t = int(candle['time'])
        bucket = t - (t % 300)
        groups.setdefault(bucket, []).append(candle)
    result = []
    for bucket, bars in sorted(groups.items()):
        bars.sort(key=lambda x: int(x['time']))
        expected = [bucket + 60 * i for i in range(5)]
        if [int(x['time']) for x in bars] != expected:
            continue
        result.append({
            'time': bucket,
            'open': float(bars[0]['open']),
            'high': max(float(x['high']) for x in bars),
            'low': min(float(x['low']) for x in bars),
            'close': float(bars[-1]['close']),
        })
    return result


@dataclass(frozen=True)
class TornadoOutput:
    bt_direction: float
    bt_confidence: float
    bt_pressure: float
    bt_turbulence: float
    bt_exhaustion: float
    bt_regime: str
    bt_structure: str
    bt_sweep_reclaim: str
    bt_breakout: str
    bt_htf_alignment: str
    bt_data_ok: bool
    technical_direction: float
    behavior_direction: float
    features: Dict[str, Any]

    def snapshot(self) -> Dict[str, Any]:
        return asdict(self)


class BlackTornado:
    """Deterministic, causal composite; pass closed M1 candles and live metadata separately."""
    def __init__(self, min_history: int = 60, volatility_lookback: int = 100):
        self.min_history = min_history
        self.volatility_lookback = volatility_lookback

    def evaluate(
        self,
        candles: List[Dict[str, Any]],
        *,
        m5_candles: Optional[List[Dict[str, Any]]] = None,
        data_fresh: bool = True,
        data_timestamp: Optional[int] = None,
        now_timestamp: Optional[int] = None,
    ) -> TornadoOutput:
        if len(candles) < self.min_history or not _candles_valid(candles) or not data_fresh:
            return TornadoOutput(0, 0, 0, 100, 0, 'UNKNOWN', 'UNKNOWN', 'NONE', 'NONE', 'NEUTRAL', False, 0, 0, {'reason': 'insufficient, invalid, or stale closed-candle data'})
        if data_timestamp is not None and now_timestamp is not None and now_timestamp - data_timestamp > 10:
            return TornadoOutput(0, 0, 0, 100, 0, 'UNKNOWN', 'UNKNOWN', 'NONE', 'NONE', 'NEUTRAL', False, 0, 0, {'reason': 'data timestamp exceeds freshness limit'})

        op = [float(x['open']) for x in candles]
        hi = [float(x['high']) for x in candles]
        lo = [float(x['low']) for x in candles]
        cl = [float(x['close']) for x in candles]
        last = candles[-1]
        atrs = calculate_atr(hi, lo, cl, 14)
        if not atrs or atrs[-1] <= 0:
            return TornadoOutput(0, 0, 0, 100, 0, 'UNKNOWN', 'UNKNOWN', 'NONE', 'NONE', 'NEUTRAL', False, 0, 0, {'reason': 'ATR unavailable'})
        atr = atrs[-1]
        price = cl[-1]
        atr_bps = calculate_normalized_atr(atr, price)

        # Technical family: trend (20), momentum (15), DMI direction (10), oscillator (5).
        e9, e21, e50 = calculate_ema(cl, 9), calculate_ema(cl, 21), calculate_ema(cl, 50)
        trend_components = []
        if e9 and e21 and e50:
            trend_components.append(math.tanh((e9[-1] - e21[-1]) / max(atr, 1e-12)) * 100)
            trend_components.append(math.tanh((e21[-1] - e50[-1]) / max(2 * atr, 1e-12)) * 100)
            if len(e21) > 5:
                trend_components.append(math.tanh((e21[-1] - e21[-6]) / max(atr, 1e-12)) * 100)
        trend_score = statistics.fmean(trend_components) if trend_components else 0.0
        macd = calculate_macd(cl)
        rsi = calculate_rsi(cl, 14)
        roc = (cl[-1] - cl[-6]) / max(atr * 5, 1e-12) if len(cl) >= 6 else 0.0
        macd_hist = _last(macd.get('histogram', []))
        momentum_score = _clamp(0.6 * math.tanh(macd_hist / max(atr * 0.1, 1e-12)) * 100 + 0.4 * math.tanh(roc) * 100)
        dmi = calculate_dmi(hi, lo, cl, 14)
        plus_di, minus_di = _last(dmi['plus_di']), _last(dmi['minus_di'])
        adx = _last(dmi['adx'])
        dmi_direction = _clamp((plus_di - minus_di) * min(1.0, adx / 25.0))
        rsi_now = _last(rsi, 50.0)
        rsi_prev = rsi[-2] if len(rsi) > 1 else rsi_now
        oscillator_score = _clamp((rsi_now - 50.0) * 1.3 + (rsi_now - rsi_prev) * 2.0)
        technical = _clamp(0.40 * trend_score + 0.30 * momentum_score + 0.20 * dmi_direction + 0.10 * oscillator_score)

        # Behavior family: structure (15), candle pressure (10), breakout (10), rejection (5),
        # exhaustion (5), closed M5 context (5). Values normalized within each feature family.
        lb = min(20, len(candles) - 2)
        prior_high = max(hi[-lb-1:-1])
        prior_low = min(lo[-lb-1:-1])
        higher_high = hi[-1] > max(hi[-min(5, lb)-1:-1])
        lower_low = lo[-1] < min(lo[-min(5, lb)-1:-1])
        close_position = (cl[-1] - lo[-1]) / max(hi[-1] - lo[-1], 1e-12)
        structure = 'HH_HL' if higher_high and cl[-1] > cl[-2] else ('LH_LL' if lower_low and cl[-1] < cl[-2] else 'MIXED')
        structure_score = _clamp((1 if structure == 'HH_HL' else -1 if structure == 'LH_LL' else 0) * 65 + math.tanh((cl[-1] - cl[-6]) / max(atr * 4, 1e-12)) * 35)
        candle_info = analyze_candle_structure(last)
        body_signed = (cl[-1] - op[-1]) / max(hi[-1] - lo[-1], 1e-12)
        candle_pressure = _clamp(65 * body_signed + 35 * (2 * close_position - 1))

        broke_up = cl[-1] > prior_high
        broke_down = cl[-1] < prior_low
        sweep_up_reclaim = hi[-1] > prior_high and cl[-1] <= prior_high
        sweep_down_reclaim = lo[-1] < prior_low and cl[-1] >= prior_low
        if broke_up:
            breakout = 'UPSIDE_BREAKOUT'
            breakout_score = 75.0
        elif broke_down:
            breakout = 'DOWNSIDE_BREAKOUT'
            breakout_score = -75.0
        elif sweep_up_reclaim:
            breakout = 'FAILED_BREAKOUT'
            breakout_score = -55.0
        elif sweep_down_reclaim:
            breakout = 'FAILED_BREAKOUT'
            breakout_score = 55.0
        else:
            breakout = 'NONE'
            breakout_score = 0.0
        sweep = 'BULLISH_RECLAIM' if sweep_down_reclaim else ('BEARISH_RECLAIM' if sweep_up_reclaim else 'NONE')

        rejection_score = 0.0
        if candle_info['rejection'] == 'BULLISH_REJECTION' and cl[-1] >= cl[-2]:
            rejection_score = 80.0
        elif candle_info['rejection'] == 'BEARISH_REJECTION' and cl[-1] <= cl[-2]:
            rejection_score = -80.0

        displacement = abs(price - e21[-1]) / max(atr, 1e-12) if e21 else 0.0
        pressure_recent = [math.tanh((cl[i] - cl[i-3]) / max(atr * 2, 1e-12)) * 100 for i in range(max(3, len(cl)-8), len(cl))]
        pressure_slope = (pressure_recent[-1] - pressure_recent[0]) if len(pressure_recent) > 1 else 0.0
        exhaustion = _clamp(25 * min(3, displacement) + 0.5 * max(0, -abs(technical) + abs(technical - pressure_slope)))
        exhaustion_signed = -math.copysign(exhaustion, technical) if abs(technical) > 5 else 0.0

        m5 = m5_candles if m5_candles is not None else aggregate_closed_m5(candles)
        htf = 'NEUTRAL'
        htf_score = 0.0
        if len(m5) >= 12:
            m5close = [float(x['close']) for x in m5]
            m5e9, m5e21 = calculate_ema(m5close, 9), calculate_ema(m5close, 21)
            if m5e9 and m5e21:
                if m5e9[-1] > m5e21[-1]:
                    htf, htf_score = 'BULLISH', 100.0
                elif m5e9[-1] < m5e21[-1]:
                    htf, htf_score = 'BEARISH', -100.0

        behavior = _clamp(0.30 * structure_score + 0.20 * candle_pressure + 0.20 * breakout_score + 0.10 * rejection_score + 0.10 * exhaustion_signed + 0.10 * htf_score)
        direction = _clamp(0.5 * technical + 0.5 * behavior)

        # Volatility/turbulence are independent of direction.
        recent_ranges = [hi[i] - lo[i] for i in range(max(0, len(hi)-50), len(hi))]
        range_median = statistics.median(recent_ranges) if recent_ranges else atr
        current_range = hi[-1] - lo[-1]
        ratio = current_range / max(range_median, 1e-12)
        turbulence = _clamp(100 * min(1.0, max(0.0, (ratio - 1.0) / 3.0)))
        atr_hist = atrs[-min(self.volatility_lookback, len(atrs)):]
        atr_rank = sum(x <= atr for x in atr_hist) / max(1, len(atr_hist))
        recent_directionality = abs(sum(1 if cl[i] > cl[i-1] else -1 if cl[i] < cl[i-1] else 0 for i in range(max(1, len(cl)-12), len(cl)))) / 12
        if turbulence >= 80 or atr_bps > 55:
            regime = 'CHAOS'
        elif exhaustion >= 70:
            regime = 'REVERSAL_RISK'
        elif atr_rank <= 0.15:
            regime = 'SQUEEZE'
        elif atr_rank >= 0.85:
            regime = 'EXPANSION'
        elif abs(direction) >= 35 and adx >= 18 and recent_directionality >= 0.35:
            regime = 'TREND_UP' if direction > 0 else 'TREND_DOWN'
        elif abs(direction) < 25 and recent_directionality < 0.4:
            regime = 'RANGE'
        else:
            regime = 'UNKNOWN'

        # Consistency is not calibrated probability.
        signs = [trend_score, momentum_score, dmi_direction, structure_score, candle_pressure]
        nonzero = [1 if x > 8 else -1 if x < -8 else 0 for x in signs]
        active = [x for x in nonzero if x]
        agreement = 100 * abs(sum(active)) / len(active) if active else 0.0
        confidence = _clamp(0.65 * agreement + 0.20 * min(100, abs(direction)) + 0.15 * (100 - turbulence), 0, 100)
        features = {
            'timestamp': int(last['time']), 'price': price, 'atr': atr, 'atr_bps': atr_bps,
            'ema9': _last(e9), 'ema21': _last(e21), 'ema50': _last(e50), 'rsi14': rsi_now,
            'macd_histogram': macd_hist, 'plus_di': plus_di, 'minus_di': minus_di, 'adx': adx,
            'trend_score': trend_score, 'momentum_score': momentum_score,
            'dmi_direction': dmi_direction, 'oscillator_score': oscillator_score,
            'structure_score': structure_score, 'candle_pressure': candle_pressure,
            'prior_high': prior_high, 'prior_low': prior_low, 'atr_percentile': atr_rank * 100,
            'body_ratio': candle_info['body_ratio'], 'upper_wick_ratio': candle_info['upper_wick_ratio'],
            'lower_wick_ratio': candle_info['lower_wick_ratio'], 'displacement_atr': displacement,
            'technical_weights': {'trend': .20, 'momentum': .15, 'directional_movement': .10, 'oscillator': .05},
            'behavior_weights': {'structure': .15, 'candle_pressure': .10, 'breakout_reclaim': .10, 'rejection': .05, 'exhaustion': .05, 'closed_m5': .05},
        }
        return TornadoOutput(direction, confidence, min(100, abs(direction)), turbulence, exhaustion, regime, structure, sweep, breakout, htf, True, technical, behavior, features)


black_tornado = BlackTornado()
