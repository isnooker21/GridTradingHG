"""
HG profiles map drawdown capacity to hedge behaviour parameters.
"""
from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class HGProfile:
    id: str
    max_distance: int
    zone_width_factor: float
    breakout_lookahead: int
    pivot_lookback: int
    score_threshold: float
    partial_close_ratio: float
    partial_close_trigger_factor: float
    zone_refresh_secs: int
    lookback_bars: int
    max_zone_age_bars: int
    fallback_distance_factor: float
    allow_reentry: bool = False

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "zone_width_factor": self.zone_width_factor,
            "breakout_lookahead": self.breakout_lookahead,
            "pivot_lookback": self.pivot_lookback,
            "score_threshold": self.score_threshold,
            "partial_close_ratio": self.partial_close_ratio,
            "partial_close_trigger_factor": self.partial_close_trigger_factor,
            "zone_refresh_secs": self.zone_refresh_secs,
            "lookback_bars": self.lookback_bars,
            "max_zone_age_bars": self.max_zone_age_bars,
            "fallback_distance_factor": self.fallback_distance_factor,
            "allow_reentry": self.allow_reentry,
        }


HG_PROFILES = [
    HGProfile(
        id="tight",
        max_distance=800,
        zone_width_factor=1.0,
        breakout_lookahead=3,
        pivot_lookback=2,
        score_threshold=0.65,
        partial_close_ratio=0.7,
        partial_close_trigger_factor=0.5,
        zone_refresh_secs=60,
        lookback_bars=180,
        max_zone_age_bars=80,
        fallback_distance_factor=2.5,
    ),
    HGProfile(
        id="balanced",
        max_distance=1600,
        zone_width_factor=1.4,
        breakout_lookahead=4,
        pivot_lookback=3,
        score_threshold=0.6,
        partial_close_ratio=0.5,
        partial_close_trigger_factor=0.6,
        zone_refresh_secs=90,
        lookback_bars=240,
        max_zone_age_bars=120,
        fallback_distance_factor=3.0,
        allow_reentry=True,
    ),
    HGProfile(
        id="wide",
        max_distance=10000,
        zone_width_factor=1.8,
        breakout_lookahead=5,
        pivot_lookback=4,
        score_threshold=0.55,
        partial_close_ratio=0.35,
        partial_close_trigger_factor=0.7,
        zone_refresh_secs=120,
        lookback_bars=300,
        max_zone_age_bars=160,
        fallback_distance_factor=3.5,
        allow_reentry=True,
    ),
]


def get_hg_profile(distance_pips: int) -> Dict:
    """
    เลือกโปรไฟล์ HG ตามระยะ drawdown ที่ต้องการให้ระบบทนได้
    """
    for profile in HG_PROFILES:
        if distance_pips <= profile.max_distance:
            return profile.to_dict()
    return HG_PROFILES[-1].to_dict()


