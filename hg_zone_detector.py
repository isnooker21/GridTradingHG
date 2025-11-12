"""
Hedge zone detector based on simple supply/demand heuristics and price action confirmation.
"""

from typing import Dict, List
from datetime import datetime

from config import config


def _is_pivot_low(rates: List[Dict], index: int, pivot_lookback: int) -> bool:
    low = rates[index]['low']
    for i in range(index - pivot_lookback, index):
        if rates[i]['low'] <= low:
            return False
    for i in range(index + 1, index + 1 + pivot_lookback):
        if rates[i]['low'] < low:
            return False
    return True


def _is_pivot_high(rates: List[Dict], index: int, pivot_lookback: int) -> bool:
    high = rates[index]['high']
    for i in range(index - pivot_lookback, index):
        if rates[i]['high'] >= high:
            return False
    for i in range(index + 1, index + 1 + pivot_lookback):
        if rates[i]['high'] > high:
            return False
    return True


def _calculate_volume_ratio(rates: List[Dict], index: int, window: int = 10) -> float:
    start = max(0, index - window)
    volumes = [rate['tick_volume'] for rate in rates[start:index]]
    avg = sum(volumes) / len(volumes) if volumes else 1.0
    if avg == 0:
        return 1.0
    return rates[index]['tick_volume'] / avg


def detect_zones(atr_pips: float, profile: Dict, rates: List[Dict]) -> Dict[str, List[Dict]]:
    """
    ตรวจหา Demand/Supply zone จากข้อมูลแท่งเทียนล่าสุด
    """
    if len(rates) < profile['lookback_bars'] // 2:
        return {'buy': [], 'sell': [], 'generated_at': datetime.utcnow().timestamp()}

    zone_width_price = config.pips_to_price(max(atr_pips * profile['zone_width_factor'], 10))
    breakout_factor = config.pips_to_price(max(atr_pips, 10))

    buy_zones: List[Dict] = []
    sell_zones: List[Dict] = []

    pivot_lookback = profile['pivot_lookback']
    breakout_lookahead = profile['breakout_lookahead']
    max_index = len(rates) - breakout_lookahead - 1

    for idx in range(pivot_lookback, max_index):
        # Demand zone (pivot low + bullish breakout)
        if _is_pivot_low(rates, idx, pivot_lookback):
            base_low = min(r['low'] for r in rates[idx - pivot_lookback: idx + 1])
            base_high = max(r['high'] for r in rates[idx - pivot_lookback: idx + 1])
            zone_height = max(base_high - base_low, zone_width_price)
            breakout_high = max(r['high'] for r in rates[idx + 1: idx + 1 + breakout_lookahead])
            breakout_strength = breakout_high - base_high
            if breakout_strength > 0:
                volume_ratio = _calculate_volume_ratio(rates, idx + 1)
                score = 0.0
                score += min(1.0, breakout_strength / breakout_factor)
                score += min(1.0, volume_ratio / 2.0)
                score /= 2.0
                if score >= profile['score_threshold']:
                    zone_id = f"demand_{rates[idx]['time']}"
                    buy_zones.append({
                        'id': zone_id,
                        'lower': base_low,
                        'upper': base_low + zone_height,
                        'score': score,
                        'created_at': rates[idx]['time'],
                        'width_pips': config.price_to_pips(zone_height),
                        'type': 'buy',
                    })

        # Supply zone (pivot high + bearish breakout)
        if _is_pivot_high(rates, idx, pivot_lookback):
            base_high = max(r['high'] for r in rates[idx - pivot_lookback: idx + 1])
            base_low = min(r['low'] for r in rates[idx - pivot_lookback: idx + 1])
            zone_height = max(base_high - base_low, zone_width_price)
            breakout_low = min(r['low'] for r in rates[idx + 1: idx + 1 + breakout_lookahead])
            breakout_strength = base_low - breakout_low
            if breakout_strength > 0:
                volume_ratio = _calculate_volume_ratio(rates, idx + 1)
                score = 0.0
                score += min(1.0, breakout_strength / breakout_factor)
                score += min(1.0, volume_ratio / 2.0)
                score /= 2.0
                if score >= profile['score_threshold']:
                    zone_id = f"supply_{rates[idx]['time']}"
                    sell_zones.append({
                        'id': zone_id,
                        'upper': base_high,
                        'lower': base_high - zone_height,
                        'score': score,
                        'created_at': rates[idx]['time'],
                        'width_pips': config.price_to_pips(zone_height),
                        'type': 'sell',
                    })

    now = datetime.utcnow().timestamp()
    max_age_bars = profile['max_zone_age_bars']
    if max_age_bars > 0 and len(rates) > 1:
        latest_time = rates[-1]['time']
        time_step = rates[1]['time'] - rates[0]['time']
        cutoff = latest_time - max_age_bars * time_step
        buy_zones = [z for z in buy_zones if z['created_at'] >= cutoff]
        sell_zones = [z for z in sell_zones if z['created_at'] >= cutoff]

    return {
        'buy': buy_zones,
        'sell': sell_zones,
        'generated_at': now,
    }


