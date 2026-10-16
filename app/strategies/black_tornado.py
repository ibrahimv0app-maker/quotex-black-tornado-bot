"""Twenty-five independently identified BLACK TORNADO strategy hypotheses.
Each module consumes the common composite outputs; no module recalculates indicators.
Rules are initial engineering hypotheses, not validated trading edge.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from app.strategies.base import BaseStrategy, StrategySignal
from app.indicators.black_tornado import TornadoOutput, black_tornado


SPECS = [
 ('BT01','TORNADO_IGNITION',{'RANGE','SQUEEZE','EXPANSION'}),
 ('BT02','MAIN_TORNADO_TREND',{'TREND_UP','TREND_DOWN'}),
 ('BT03','ADAPTIVE_PULLBACK',{'TREND_UP','TREND_DOWN'}),
 ('BT04','SHALLOW_RETRACEMENT',{'TREND_UP','TREND_DOWN'}),
 ('BT05','STORM_ACCELERATION',{'TREND_UP','TREND_DOWN','EXPANSION'}),
 ('BT06','FRESH_STRUCTURE_BREAKOUT',{'EXPANSION','TREND_UP','TREND_DOWN'}),
 ('BT07','BREAKOUT_RETEST',{'TREND_UP','TREND_DOWN','EXPANSION'}),
 ('BT08','SQUEEZE_RELEASE',{'SQUEEZE','EXPANSION'}),
 ('BT09','FIRST_IMPULSE_AFTER_COMPRESSION',{'EXPANSION'}),
 ('BT10','M5_M1_ALIGNMENT',{'TREND_UP','TREND_DOWN','EXPANSION'}),
 ('BT11','SWEEP_AND_RECLAIM',{'RANGE','REVERSAL_RISK'}),
 ('BT12','FAILED_BREAKOUT_TRAP',{'RANGE','REVERSAL_RISK'}),
 ('BT13','STRUCTURAL_WICK_REJECTION',{'RANGE','REVERSAL_RISK'}),
 ('BT14','EXHAUSTION_DIVERGENCE',{'REVERSAL_RISK','RANGE'}),
 ('BT15','OVEREXTENSION_SNAPBACK',{'RANGE','REVERSAL_RISK'}),
 ('BT16','RANGE_FLOOR_BOUNCE',{'RANGE'}),
 ('BT17','RANGE_CEILING_FADE',{'RANGE'}),
 ('BT18','MEAN_REVERSION_RETURN',{'RANGE'}),
 ('BT19','DOUBLE_SWEEP_TRAP',{'RANGE','REVERSAL_RISK'}),
 ('BT20','FAILED_CONTINUATION_FLIP',{'REVERSAL_RISK','RANGE'}),
 ('BT21','SPIKE_COOLDOWN_CONTINUATION',{'TREND_UP','TREND_DOWN','EXPANSION'}),
 ('BT22','SPIKE_EXHAUSTION_REVERSAL',{'REVERSAL_RISK'}),
 ('BT23','CANDLE_PRESSURE_SEQUENCE',{'TREND_UP','TREND_DOWN','EXPANSION'}),
 ('BT24','TREND_TO_RANGE_TRANSITION',{'RANGE','REVERSAL_RISK'}),
 ('BT25','RANGE_TO_TREND_TRANSITION',{'TREND_UP','TREND_DOWN','EXPANSION'}),
]


def _trigger(i: int, o: TornadoOutput) -> Optional[str]:
    f=o.features; d=o.bt_direction; p=o.bt_pressure; ex=o.bt_exhaustion; turb=o.bt_turbulence
    if not o.bt_data_ok or o.bt_regime in {'CHAOS','UNKNOWN'} or turb >= 80: return None
    bullish=d >= 25; bearish=d <= -25
    strong_up=d >= 40 and p >= 35; strong_dn=d <= -40 and p >= 35
    up = bullish; dn = bearish
    # These definitions are deliberately explicit and symmetric where appropriate.
    checks = {
      1: (o.bt_regime in {'RANGE','SQUEEZE','EXPANSION'} and o.bt_breakout=='UPSIDE_BREAKOUT' and strong_up and f['displacement_atr']<2.5, 'CALL'),
      2: (o.bt_regime=='TREND_UP' and strong_up and o.bt_structure=='HH_HL', 'CALL') if d>0 else (o.bt_regime=='TREND_DOWN' and strong_dn and o.bt_structure=='LH_LL','PUT'),
      3: (o.bt_regime=='TREND_UP' and up and f['displacement_atr']<1.4 and f['lower_wick_ratio']>=.25 and f['candle_pressure']>0,'CALL') if d>0 else (o.bt_regime=='TREND_DOWN' and dn and f['displacement_atr']<1.4 and f['upper_wick_ratio']>=.25 and f['candle_pressure']<0,'PUT'),
      4: (o.bt_regime=='TREND_UP' and up and o.bt_structure=='HH_HL' and f['candle_pressure']>8,'CALL') if d>0 else (o.bt_regime=='TREND_DOWN' and dn and o.bt_structure=='LH_LL' and f['candle_pressure']<-8,'PUT'),
      5: (o.bt_regime in {'TREND_UP','EXPANSION'} and strong_up and f['momentum_score']>20 and f['displacement_atr']<2,'CALL') if d>0 else (o.bt_regime in {'TREND_DOWN','EXPANSION'} and strong_dn and f['momentum_score']<-20 and f['displacement_atr']<2,'PUT'),
      6: (o.bt_breakout=='UPSIDE_BREAKOUT' and strong_up,'CALL') if d>0 else (o.bt_breakout=='DOWNSIDE_BREAKOUT' and strong_dn,'PUT'),
      7: (o.bt_regime in {'TREND_UP','EXPANSION'} and up and f['price']>=f['prior_high']*.9995 and f['candle_pressure']>0,'CALL') if d>0 else (o.bt_regime in {'TREND_DOWN','EXPANSION'} and dn and f['price']<=f['prior_low']*1.0005 and f['candle_pressure']<0,'PUT'),
      8: (o.bt_regime=='EXPANSION' and strong_up and o.bt_breakout=='UPSIDE_BREAKOUT' and turb<70,'CALL') if d>0 else (o.bt_regime=='EXPANSION' and strong_dn and o.bt_breakout=='DOWNSIDE_BREAKOUT' and turb<70,'PUT'),
      9: (o.bt_regime=='EXPANSION' and strong_up and f['candle_pressure']>35 and f['displacement_atr']<1.8,'CALL') if d>0 else (o.bt_regime=='EXPANSION' and strong_dn and f['candle_pressure']<-35 and f['displacement_atr']<1.8,'PUT'),
      10: (o.bt_htf_alignment=='BULLISH' and up and f['candle_pressure']>0,'CALL') if d>0 else (o.bt_htf_alignment=='BEARISH' and dn and f['candle_pressure']<0,'PUT'),
      11: (o.bt_sweep_reclaim=='BULLISH_RECLAIM' and d>10 and f['candle_pressure']>0,'CALL') if o.bt_sweep_reclaim=='BULLISH_RECLAIM' else (o.bt_sweep_reclaim=='BEARISH_RECLAIM' and d<-10 and f['candle_pressure']<0,'PUT'),
      12: (o.bt_breakout=='FAILED_BREAKOUT' and d>15 and f['candle_pressure']>0,'CALL') if o.bt_breakout=='FAILED_BREAKOUT' and d>0 else (o.bt_breakout=='FAILED_BREAKOUT' and d<-15 and f['candle_pressure']<0,'PUT'),
      13: (o.bt_structure in {'HH_HL','MIXED'} and f['lower_wick_ratio']>.55 and d>10 and f['candle_pressure']>10,'CALL') if f['lower_wick_ratio']>.55 else (o.bt_structure in {'LH_LL','MIXED'} and f['upper_wick_ratio']>.55 and d<-10 and f['candle_pressure']<-10,'PUT'),
      14: (o.bt_regime in {'REVERSAL_RISK','RANGE'} and ex>=55 and d>10 and f['momentum_score']>0,'CALL') if d>0 else (o.bt_regime in {'REVERSAL_RISK','RANGE'} and ex>=55 and d<-10 and f['momentum_score']<0,'PUT'),
      15: (o.bt_regime in {'RANGE','REVERSAL_RISK'} and ex>=55 and f['displacement_atr']>=1.8 and d>12 and f['candle_pressure']>0,'CALL') if d>0 else (o.bt_regime in {'RANGE','REVERSAL_RISK'} and ex>=55 and f['displacement_atr']>=1.8 and d<-12 and f['candle_pressure']<0,'PUT'),
      16: (o.bt_regime=='RANGE' and f['price']<=f['prior_low']+0.25*f['atr'] and f['lower_wick_ratio']>.4 and d>10,'CALL'),
      17: (o.bt_regime=='RANGE' and f['price']>=f['prior_high']-0.25*f['atr'] and f['upper_wick_ratio']>.4 and d<-10,'PUT'),
      18: (o.bt_regime=='RANGE' and f['displacement_atr']>=1.5 and d>15 and f['candle_pressure']>0,'CALL') if d>0 else (o.bt_regime=='RANGE' and f['displacement_atr']>=1.5 and d<-15 and f['candle_pressure']<0,'PUT'),
      19: (o.bt_sweep_reclaim=='BULLISH_RECLAIM' and d>20 and f['lower_wick_ratio']>.35,'CALL') if o.bt_sweep_reclaim=='BULLISH_RECLAIM' else (o.bt_sweep_reclaim=='BEARISH_RECLAIM' and d<-20 and f['upper_wick_ratio']>.35,'PUT'),
      20: (o.bt_regime=='REVERSAL_RISK' and d>20 and f['structure_score']>20 and f['momentum_score']>0,'CALL') if d>0 else (o.bt_regime=='REVERSAL_RISK' and d<-20 and f['structure_score']<-20 and f['momentum_score']<0,'PUT'),
      21: (o.bt_regime in {'TREND_UP','EXPANSION'} and o.bt_turbulence<45 and strong_up and o.bt_structure=='HH_HL','CALL') if d>0 else (o.bt_regime in {'TREND_DOWN','EXPANSION'} and o.bt_turbulence<45 and strong_dn and o.bt_structure=='LH_LL','PUT'),
      22: (o.bt_regime=='REVERSAL_RISK' and ex>=60 and o.bt_sweep_reclaim=='BULLISH_RECLAIM' and d>10,'CALL') if o.bt_sweep_reclaim=='BULLISH_RECLAIM' else (o.bt_regime=='REVERSAL_RISK' and ex>=60 and o.bt_sweep_reclaim=='BEARISH_RECLAIM' and d<-10,'PUT'),
      23: (o.bt_regime in {'TREND_UP','EXPANSION'} and f['candle_pressure']>30 and d>25 and p>=30,'CALL') if d>0 else (o.bt_regime in {'TREND_DOWN','EXPANSION'} and f['candle_pressure']<-30 and d<-25 and p>=30,'PUT'),
      24: (o.bt_regime in {'RANGE','REVERSAL_RISK'} and abs(d)<45 and ex>=35 and o.bt_structure=='MIXED','CALL' if d>=0 else 'PUT'),
      25: (o.bt_regime in {'TREND_UP','EXPANSION'} and o.bt_breakout=='UPSIDE_BREAKOUT' and strong_up,'CALL') if d>0 else (o.bt_regime in {'TREND_DOWN','EXPANSION'} and o.bt_breakout=='DOWNSIDE_BREAKOUT' and strong_dn,'PUT'),
    }
    ok, side = checks[i]
    return side if ok else None


class BlackTornadoStrategy(BaseStrategy):
    def __init__(self, strategy_id: str, name: str, regimes: set[str]):
        super().__init__(f'{strategy_id} — {name}')
        self.strategy_id, self.strategy_name, self.regimes = strategy_id, name, regimes
        self.index = int(strategy_id[2:])

    def evaluate(self, symbol: str, closed_candles: List[Dict[str, Any]], forming_candle=None, context=None) -> Optional[StrategySignal]:
        context = context or {}
        output = context.get('tornado')
        if output is None:
            output = black_tornado.evaluate(closed_candles, data_fresh=context.get('data_fresh', True), data_timestamp=context.get('data_timestamp'), now_timestamp=context.get('now_timestamp'))
        if not isinstance(output, TornadoOutput) or output.bt_regime not in self.regimes:
            return None
        direction = _trigger(self.index, output)
        if not direction:
            return None
        score = min(100.0, 55 + abs(output.bt_direction)*0.25 + output.bt_confidence*0.15 + max(0, 35-output.bt_turbulence)*0.15)
        confirmations = [f"BT direction {output.bt_direction:+.0f}", f"Regime {output.bt_regime}", f"Structure {output.bt_structure}"]
        if output.bt_htf_alignment != 'NEUTRAL': confirmations.append(f"Closed M5 context {output.bt_htf_alignment}")
        return StrategySignal(self.name, symbol, direction, score, f"{self.strategy_id} trigger satisfied; feed-only price behavior", output.snapshot(), confirmations)


# Concrete independent strategy classes for transparent discovery and testability.
def _make_class(spec, idx):
    sid, name, regimes = spec
    return type(name.title().replace('_','') + 'Strategy', (BlackTornadoStrategy,), {
        '__init__': lambda self, _sid=sid, _name=name, _regimes=regimes: BlackTornadoStrategy.__init__(self, _sid, _name, _regimes)
    })

STRATEGIES = [_make_class(spec, i) for i, spec in enumerate(SPECS, 1)]

def build_strategies():
    return [cls() for cls in STRATEGIES]
