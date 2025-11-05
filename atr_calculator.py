# atr_calculator.py
# คำนวณ ATR (Average True Range) สำหรับ XAUUSD

import MetaTrader5 as mt5
from typing import Optional, Dict
import logging
from datetime import datetime, timedelta
from config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ATRCalculator:
    """คลาสสำหรับคำนวณ ATR (Average True Range)"""
    
    def __init__(self):
        self.cached_atr = None
        self.cache_timestamp = None
        self.cache_duration = 60  # วินาที
        self.atr_period = 14
        self.timeframe = mt5.TIMEFRAME_M15
    
    def calculate_atr(self) -> Optional[float]:
        """
        คำนวณ ATR (Average True Range) period 14, Timeframe M15
        มี cache 60 วินาที
        
        Returns:
            ATR ในหน่วย pips หรือ None ถ้าเกิดข้อผิดพลาด
        """
        try:
            # เช็ค cache
            if self._is_cache_valid():
                logger.debug(f"Using cached ATR: {self.cached_atr:.1f} pips")
                return self.cached_atr
            
            # ตรวจสอบการเชื่อมต่อ MT5
            from mt5_connection import mt5_connection
            if not mt5_connection.connected:
                logger.error("MT5 not connected")
                return None
            
            # ดึงข้อมูลแท่งเทียน (ต้องการข้อมูลอย่างน้อย atr_period + 1 แท่ง)
            symbol = config.mt5.symbol
            bars_needed = self.atr_period + 1
            
            rates = mt5.copy_rates_from_pos(symbol, self.timeframe, 0, bars_needed)
            
            if rates is None or len(rates) < bars_needed:
                logger.error(f"Cannot get rates data for {symbol}")
                return None
            
            # คำนวณ True Range สำหรับแต่ละแท่ง
            true_ranges = []
            
            for i in range(1, len(rates)):
                high = rates[i]['high']
                low = rates[i]['low']
                prev_close = rates[i-1]['close']
                
                # True Range = max(high-low, |high-prev_close|, |low-prev_close|)
                tr = max(
                    high - low,
                    abs(high - prev_close),
                    abs(low - prev_close)
                )
                true_ranges.append(tr)
            
            # คำนวณ ATR (Average ของ True Range ล่าสุด atr_period แท่ง)
            if len(true_ranges) < self.atr_period:
                logger.error(f"Not enough data to calculate ATR (need {self.atr_period}, got {len(true_ranges)})")
                return None
            
            atr_price = sum(true_ranges[-self.atr_period:]) / self.atr_period
            
            # แปลงเป็น pips (XAUUSD: 0.1 = 1 pip)
            atr_pips = config.price_to_pips(atr_price)
            
            # บันทึกลง cache
            self.cached_atr = atr_pips
            self.cache_timestamp = datetime.now()
            
            logger.info(f"ATR calculated: {atr_pips:.1f} pips (period {self.atr_period}, TF M15)")
            
            return atr_pips
            
        except Exception as e:
            logger.error(f"Error calculating ATR: {e}")
            return None
    
    def get_volatility_level(self) -> str:
        """
        ระบุระดับความผันผวน (Volatility) ตาม ATR
        
        Returns:
            "LOW", "MODERATE", "HIGH", "VERY HIGH"
        """
        atr = self.calculate_atr()
        
        if atr is None:
            return "UNKNOWN"
        
        # เกณฑ์สำหรับ XAUUSD (ปรับตามประสบการณ์)
        if atr < 40:
            return "LOW"
        elif atr < 70:
            return "MODERATE"
        elif atr < 100:
            return "HIGH"
        else:
            return "VERY HIGH"
    
    def get_atr_info(self) -> Dict:
        """
        ดึงข้อมูล ATR พร้อมรายละเอียดทั้งหมด
        
        Returns:
            Dict ที่มี ATR, volatility level, timestamp
        """
        atr = self.calculate_atr()
        volatility = self.get_volatility_level()
        
        return {
            'atr': atr if atr is not None else 0.0,
            'volatility_level': volatility,
            'timestamp': datetime.now(),
            'period': self.atr_period,
            'timeframe': 'M15',
            'cache_valid': self._is_cache_valid()
        }
    
    def _is_cache_valid(self) -> bool:
        """
        ตรวจสอบว่า cache ยังใช้ได้หรือไม่
        
        Returns:
            True ถ้า cache ยังใช้ได้
        """
        if self.cached_atr is None or self.cache_timestamp is None:
            return False
        
        time_elapsed = (datetime.now() - self.cache_timestamp).total_seconds()
        return time_elapsed < self.cache_duration
    
    def clear_cache(self):
        """ล้าง cache เพื่อบังคับให้คำนวณใหม่"""
        self.cached_atr = None
        self.cache_timestamp = None
        logger.info("ATR cache cleared")


# สร้าง instance หลักสำหรับใช้งาน
atr_calculator = ATRCalculator()

