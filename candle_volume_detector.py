# candle_volume_detector.py
# ระบบตรวจจับทิศทาง Grid โดยดูจาก Volume + Candle Pattern

import MetaTrader5 as mt5
import logging
from typing import Optional, Dict, List
from datetime import datetime
import numpy as np
from config import config

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)  # Candle Volume Detector ใช้ WARNING เพื่อลด log


class CandleVolumeDetector:
    """
    ตรวจจับทิศทางการเทรดโดยดูจาก:
    1. แท่งเทียนที่ปิดแล้ว (Closed Candle)
    2. Volume เทียบกับค่าเฉลี่ย (Volume MA)
    
    Logic:
    - Bullish Candle + High Volume → BUY
    - Bearish Candle + High Volume → SELL
    - Low Volume หรือ Weak Candle → BOTH
    """
    
    def __init__(self):
        self.symbol = config.mt5.symbol
        self.primary_timeframe = mt5.TIMEFRAME_M15  # default
        self.volume_ma_period = 20  # Volume MA 20 แท่ง
        self.cached_result = None
        self.cached_time = None
        self.cache_duration = 60  # cache 60 วินาที
        self.timeframe_config = [
            {'tf': mt5.TIMEFRAME_M5, 'label': 'M5', 'weight': 0.2},
            {'tf': mt5.TIMEFRAME_M15, 'label': 'M15', 'weight': 0.5},
            {'tf': mt5.TIMEFRAME_H1, 'label': 'H1', 'weight': 0.3},
        ]
        self.confidence_weight = {
            'HIGH': 1.0,
            'MODERATE': 0.6,
            'LOW': 0.3
        }
    
    def get_closed_candle(self, position: int = 1, timeframe: Optional[int] = None) -> Optional[object]:
        """
        ดึงแท่งเทียนที่ปิดแล้ว
        
        Args:
            position: 1 = แท่งล่าสุดที่ปิดแล้ว, 2 = แท่งก่อนหน้า
            
        Returns:
            Candle object หรือ None
        """
        try:
            # position = 1 คือแท่งที่ปิดแล้ว (index 0 คือแท่งปัจจุบันที่กำลังวิ่ง)
            tf = timeframe or self.primary_timeframe
            rates = mt5.copy_rates_from_pos(self.symbol, tf, position, 1)
            
            if rates is None or len(rates) == 0:
                logger.error(f"Cannot get closed candle at position {position}")
                return None
            
            return rates[0]
            
        except Exception as e:
            logger.error(f"Error getting closed candle: {e}")
            return None
    
    def get_last_n_candles(self, n: int = 20, timeframe: Optional[int] = None) -> Optional[List]:
        """
        ดึง N แท่งล่าสุดที่ปิดแล้ว
        
        Args:
            n: จำนวนแท่ง
            
        Returns:
            List of candles หรือ None
        """
        try:
            tf = timeframe or self.primary_timeframe
            rates = mt5.copy_rates_from_pos(self.symbol, tf, 1, n)
            
            if rates is None or len(rates) == 0:
                logger.error(f"Cannot get last {n} candles")
                return None
            
            return rates
            
        except Exception as e:
            logger.error(f"Error getting candles: {e}")
            return None
    
    def calculate_volume_ma(self, period: int = 20, timeframe: Optional[int] = None) -> float:
        """
        คำนวณ Volume MA
        
        Args:
            period: จำนวนแท่ง
            
        Returns:
            Volume MA หรือ 0
        """
        try:
            candles = self.get_last_n_candles(period, timeframe=timeframe)
            
            if candles is None or len(candles) < period:
                logger.warning(f"Not enough candles for Volume MA calculation")
                return 0
            
            # ใช้ tick_volume (Volume ใน MT5)
            volumes = [candle['tick_volume'] for candle in candles]
            volume_ma = np.mean(volumes)
            
            logger.debug(f"Volume MA({period}): {volume_ma:.0f}")
            return volume_ma
            
        except Exception as e:
            logger.error(f"Error calculating Volume MA: {e}")
            return 0
    
    def analyze_candle(self, candle: object) -> Dict:
        """
        วิเคราะห์แท่งเทียน
        
        Returns:
            {
                'type': 'BULLISH'/'BEARISH'/'DOJI',
                'strength': 'STRONG'/'MODERATE'/'WEAK',
                'body_pips': float,
                'range_pips': float
            }
        """
        try:
            open_price = candle['open']
            close_price = candle['close']
            high_price = candle['high']
            low_price = candle['low']
            
            # คำนวณขนาด
            point = 0.01  # XAUUSD (0.01 = 1 pip)
            body_size = abs(close_price - open_price)
            full_range = high_price - low_price
            body_pips = body_size / point
            range_pips = full_range / point
            
            # ประเภทแท่ง
            if close_price > open_price:
                candle_type = "BULLISH"
            elif close_price < open_price:
                candle_type = "BEARISH"
            else:
                candle_type = "DOJI"
            
            # ความแข็งแรง (Body เทียบกับ Range)
            if full_range > 0:
                body_ratio = body_size / full_range
            else:
                body_ratio = 0
            
            if body_ratio >= 0.7:  # Body > 70%
                strength = "STRONG"
            elif body_ratio >= 0.4:  # Body 40-70%
                strength = "MODERATE"
            else:  # Body < 40%
                strength = "WEAK"
            
            return {
                'type': candle_type,
                'strength': strength,
                'body_pips': body_pips,
                'range_pips': range_pips,
                'body_ratio': body_ratio
            }
            
        except Exception as e:
            logger.error(f"Error analyzing candle: {e}")
            return {
                'type': 'DOJI',
                'strength': 'WEAK',
                'body_pips': 0,
                'range_pips': 0,
                'body_ratio': 0
            }
    
    def analyze_volume(self, candle: object, timeframe: Optional[int] = None) -> Dict:
        """
        วิเคราะห์ Volume
        
        Returns:
            {
                'level': 'VERY HIGH'/'HIGH'/'MODERATE'/'LOW',
                'ratio': float,
                'current': float,
                'ma': float
            }
        """
        try:
            current_volume = candle['tick_volume']
            volume_ma = self.calculate_volume_ma(self.volume_ma_period, timeframe=timeframe)
            
            if volume_ma == 0:
                return {
                    'level': 'UNKNOWN',
                    'ratio': 0,
                    'current': current_volume,
                    'ma': 0
                }
            
            volume_ratio = current_volume / volume_ma
            
            # กำหนดระดับ Volume
            if volume_ratio >= 2.0:
                level = "VERY HIGH"
            elif volume_ratio >= 1.5:
                level = "HIGH"
            elif volume_ratio >= 1.2:
                level = "MODERATE"
            else:
                level = "LOW"
            
            return {
                'level': level,
                'ratio': volume_ratio,
                'current': current_volume,
                'ma': volume_ma
            }
            
        except Exception as e:
            logger.error(f"Error analyzing volume: {e}")
            return {
                'level': 'UNKNOWN',
                'ratio': 0,
                'current': 0,
                'ma': 0
            }
    
    def decide_direction(self, candle_info: Dict, volume_info: Dict) -> Dict:
        """
        ตัดสินใจทิศทาง Grid
        
        Logic:
        1. BULLISH + (VERY HIGH/HIGH Volume) → BUY
        2. BEARISH + (VERY HIGH/HIGH Volume) → SELL
        3. อื่นๆ → BOTH
        
        Returns:
            {
                'direction': 'buy'/'sell'/'both',
                'confidence': 'HIGH'/'MODERATE'/'LOW',
                'reason': str
            }
        """
        candle_type = candle_info['type']
        candle_strength = candle_info['strength']
        volume_level = volume_info['level']
        volume_ratio = volume_info['ratio']
        body_pips = candle_info['body_pips']
        
        # ========== STRONG BUY SIGNAL ==========
        if (candle_type == "BULLISH" and 
            candle_strength in ["STRONG", "MODERATE"] and 
            volume_level in ["VERY HIGH", "HIGH"]):
            
            direction = "buy"
            confidence = "HIGH"
            reason = f"Bullish Candle ({body_pips:.1f}p) + {volume_level} Vol ({volume_ratio:.2f}x)"
        
        # ========== STRONG SELL SIGNAL ==========
        elif (candle_type == "BEARISH" and 
              candle_strength in ["STRONG", "MODERATE"] and 
              volume_level in ["VERY HIGH", "HIGH"]):
            
            direction = "sell"
            confidence = "HIGH"
            reason = f"Bearish Candle ({body_pips:.1f}p) + {volume_level} Vol ({volume_ratio:.2f}x)"
        
        # ========== MODERATE BUY SIGNAL ==========
        elif (candle_type == "BULLISH" and 
              volume_level == "MODERATE"):
            
            direction = "buy"
            confidence = "MODERATE"
            reason = f"Bullish + Moderate Vol ({volume_ratio:.2f}x)"
        
        # ========== MODERATE SELL SIGNAL ==========
        elif (candle_type == "BEARISH" and 
              volume_level == "MODERATE"):
            
            direction = "sell"
            confidence = "MODERATE"
            reason = f"Bearish + Moderate Vol ({volume_ratio:.2f}x)"
        
        # ========== WEAK SIGNAL ==========
        else:
            direction = "both"
            confidence = "LOW"
            reason = f"Weak: {candle_type} {candle_strength} + {volume_level} Vol"
        
        return {
            'direction': direction,
            'confidence': confidence,
            'reason': reason
        }
    
    def detect_direction(self) -> str:
        """
        ตรวจจับทิศทาง Grid
        
        Returns:
            "buy", "sell", "both"
        """
        result = self.get_full_analysis()
        return result['direction'] if result else "both"
    
    def get_full_analysis(self) -> Optional[Dict]:
        """
        วิเคราะห์เต็มรูปแบบ
        
        Returns:
            {
                'direction': str,
                'confidence': str,
                'reason': str,
                'candle_type': str,
                'candle_strength': str,
                'candle_pips': float,
                'volume_level': str,
                'volume_ratio': float,
                'timestamp': datetime
            }
        """
        try:
            # เช็ค Cache
            current_time = datetime.now()
            if (self.cached_result and self.cached_time and 
                (current_time - self.cached_time).total_seconds() < self.cache_duration):
                logger.debug("Using cached result")
                return self.cached_result
            
            aggregated_scores = {'buy': 0.0, 'sell': 0.0}
            tf_details = []
            
            for tf_conf in self.timeframe_config:
                detail = self._analyze_timeframe(tf_conf['tf'])
                if not detail:
                    continue
                tf_details.append(detail)
                direction = detail['decision']['direction']
                confidence = detail['decision']['confidence']
                weight = tf_conf['weight']
                conf_weight = self.confidence_weight.get(confidence, 0.3)
                score_contribution = weight * conf_weight
                if direction == 'buy':
                    aggregated_scores['buy'] += score_contribution
                elif direction == 'sell':
                    aggregated_scores['sell'] += score_contribution
                else:
                    aggregated_scores['buy'] += score_contribution * 0.5
                    aggregated_scores['sell'] += score_contribution * 0.5
            
            if not tf_details:
                logger.error("No timeframe data for direction analysis")
                return None
            
            buy_score = aggregated_scores['buy']
            sell_score = aggregated_scores['sell']
            score_diff = abs(buy_score - sell_score)
            
            if buy_score - sell_score > 0.15:
                direction = 'buy'
            elif sell_score - buy_score > 0.15:
                direction = 'sell'
            else:
                direction = 'both'
            
            if score_diff >= 0.4:
                confidence = 'HIGH'
            elif score_diff >= 0.2:
                confidence = 'MODERATE'
            else:
                confidence = 'LOW'
            
            reason_chunks = [
                f"{d['label']} {d['decision']['direction'].upper()} ({d['decision']['confidence']}): {d['decision']['reason']}"
                for d in tf_details
            ]
            reason_text = " | ".join(reason_chunks)
            
            primary_detail = next((d for d in tf_details if d['timeframe'] == mt5.TIMEFRAME_M15), tf_details[0])
            result = {
                'direction': direction,
                'confidence': confidence,
                'reason': reason_text,
                'scores': {'buy': buy_score, 'sell': sell_score},
                'timeframes': tf_details,
                'candle_type': primary_detail['candle']['type'],
                'candle_strength': primary_detail['candle']['strength'],
                'candle_pips': primary_detail['candle']['body_pips'],
                'candle_range_pips': primary_detail['candle']['range_pips'],
                'volume_level': primary_detail['volume']['level'],
                'volume_ratio': primary_detail['volume']['ratio'],
                'volume_current': primary_detail['volume']['current'],
                'volume_ma': primary_detail['volume']['ma'],
                'timestamp': datetime.now()
            }
            
            # Cache ผลลัพธ์
            self.cached_result = result
            self.cached_time = current_time
            
            logger.info(f"📊 Direction: {result['direction'].upper()} ({result['confidence']})")
            logger.info(f"   {result['reason']}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in full analysis: {e}")
            return None
    
    def clear_cache(self):
        """ล้าง cache เพื่อบังคับให้คำนวณใหม่"""
        self.cached_result = None
        self.cached_time = None
        logger.info("Candle/Volume cache cleared")

    def _analyze_timeframe(self, timeframe: int) -> Optional[Dict]:
        last_candle = self.get_closed_candle(position=1, timeframe=timeframe)
        if last_candle is None:
            return None
        candle_info = self.analyze_candle(last_candle)
        volume_info = self.analyze_volume(last_candle, timeframe=timeframe)
        decision = self.decide_direction(candle_info, volume_info)
        label = next((cfg['label'] for cfg in self.timeframe_config if cfg['tf'] == timeframe), str(timeframe))
        return {
            'label': label,
            'timeframe': timeframe,
            'candle': candle_info,
            'volume': volume_info,
            'decision': decision
        }


# สร้าง singleton instance
candle_volume_detector = CandleVolumeDetector()

