"""Directional Movement Index (+DI, -DI, ADX) calculations."""
import math
from typing import List, Dict, Any, Tuple


def calculate_dmi(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    period: int = 14
) -> Dict[str, List[float]]:
    """
    Calculate True Range, +DI, -DI, DX and ADX (Wilder's smoothing).
    Returns dict with keys: plus_di, minus_di, adx
    """
    n = len(closes)
    if n < period + 2:
        return {"plus_di": [], "minus_di": [], "adx": []}

    tr_list = []
    plus_dm_list = []
    minus_dm_list = []

    for i in range(1, n):
        h = highs[i]
        l = lows[i]
        prev_c = closes[i - 1]
        prev_h = highs[i - 1]
        prev_l = lows[i - 1]

        # True Range
        tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
        tr_list.append(tr)

        # Directional Movement
        up_move = h - prev_h
        down_move = prev_l - l

        if up_move > down_move and up_move > 0:
            plus_dm_list.append(up_move)
        else:
            plus_dm_list.append(0.0)

        if down_move > up_move and down_move > 0:
            minus_dm_list.append(down_move)
        else:
            minus_dm_list.append(0.0)

    # Initial sums
    smooth_tr = sum(tr_list[:period])
    smooth_plus_dm = sum(plus_dm_list[:period])
    smooth_minus_dm = sum(minus_dm_list[:period])

    plus_di = []
    minus_di = []
    dx_list = []

    def get_di(p_dm: float, m_dm: float, tr_val: float) -> Tuple[float, float, float]:
        if tr_val <= 0:
            return 0.0, 0.0, 0.0
        p_di = (p_dm / tr_val) * 100.0
        m_di = (m_dm / tr_val) * 100.0
        di_sum = p_di + m_di
        dx = (abs(p_di - m_di) / di_sum * 100.0) if di_sum > 0 else 0.0
        return p_di, m_di, dx

    p_di, m_di, dx = get_di(smooth_plus_dm, smooth_minus_dm, smooth_tr)
    plus_di.append(p_di)
    minus_di.append(m_di)
    dx_list.append(dx)

    for i in range(period, len(tr_list)):
        smooth_tr = smooth_tr - (smooth_tr / period) + tr_list[i]
        smooth_plus_dm = smooth_plus_dm - (smooth_plus_dm / period) + plus_dm_list[i]
        smooth_minus_dm = smooth_minus_dm - (smooth_minus_dm / period) + minus_dm_list[i]

        p_di, m_di, dx = get_di(smooth_plus_dm, smooth_minus_dm, smooth_tr)
        plus_di.append(p_di)
        minus_di.append(m_di)
        dx_list.append(dx)

    # Calculate ADX from DX series
    if len(dx_list) < period:
        adx_list = [sum(dx_list) / len(dx_list)] if dx_list else []
    else:
        adx_val = sum(dx_list[:period]) / period
        adx_list = [adx_val]
        for i in range(period, len(dx_list)):
            adx_val = (adx_val * (period - 1) + dx_list[i]) / period
            adx_list.append(adx_val)

    return {
        "plus_di": plus_di,
        "minus_di": minus_di,
        "adx": adx_list
    }
