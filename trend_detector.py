# trend_detector.py
# ตรวจจับ Trend ด้วย EMA Crossover สำหรับ XAUUSD

import MetaTrader5 as mt5
from typing import Optional, Dict, Tuple
import logging
from datetime import datetime
from config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TrendDetector:
    """คลาสสำหรับตรวจจับ Trend ด้วย EMA Crossover"""
    
    def __init__(self):
        self.cached_trend_info = None
        self.cache_timestamp = None
        self.cache_duration = 60  # วินาที
        self.ema_fast_period = 20
        self.ema_slow_period = 50
        self.timeframe = mt5.TIMEFRAME_M15
    
    def calculate_ema(self, period: int) -> Optional[float]:
        """
        คำนวณ EMA (Exponential Moving Average)
        
        Args:
            period: จำนวนแท่งเทียนที่ใช้คำนวณ
            
        Returns:
            EMA value หรือ None ถ้าเกิดข้อผิดพลาด
        """
        try:
            # ตรวจสอบการเชื่อมต่อ MT5
            from mt5_connection import mt5_connection
            if not mt5_connection.connected:
                logger.error("MT5 not connected")
                return None
            
            # ดึงข้อมูลแท่งเทียน (ต้องการข้อมูลมากพอสำหรับ EMA)
            symbol = config.mt5.symbol
            bars_needed = period * 3  # ดึงข้อมูลเยอะพอสำหรับความแม่นยำ
            
            rates = mt5.copy_rates_from_pos(symbol, self.timeframe, 0, bars_needed)
            
            if rates is None or len(rates) < period:
                logger.error(f"Cannot get rates data for {symbol}")
                return None
            
            # คำนวณ EMA แบบ manual
            # EMA = (Close - EMA(previous)) * multiplier + EMA(previous)
            # multiplier = 2 / (period + 1)
            
            multiplier = 2.0 / (period + 1)
            
            # เริ่มต้นด้วย SMA (Simple Moving Average)
            sma = sum(rates[i]['close'] for i in range(period)) / period
            ema = sma
            
            # คำนวณ EMA ต่อเนื่อง
            for i in range(period, len(rates)):
                close = rates[i]['close']
                ema = (close - ema) * multiplier + ema
            
            return ema
            
        except Exception as e:
            logger.error(f"Error calculating EMA({period}): {e}")
            return None
    
    def detect_trend(self) -> str:
        """
        ตรวจจับ Trend ด้วย EMA Crossover
        
        Trend Detection Logic:
        - EMA_Fast = EMA(20)
        - EMA_Slow = EMA(50)
        - Current_Price = current_price
        
        Main Trend:
        - UPTREND: EMA_Fast > EMA_Slow + 10 pips
        - DOWNTREND: EMA_Fast < EMA_Slow - 10 pips
        - SIDEWAYS: อื่นๆ
        
        Price Position:
        - ABOVE: Current_Price > EMA_Slow + 30 pips
        - BELOW: Current_Price < EMA_Slow - 30 pips
        - NEAR: อื่นๆ
        
        Final Decision:
        - "buy": UPTREND + ABOVE
        - "sell": DOWNTREND + BELOW
        - "both": SIDEWAYS
        
        Returns:
            "buy", "sell", "both"
        """
        try:
            # ดึงข้อมูลที่จำเป็น
            from mt5_connection import mt5_connection
            
            ema_fast = self.calculate_ema(self.ema_fast_period)
            ema_slow = self.calculate_ema(self.ema_slow_period)
            
            if ema_fast is None or ema_slow is None:
                logger.error("Cannot calculate EMAs")
                return "both"  # Default to both ถ้าคำนวณไม่ได้
            
            # ดึงราคาปัจจุบัน
            price_info = mt5_connection.get_current_price()
            if not price_info:
                logger.error("Cannot get current price")
                return "both"
            
            current_price = price_info['bid']
            
            # คำนวณระยะห่างใน pips
            ema_diff_pips = config.price_to_pips(ema_fast - ema_slow)
            price_diff_pips = config.price_to_pips(current_price - ema_slow)
            
            # Main Trend
            if ema_diff_pips > 10:
                main_trend = "UPTREND"
            elif ema_diff_pips < -10:
                main_trend = "DOWNTREND"
            else:
                main_trend = "SIDEWAYS"
            
            # Price Position
            if price_diff_pips > 30:
                price_position = "ABOVE"
            elif price_diff_pips < -30:
                price_position = "BELOW"
            else:
                price_position = "NEAR"
            
            # Final Decision
            if main_trend == "UPTREND" and price_position == "ABOVE":
                trend = "buy"
                logger.info(f"Trend: BUY (Uptrend + Above) - EMA_Fast: {ema_fast:.2f}, EMA_Slow: {ema_slow:.2f}, Price: {current_price:.2f}")
            elif main_trend == "DOWNTREND" and price_position == "BELOW":
                trend = "sell"
                logger.info(f"Trend: SELL (Downtrend + Below) - EMA_Fast: {ema_fast:.2f}, EMA_Slow: {ema_slow:.2f}, Price: {current_price:.2f}")
            else:
                trend = "both"
                logger.info(f"Trend: BOTH (Sideways) - EMA_Fast: {ema_fast:.2f}, EMA_Slow: {ema_slow:.2f}, Price: {current_price:.2f}")
            
            return trend
            
        except Exception as e:
            logger.error(f"Error detecting trend: {e}")
            return "both"
    
    def get_trend_strength(self) -> str:
        """
        ระบุความแข็งแรงของ Trend
        
        Returns:
            "strong", "weak", "neutral"
        """
        try:
            ema_fast = self.calculate_ema(self.ema_fast_period)
            ema_slow = self.calculate_ema(self.ema_slow_period)
            
            if ema_fast is None or ema_slow is None:
                return "neutral"
            
            # คำนวณระยะห่างใน pips
            ema_diff_pips = abs(config.price_to_pips(ema_fast - ema_slow))
            
            # เกณฑ์สำหรับ XAUUSD
            if ema_diff_pips > 30:
                return "strong"
            elif ema_diff_pips > 10:
                return "weak"
            else:
                return "neutral"
            
        except Exception as e:
            logger.error(f"Error getting trend strength: {e}")
            return "neutral"
    
    def get_trend_info(self) -> Dict:
        """
        ดึงข้อมูล Trend พร้อมรายละเอียดทั้งหมด
        
        Returns:
            Dict ที่มี trend, strength, ema_fast, ema_slow, timestamp
        """
        try:
            # เช็ค cache
            if self._is_cache_valid():
                logger.debug("Using cached trend info")
                return self.cached_trend_info
            
            # คำนวณใหม่
            ema_fast = self.calculate_ema(self.ema_fast_period)
            ema_slow = self.calculate_ema(self.ema_slow_period)
            trend = self.detect_trend()
            strength = self.get_trend_strength()
            
            trend_info = {
                'trend': trend,
                'strength': strength,
                'ema_fast': ema_fast if ema_fast is not None else 0.0,
                'ema_slow': ema_slow if ema_slow is not None else 0.0,
                'timestamp': datetime.now(),
                'ema_fast_period': self.ema_fast_period,
                'ema_slow_period': self.ema_slow_period,
                'timeframe': 'M15',
                'cache_valid': True
            }
            
            # บันทึกลง cache
            self.cached_trend_info = trend_info
            self.cache_timestamp = datetime.now()
            
            return trend_info
            
        except Exception as e:
            logger.error(f"Error getting trend info: {e}")
            return {
                'trend': 'both',
                'strength': 'neutral',
                'ema_fast': 0.0,
                'ema_slow': 0.0,
                'timestamp': datetime.now(),
                'ema_fast_period': self.ema_fast_period,
                'ema_slow_period': self.ema_slow_period,
                'timeframe': 'M15',
                'cache_valid': False
            }
    
    def _is_cache_valid(self) -> bool:
        """
        ตรวจสอบว่า cache ยังใช้ได้หรือไม่
        
        Returns:
            True ถ้า cache ยังใช้ได้
        """
        if self.cached_trend_info is None or self.cache_timestamp is None:
            return False
        
        time_elapsed = (datetime.now() - self.cache_timestamp).total_seconds()
        return time_elapsed < self.cache_duration
    
    def clear_cache(self):
        """ล้าง cache เพื่อบังคับให้คำนวณใหม่"""
        self.cached_trend_info = None
        self.cache_timestamp = None
        logger.info("Trend cache cleared")


# สร้าง instance หลักสำหรับใช้งาน
trend_detector = TrendDetector()

