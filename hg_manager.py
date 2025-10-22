# hg_manager.py
# ไฟล์จัดการระบบ Hedge (HG)

from typing import List, Dict, Optional
import logging
from mt5_connection import mt5_connection
from position_monitor import position_monitor
from config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HGManager:
    """คลาสจัดการระบบ Hedge (HG)"""
    
    def __init__(self):
        self.active = False
        self.hg_levels = []  # เก็บข้อมูล HG levels
        self.placed_hg = {}  # เก็บ HG positions ที่เปิดอยู่
        self.closed_hg_levels = set()  # เก็บ HG levels ที่ถูกปิดแล้ว (SL/TP)
        self.start_price = 0.0
        
        # Smart HG cache
        self.smart_zones_cache = {'support': [], 'resistance': [], 'timestamp': 0}
        self.atr_cache = {'value': 0.0, 'timestamp': 0}
        
    def check_hg_trigger(self, current_price: float) -> List[Dict]:
        """
        ตรวจสอบว่าถึงเงื่อนไขวาง HG หรือยัง
        
        Args:
            current_price: ราคาปัจจุบัน
            
        Returns:
            List ของ HG ที่ควรวาง
        """
        triggers = []
        
        # ใช้ระยะห่างแยก Buy/Sell
        buy_hg_distance_price = config.pips_to_price(config.hg.buy_hg_distance)
        sell_hg_distance_price = config.pips_to_price(config.hg.sell_hg_distance)
        
        # HG Buy (ด้านล่าง) - เฉพาะเมื่อเปิดใช้งานและเลือก buy/both
        if config.hg.direction in ['buy', 'both']:
            for i in range(1, config.hg.buy_max_hg_levels + 1):
                level_price_buy = self.start_price - (buy_hg_distance_price * i)
                level_key_buy = f"HG_BUY_{i}"
                
                if (current_price <= level_price_buy and 
                    level_key_buy not in self.placed_hg and 
                    level_key_buy not in self.closed_hg_levels):
                    logger.info(f"HG Trigger detected: {level_key_buy} | Target: {level_price_buy:.2f} | Current: {current_price:.2f}")
                    triggers.append({
                        'level_key': level_key_buy,
                        'price': level_price_buy,
                        'type': 'buy',
                        'level': -i
                    })
        
        # HG Sell (ด้านบน) - เฉพาะเมื่อเปิดใช้งานและเลือก sell/both
        if config.hg.direction in ['sell', 'both']:
            for i in range(1, config.hg.sell_max_hg_levels + 1):
                level_price_sell = self.start_price + (sell_hg_distance_price * i)
                level_key_sell = f"HG_SELL_{i}"
                
                if (current_price >= level_price_sell and 
                    level_key_sell not in self.placed_hg and 
                    level_key_sell not in self.closed_hg_levels):
                    logger.info(f"HG Trigger detected: {level_key_sell} | Target: {level_price_sell:.2f} | Current: {current_price:.2f}")
                    triggers.append({
                        'level_key': level_key_sell,
                        'price': level_price_sell,
                        'type': 'sell',
                        'level': i
                    })
        
        return triggers
    
    def update_hg_start_price_if_needed(self, current_price: float):
        """
        อัพเดท start_price เมื่อราคาเคลื่อนไหวไกลจากจุดเริ่มต้น
        เพื่อให้ระบบ HG ยังวางได้เมื่อราคาเคลื่อนไหวไปเรื่อยๆ
        """
        if not self.active or not config.hg.enabled:
            return
        
        # ใช้ค่าเฉลี่ยของ Buy และ Sell HG Distance
        avg_hg_distance_price = (config.pips_to_price(config.hg.buy_hg_distance) + 
                                 config.pips_to_price(config.hg.sell_hg_distance)) / 2
        distance_from_start = abs(current_price - self.start_price)
        
        # ถ้าราคาเคลื่อนไหวไกลเกิน 2 เท่าของ HG Distance
        if distance_from_start >= (avg_hg_distance_price * 2):
            # อัพเดท start_price เป็นราคาปัจจุบัน
            old_start_price = self.start_price
            self.start_price = current_price
            
            logger.info(f"HG Start Price updated: {old_start_price:.2f} → {self.start_price:.2f}")
            logger.info(f"Distance moved: {config.price_to_pips(distance_from_start):.0f} pips")
            
            # ล้าง HG positions ที่วางไว้แล้ว (เพื่อให้วางใหม่ได้)
            self.placed_hg = {}
            # ล้าง closed_hg_levels ด้วย (เพื่อให้วางใหม่ได้)
            self.closed_hg_levels = set()
            logger.info("HG positions cleared - will place new HG levels")
    
    def calculate_hg_lot(self, hg_type: str = 'buy') -> float:
        """
        คำนวณ lot size สำหรับ HG (ใช้ multiplier และ initial lot แยก Buy/Sell)
        HG Lot = max(Grid Exposure × multiplier, Initial Lot)
        
        รองรับทั้ง:
        - Classic Mode: คำนวณแบบง่าย
        - Smart Mode: คำนวณแบบแม่นยำ (Risk-adjusted)
        
        Args:
            hg_type: 'buy' หรือ 'sell'
        
        Returns:
            lot size สำหรับ HG
        """
        # เช็คโหมด
        if config.hg.mode == 'smart':
            # ใช้ Smart Mode (คำนวณแม่นยำ)
            return self.calculate_precise_hg_lot_smart(hg_type)
        
        # Classic Mode (แบบเดิม)
        # ดึงข้อมูล Grid exposure
        exposure = position_monitor.get_net_grid_exposure()
        net_volume = exposure['net_volume']
        
        # เลือก multiplier และ initial lot ตามประเภท
        if hg_type == 'buy':
            multiplier = config.hg.buy_hg_multiplier
            initial_lot = config.hg.buy_hg_initial_lot
        else:  # sell
            multiplier = config.hg.sell_hg_multiplier
            initial_lot = config.hg.sell_hg_initial_lot
        
        # คำนวณ HG lot
        hg_lot = net_volume * multiplier
        
        # ใช้ค่าที่มากกว่าระหว่าง calculated lot กับ initial lot
        hg_lot = max(hg_lot, initial_lot)
        
        # ปัดเศษตาม step
        hg_lot = round(hg_lot, 2)
        
        logger.info(f"HG {hg_type.upper()} Lot calculated: {hg_lot} (Grid exposure: {net_volume}, Multiplier: {multiplier}, Min: {initial_lot})")
        
        return hg_lot
    
    def place_hg_order(self, hg_info: Dict) -> Optional[int]:
        """
        วาง HG order
        
        Args:
            hg_info: ข้อมูล HG ที่ต้องวาง
            
        Returns:
            ticket number หรือ None
        """
        # คำนวณ lot size (แยก Buy/Sell)
        hg_lot = self.calculate_hg_lot(hg_info['type'])
        
        # กำหนด comment
        comment = f"{config.mt5.comment_hg}_{hg_info['level_key']}"
        
        # วาง order (ไม่มี TP เพราะจะใช้วิธี breakeven)
        ticket = mt5_connection.place_order(
            order_type=hg_info['type'],
            volume=hg_lot,
            comment=comment
        )
        
        if ticket:
            # บันทึก HG position
            self.placed_hg[hg_info['level_key']] = {
                'ticket': ticket,
                'open_price': hg_info['price'],
                'type': hg_info['type'],
                'lot': hg_lot,
                'breakeven_set': False,
                'level': hg_info['level']
            }
            
            logger.info(f"HG placed: {hg_info['type'].upper()} {hg_lot} lots at {hg_info['price']:.2f}")
            logger.info(f"Level: {hg_info['level_key']}")
        
        return ticket
    
    def monitor_hg_profit(self):
        """
        ติดตามกำไรของ HG positions
        และตั้ง breakeven SL เมื่อถึงเงื่อนไข
        """
        if not self.active or not config.hg.enabled:
            return
        
        # อัพเดท positions
        position_monitor.update_all_positions()
        
        for level_key, hg_data in self.placed_hg.items():
            # ตรวจสอบว่า position ยังเปิดอยู่หรือไม่
            pos = position_monitor.get_position_by_ticket(hg_data['ticket'])
            
            if pos is None:
                # Position ถูกปิดแล้ว (SL/TP)
                logger.info(f"HG closed: {level_key}")
                # เพิ่มลง closed_hg_levels เพื่อไม่ให้วางซ้ำ
                self.closed_hg_levels.add(level_key)
                continue
            
            # ตรวจสอบว่าตั้ง breakeven แล้วหรือยัง
            if hg_data['breakeven_set']:
                continue
            
            # คำนวณกำไรเป็น pips
            if hg_data['type'] == 'buy':
                pips_profit = config.price_to_pips(pos['current_price'] - pos['open_price'])
                sl_trigger = config.hg.buy_hg_sl_trigger
            else:  # sell
                pips_profit = config.price_to_pips(pos['open_price'] - pos['current_price'])
                sl_trigger = config.hg.sell_hg_sl_trigger
            
            # ตรวจสอบว่าถึง trigger breakeven หรือยัง (ใช้ค่าแยก Buy/Sell)
            if pips_profit >= sl_trigger:
                self.set_hg_breakeven_sl(hg_data, pos)
    
    def set_hg_breakeven_sl(self, hg_data: Dict, position: Dict):
        """
        ตั้ง Stop Loss แบบ breakeven สำหรับ HG (ใช้ buffer แยก Buy/Sell)
        
        Args:
            hg_data: ข้อมูล HG
            position: ข้อมูล position จาก MT5
        """
        # เลือก buffer ตามประเภท
        if hg_data['type'] == 'buy':
            buffer = config.hg.buy_sl_buffer
        else:  # sell
            buffer = config.hg.sell_sl_buffer
        
        # คำนวณราคา breakeven (เพิ่ม buffer)
        buffer_price = config.pips_to_price(buffer)
        
        if hg_data['type'] == 'buy':
            sl_price = position['open_price'] + buffer_price
        else:  # sell
            sl_price = position['open_price'] - buffer_price
        
        # ตั้ง SL
        success = mt5_connection.modify_order(
            ticket=hg_data['ticket'],
            sl=sl_price
        )
        
        if success:
            hg_data['breakeven_set'] = True
            logger.info(f"HG Breakeven set: Ticket {hg_data['ticket']} | SL: {sl_price:.2f}")
            logger.info(f"Buffer: {buffer} pips ({hg_data['type'].upper()})")
    
    # ========================================
    # SMART HG FUNCTIONS (โหมดใหม่)
    # ========================================
    
    def calculate_atr(self, period: int = 14) -> float:
        """
        คำนวณ ATR (Average True Range) สำหรับวัด Volatility
        
        Args:
            period: จำนวน bars สำหรับคำนวณ (default: 14)
            
        Returns:
            ATR value (pips)
        """
        try:
            import MetaTrader5 as mt5
            import time
            
            # ใช้ cache ถ้ายังไม่หมดอายุ (5 นาที)
            current_time = time.time()
            if current_time - self.atr_cache['timestamp'] < 300:
                return self.atr_cache['value']
            
            # ดึงราคาย้อนหลัง (H1 timeframe)
            rates = mt5.copy_rates_from_pos(config.mt5.symbol, mt5.TIMEFRAME_H1, 0, period + 1)
            
            if rates is None or len(rates) < period + 1:
                logger.warning(f"Cannot calculate ATR: insufficient data")
                return 30.0  # ค่า default
            
            # คำนวณ True Range สำหรับแต่ละ bar
            true_ranges = []
            for i in range(1, len(rates)):
                high = rates[i]['high']
                low = rates[i]['low']
                prev_close = rates[i-1]['close']
                
                tr = max(
                    high - low,
                    abs(high - prev_close),
                    abs(low - prev_close)
                )
                true_ranges.append(tr)
            
            # คำนวณ ATR (average ของ True Range)
            atr = sum(true_ranges) / len(true_ranges)
            atr_pips = config.price_to_pips(atr)
            
            # บันทึก cache
            self.atr_cache = {'value': atr_pips, 'timestamp': current_time}
            
            logger.debug(f"ATR calculated: {atr_pips:.1f} pips")
            return atr_pips
            
        except Exception as e:
            logger.error(f"Error calculating ATR: {e}")
            return 30.0  # ค่า default
    
    def cluster_price_zones(self, prices: List[float], tolerance: float = 10.0) -> List[float]:
        """
        รวมราคาที่ใกล้กันเป็น cluster เดียว
        
        Args:
            prices: รายการราคา
            tolerance: ระยะห่างที่ถือว่าใกล้กัน (default: 10.0)
            
        Returns:
            รายการราคาที่รวมแล้ว (average ของแต่ละ cluster)
        """
        if not prices:
            return []
        
        sorted_prices = sorted(prices)
        clusters = []
        current_cluster = [sorted_prices[0]]
        
        for price in sorted_prices[1:]:
            if price - current_cluster[-1] <= tolerance:
                current_cluster.append(price)
            else:
                # สร้าง cluster ใหม่
                clusters.append(sum(current_cluster) / len(current_cluster))
                current_cluster = [price]
        
        # เพิ่ม cluster สุดท้าย
        clusters.append(sum(current_cluster) / len(current_cluster))
        
        return clusters
    
    def find_smart_hg_zones(self, lookback_bars: int = 100) -> Dict:
        """
        หา Zone ที่เหมาะสมสำหรับวาง HG
        
        คำนึงถึง:
        1. Support/Resistance จากราคาในอดีต
        2. Round Numbers (2600, 2650, 2700)
        
        Args:
            lookback_bars: จำนวน bars ย้อนหลัง
            
        Returns:
            {
                'support_zones': [2600.0, 2610.0, 2620.0],
                'resistance_zones': [2650.0, 2660.0, 2670.0]
            }
        """
        try:
            import MetaTrader5 as mt5
            import time
            
            # ใช้ cache ถ้ายังไม่หมดอายุ (10 นาที)
            current_time = time.time()
            if current_time - self.smart_zones_cache['timestamp'] < 600:
                return {
                    'support_zones': self.smart_zones_cache['support'],
                    'resistance_zones': self.smart_zones_cache['resistance']
                }
            
            # ดึงราคาย้อนหลัง
            rates = mt5.copy_rates_from_pos(config.mt5.symbol, mt5.TIMEFRAME_H1, 0, lookback_bars)
            
            if rates is None or len(rates) == 0:
                logger.warning("Cannot get historical data for zone detection")
                return {'support_zones': [], 'resistance_zones': []}
            
            highs = [r['high'] for r in rates]
            lows = [r['low'] for r in rates]
            
            # หา Support Zones (จากจุด Low ที่สำคัญ)
            support_zones = []
            
            # หา Local Lows (จุดต่ำสุดในช่วง)
            for i in range(5, len(lows) - 5):
                is_local_low = True
                for j in range(i - 5, i + 5):
                    if j != i and lows[j] < lows[i]:
                        is_local_low = False
                        break
                
                if is_local_low:
                    support_zones.append(lows[i])
            
            # หา Resistance Zones (จากจุด High ที่สำคัญ)
            resistance_zones = []
            
            # หา Local Highs (จุดสูงสุดในช่วง)
            for i in range(5, len(highs) - 5):
                is_local_high = True
                for j in range(i - 5, i + 5):
                    if j != i and highs[j] > highs[i]:
                        is_local_high = False
                        break
                
                if is_local_high:
                    resistance_zones.append(highs[i])
            
            # เพิ่ม Round Numbers (2600, 2650, 2700, etc.)
            current_price = mt5_connection.get_current_price()['bid']
            price_min = current_price - 500  # ดูช่วง ±500
            price_max = current_price + 500
            
            round_numbers = []
            for price in range(int(price_min), int(price_max), 50):  # ทุกๆ 50
                round_numbers.append(float(price))
            
            # เพิ่ม round numbers เข้าไปใน zones
            for rn in round_numbers:
                if rn < current_price:
                    support_zones.append(rn)
                else:
                    resistance_zones.append(rn)
            
            # Cluster zones ที่ใกล้กัน
            support_zones = self.cluster_price_zones(support_zones, tolerance=10.0)
            resistance_zones = self.cluster_price_zones(resistance_zones, tolerance=10.0)
            
            # เรียงลำดับและเลือกเฉพาะ Top 5
            support_zones = sorted(support_zones, reverse=True)[:5]  # ใกล้ราคาปัจจุบันที่สุด
            resistance_zones = sorted(resistance_zones)[:5]
            
            # บันทึก cache
            self.smart_zones_cache = {
                'support': support_zones,
                'resistance': resistance_zones,
                'timestamp': current_time
            }
            
            logger.info(f"Smart HG Zones found:")
            logger.info(f"  - Support: {[f'{z:.1f}' for z in support_zones]}")
            logger.info(f"  - Resistance: {[f'{z:.1f}' for z in resistance_zones]}")
            
            return {
                'support_zones': support_zones,
                'resistance_zones': resistance_zones
            }
            
        except Exception as e:
            logger.error(f"Error finding HG zones: {e}")
            return {'support_zones': [], 'resistance_zones': []}
    
    def calculate_smart_hg_distance(self) -> Dict:
        """
        คำนวณระยะ HG แบบ Dynamic
        
        คำนึงถึง:
        1. Volatility (ATR)
        2. Grid Exposure Risk
        3. Drawdown ปัจจุบัน
        
        Returns:
            {
                'buy_distance': 250,  # pips
                'sell_distance': 250
            }
        """
        # 1. คำนวณ ATR (Volatility)
        atr = self.calculate_atr(period=14)
        
        # 2. เช็ค Grid Exposure
        exposure = position_monitor.get_net_grid_exposure()
        net_volume = exposure['net_volume']
        
        # 3. เช็ค Drawdown
        total_pnl = position_monitor.total_pnl
        account_info = mt5_connection.get_account_info()
        balance = account_info['balance'] if account_info else 10000
        drawdown_percent = (total_pnl / balance) * 100 if balance > 0 else 0
        
        # 4. คำนวณ Base Distance
        # Base = ATR × 7 (ปรับได้)
        base_distance = atr * 7
        
        # 5. ปรับตาม Exposure (ยิ่ง Exposure สูง ยิ่งเข้าไว)
        exposure_factor = 1.0
        
        if net_volume > 0.5:  # Exposure สูง
            exposure_factor = 0.8  # ลด 20%
            logger.info(f"⚠️ High Exposure ({net_volume:.2f}) → Reduce HG distance")
        elif net_volume > 1.0:  # Exposure สูงมาก
            exposure_factor = 0.6  # ลด 40%
            logger.info(f"🔴 Very High Exposure ({net_volume:.2f}) → Significantly reduce HG distance")
        
        # 6. ปรับตาม Drawdown (ยิ่งขาดทุน ยิ่งเข้าไว)
        drawdown_factor = 1.0
        
        if drawdown_percent < -5:  # ขาดทุนเกิน 5%
            drawdown_factor = 0.8  # ลด 20%
            logger.info(f"⚠️ Drawdown {drawdown_percent:.1f}% → Reduce HG distance")
        elif drawdown_percent < -10:  # ขาดทุนเกิน 10%
            drawdown_factor = 0.6  # ลด 40%
            logger.info(f"🔴 High Drawdown {drawdown_percent:.1f}% → Significantly reduce HG distance")
        
        # 7. คำนวณ Final Distance
        final_distance = base_distance * exposure_factor * drawdown_factor
        
        # จำกัดช่วง (50-500 pips)
        final_distance = max(50, min(500, final_distance))
        
        logger.info(f"Smart HG Distance Calculation:")
        logger.info(f"  - ATR: {atr:.0f} pips")
        logger.info(f"  - Base: {base_distance:.0f} pips")
        logger.info(f"  - Exposure Factor: {exposure_factor:.2f}")
        logger.info(f"  - Drawdown Factor: {drawdown_factor:.2f}")
        logger.info(f"  - Final: {final_distance:.0f} pips")
        
        return {
            'buy_distance': final_distance,
            'sell_distance': final_distance
        }
    
    def should_place_hg_at_current_price_smart(self, current_price: float, hg_type: str) -> bool:
        """
        ตรวจสอบว่าควรวาง HG ที่ราคาปัจจุบันหรือไม่ (Smart Mode)
        
        เงื่อนไข:
        1. ราคาอยู่ใน Smart Zone (Support/Resistance)
        2. Grid Exposure สูงพอ
        3. ระยะห่างจาก Start Price ตาม Dynamic Distance
        
        Args:
            current_price: ราคาปัจจุบัน
            hg_type: 'buy' or 'sell'
            
        Returns:
            True = ควรวาง HG
        """
        # 1. คำนวณ Dynamic Distance
        distances = self.calculate_smart_hg_distance()
        
        # 2. เช็คระยะห่างจาก Start Price
        if hg_type == 'buy':
            required_distance = config.pips_to_price(distances['buy_distance'])
            price_diff = self.start_price - current_price
            
            if price_diff < required_distance:
                logger.debug(f"HG BUY: Not far enough ({config.price_to_pips(price_diff):.0f} < {distances['buy_distance']:.0f} pips)")
                return False
        
        elif hg_type == 'sell':
            required_distance = config.pips_to_price(distances['sell_distance'])
            price_diff = current_price - self.start_price
            
            if price_diff < required_distance:
                logger.debug(f"HG SELL: Not far enough ({config.price_to_pips(price_diff):.0f} < {distances['sell_distance']:.0f} pips)")
                return False
        
        # 3. หา Smart Zones
        zones = self.find_smart_hg_zones()
        
        # 4. เช็คว่าราคาปัจจุบันอยู่ใน Zone หรือไม่
        zone_tolerance = 10.0  # ห่างจาก zone ไม่เกิน 10 ดอลลาร์
        
        if hg_type == 'buy':
            # HG Buy → เข้าที่ Support
            for support in zones['support_zones']:
                if abs(current_price - support) <= zone_tolerance:
                    logger.info(f"✅ SMART HG BUY at Support Zone: {support:.1f} (current: {current_price:.2f})")
                    return True
            
            logger.debug(f"⚠️ HG BUY skipped: Not near any Support zone")
            return False
        
        elif hg_type == 'sell':
            # HG Sell → เข้าที่ Resistance
            for resistance in zones['resistance_zones']:
                if abs(current_price - resistance) <= zone_tolerance:
                    logger.info(f"✅ SMART HG SELL at Resistance Zone: {resistance:.1f} (current: {current_price:.2f})")
                    return True
            
            logger.debug(f"⚠️ HG SELL skipped: Not near any Resistance zone")
            return False
        
        return False
    
    def calculate_grid_average_price(self, order_type: str) -> float:
        """
        คำนวณราคาเฉลี่ยของ Grid positions
        
        Args:
            order_type: 'buy' or 'sell'
            
        Returns:
            ราคาเฉลี่ย
        """
        position_monitor.update_all_positions()
        positions = [p for p in position_monitor.grid_positions if p['type'] == order_type]
        
        if not positions:
            return 0.0
        
        total_value = sum(p['open_price'] * p['volume'] for p in positions)
        total_volume = sum(p['volume'] for p in positions)
        
        if total_volume == 0:
            return 0.0
        
        avg_price = total_value / total_volume
        return avg_price
    
    def calculate_precise_hg_lot_smart(self, hg_type: str) -> float:
        """
        คำนวณ HG Lot แบบแม่นยำ (Smart Mode)
        
        คำนึงถึง:
        1. Grid Exposure (สัดส่วนไม้ Buy/Sell)
        2. Risk Management (% ของ Balance)
        3. Current Drawdown
        
        Returns:
            HG Lot Size ที่แม่นยำ
        """
        # 1. ดึงข้อมูล Grid Exposure
        exposure = position_monitor.get_net_grid_exposure()
        net_volume = exposure['net_volume']
        
        # 2. ดึงข้อมูล Account
        account_info = mt5_connection.get_account_info()
        balance = account_info['balance'] if account_info else 10000
        equity = account_info['equity'] if account_info else 10000
        
        # 3. คำนวณ HG Lot ที่ต้องการ
        if hg_type == 'buy':
            base_multiplier = config.hg.buy_hg_multiplier
            initial_lot = config.hg.buy_hg_initial_lot
        else:
            base_multiplier = config.hg.sell_hg_multiplier
            initial_lot = config.hg.sell_hg_initial_lot
        
        calculated_lot = net_volume * base_multiplier
        
        # 4. ปรับตาม Risk (% ของ Balance)
        max_risk_percent = 3.0
        max_risk_amount = balance * (max_risk_percent / 100)
        
        # คำนวณ Lot สูงสุดจาก Risk (สมมติ SL = 100 pips)
        sl_distance_pips = 100
        sl_distance_price = config.pips_to_price(sl_distance_pips)
        max_lot_from_risk = max_risk_amount / (sl_distance_price * 100)
        
        # 5. ปรับตาม Drawdown
        current_drawdown_percent = ((equity - balance) / balance) * 100 if balance > 0 else 0
        drawdown_multiplier = 1.0
        
        if current_drawdown_percent < -5:
            # ขาดทุนเกิน 5% → เพิ่ม HG (ค้ำแรงขึ้น)
            drawdown_multiplier = 1.2
            logger.info(f"⚠️ Drawdown {current_drawdown_percent:.1f}% → Increase HG by 20%")
        elif current_drawdown_percent < -10:
            # ขาดทุนเกิน 10% → เพิ่ม HG มาก
            drawdown_multiplier = 1.5
            logger.info(f"🔴 High Drawdown {current_drawdown_percent:.1f}% → Increase HG by 50%")
        
        # 6. คำนวณ Final Lot
        final_lot = calculated_lot * drawdown_multiplier
        final_lot = max(initial_lot, final_lot)  # อย่างน้อยเท่ากับ initial lot
        final_lot = min(final_lot, max_lot_from_risk)  # ไม่เกิน risk limit
        final_lot = round(final_lot, 2)
        
        # 7. Log การคำนวณ
        logger.info(f"Smart HG Lot Calculation ({hg_type.upper()}):")
        logger.info(f"  - Net Volume: {net_volume:.2f}")
        logger.info(f"  - Base Lot: {calculated_lot:.2f} (Net × {base_multiplier})")
        logger.info(f"  - Drawdown Multiplier: {drawdown_multiplier:.2f}")
        logger.info(f"  - Max from Risk: {max_lot_from_risk:.2f}")
        logger.info(f"  - Final Lot: {final_lot:.2f}")
        
        return final_lot
    
    def check_hg_trigger_smart(self, current_price: float) -> List[Dict]:
        """
        ตรวจสอบว่าถึงเงื่อนไขวาง HG หรือยัง (Smart Mode)
        
        Args:
            current_price: ราคาปัจจุบัน
            
        Returns:
            List ของ HG ที่ควรวาง
        """
        triggers = []
        
        # HG Buy - เช็คว่าควรวางหรือไม่
        if config.hg.direction in ['buy', 'both']:
            # เช็คว่ายังไม่มี HG Buy อยู่
            has_buy_hg = any(hg['type'] == 'buy' for hg in self.placed_hg.values())
            
            if not has_buy_hg:
                # เช็คเงื่อนไข Smart Entry
                if self.should_place_hg_at_current_price_smart(current_price, 'buy'):
                    level_key_buy = f"HG_BUY_SMART_{int(current_price)}"
                    
                    if level_key_buy not in self.closed_hg_levels:
                        triggers.append({
                            'level_key': level_key_buy,
                            'price': current_price,
                            'type': 'buy',
                            'level': -1
                        })
        
        # HG Sell - เช็คว่าควรวางหรือไม่
        if config.hg.direction in ['sell', 'both']:
            # เช็คว่ายังไม่มี HG Sell อยู่
            has_sell_hg = any(hg['type'] == 'sell' for hg in self.placed_hg.values())
            
            if not has_sell_hg:
                # เช็คเงื่อนไข Smart Entry
                if self.should_place_hg_at_current_price_smart(current_price, 'sell'):
                    level_key_sell = f"HG_SELL_SMART_{int(current_price)}"
                    
                    if level_key_sell not in self.closed_hg_levels:
                        triggers.append({
                            'level_key': level_key_sell,
                            'price': current_price,
                            'type': 'sell',
                            'level': 1
                        })
        
        return triggers
    
    # ========================================
    # END OF SMART HG FUNCTIONS
    # ========================================
    
    def manage_multiple_hg(self):
        """
        จัดการ HG หลายระดับ
        - ตรวจสอบและวาง HG ใหม่เมื่อถึง trigger
        - ติดตาม breakeven ของ HG ที่เปิดอยู่
        - รีเซ็ต HG เมื่อไม้ Grid หมด
        - รองรับทั้งโหมด Classic และ Smart
        """
        if not self.active or not config.hg.enabled:
            return
        
        # ตรวจสอบว่าต้องรีเซ็ต HG หรือไม่ (เมื่อไม้ Grid หมด)
        self.check_and_reset_hg_if_grid_empty()
        
        # ดึงราคาปัจจุบัน
        price_info = mt5_connection.get_current_price()
        if not price_info:
            return
        
        current_price = price_info['bid']
        
        # อัพเดท start_price เมื่อราคาเคลื่อนไหวไกล (เฉพาะโหมด Classic)
        if config.hg.mode == 'classic':
            self.update_hg_start_price_if_needed(current_price)
        
        # ตรวจสอบว่ามี HG ที่ต้องวางหรือไม่ (เลือกโหมด)
        if config.hg.mode == 'smart':
            logger.info(f"🧠 Using SMART HG Mode")
            triggers = self.check_hg_trigger_smart(current_price)
        else:
            logger.debug(f"📌 Using CLASSIC HG Mode")
            triggers = self.check_hg_trigger(current_price)
        
        for trigger in triggers:
            self.place_hg_order(trigger)
        
        # ติดตามกำไรและตั้ง breakeven
        self.monitor_hg_profit()
    
    def check_and_reset_hg_if_grid_empty(self):
        """
        ตรวจสอบว่าไม้ Grid หมดหรือไม่
        ถ้าหมด ให้รีเซ็ต HG start_price และ placed_hg
        """
        if not self.active or not config.hg.enabled:
            return
        
        # อัพเดท positions
        position_monitor.update_all_positions()
        
        # ตรวจสอบว่ามีไม้ Grid เหลืออยู่ไหม
        grid_positions = position_monitor.grid_positions
        
        # ถ้าไม้ Grid หมด และมี HG อยู่
        if len(grid_positions) == 0 and len(self.placed_hg) > 0:
            logger.info("=" * 60)
            logger.info("⚠️ All Grid positions closed - Resetting HG system...")
            logger.info("=" * 60)
            
            # รีเซ็ต HG
            self.placed_hg = {}
            
            # อัพเดท start_price เป็นราคาปัจจุบัน
            price_info = mt5_connection.get_current_price()
            if price_info:
                self.start_price = price_info['bid']
                logger.info(f"✓ HG System Reset - New start price: {self.start_price:.2f}")
    
    def restore_existing_hg_positions(self):
        """
        จดจำ HG positions ที่มีอยู่แล้วใน MT5 (ผ่าน magic number)
        เพื่อให้สามารถเปิดโปรแกรมใหม่ได้โดยไม่สูญเสียข้อมูล
        """
        logger.info("Restoring existing HG positions...")
        
        # อัพเดท positions
        position_monitor.update_all_positions()
        
        # ดึง HG positions ที่มีอยู่
        hg_positions = position_monitor.hg_positions
        
        if not hg_positions:
            logger.info("No existing HG positions found")
            return 0
        
        # จดจำ HG positions ที่มีอยู่
        restored_count = 0
        for pos in hg_positions:
            # ดึง level_key จาก comment
            comment = pos['comment']
            if config.mt5.comment_hg in comment:
                # แยก level_key จาก comment (format: "HG_HG_BUY_1" หรือ "HG_HG_SELL_2")
                parts = comment.split('_')
                if len(parts) >= 3:
                    # level_key = "HG_BUY_1" หรือ "HG_SELL_2"
                    level_key = '_'.join(parts[1:])  # เอาตั้งแต่ส่วนที่ 2 เป็นต้นไป
                    
                    # ตรวจสอบว่ามี SL ตั้งไว้หรือไม่ (เพื่อดู breakeven_set)
                    breakeven_set = (pos['sl'] != 0.0)
                    
                    # แยก type และ level
                    order_type = parts[2].lower() if len(parts) >= 3 else 'buy'  # buy หรือ sell
                    level_num = int(parts[3]) if len(parts) >= 4 else 1
                    
                    # บันทึกลง placed_hg
                    self.placed_hg[level_key] = {
                        'ticket': pos['ticket'],
                        'open_price': pos['open_price'],
                        'type': order_type,
                        'lot': pos['volume'],
                        'breakeven_set': breakeven_set,
                        'level': level_num if order_type == 'sell' else -level_num
                    }
                    
                    restored_count += 1
                    be_status = "✓ Breakeven" if breakeven_set else "⏳ Monitoring"
                    logger.info(f"Restored HG: {level_key} | Ticket: {pos['ticket']} | Price: {pos['open_price']:.2f} | {be_status}")
        
        logger.info(f"✓ Restored {restored_count} HG positions")
        return restored_count
    
    def start_hg_system(self, start_price: float):
        """
        เริ่มต้นระบบ HG
        
        Args:
            start_price: ราคาเริ่มต้น
        """
        self.start_price = start_price
        self.active = True
        
        # จดจำ HG positions ที่มีอยู่แล้ว (ถ้ามี)
        restored_hg_count = self.restore_existing_hg_positions()
        
        logger.info(f"HG System started at {self.start_price:.2f}")
        logger.info(f"Buy HG:  Distance={config.hg.buy_hg_distance} pips, SL Trigger={config.hg.buy_hg_sl_trigger} pips, " +
                   f"Multiplier={config.hg.buy_hg_multiplier}x, Initial Lot={config.hg.buy_hg_initial_lot}, " +
                   f"Buffer={config.hg.buy_sl_buffer} pips, Max Levels={config.hg.buy_max_hg_levels}")
        logger.info(f"Sell HG: Distance={config.hg.sell_hg_distance} pips, SL Trigger={config.hg.sell_hg_sl_trigger} pips, " +
                   f"Multiplier={config.hg.sell_hg_multiplier}x, Initial Lot={config.hg.sell_hg_initial_lot}, " +
                   f"Buffer={config.hg.sell_sl_buffer} pips, Max Levels={config.hg.sell_max_hg_levels}")
        logger.info(f"Restored {restored_hg_count} existing HG positions")
    
    def stop_hg_system(self, close_positions: bool = False):
        """
        หยุดระบบ HG
        
        Args:
            close_positions: True = ปิด HG positions ทั้งหมด
        """
        self.active = False
        
        if close_positions:
            closed = position_monitor.close_all_hg_positions()
            logger.info(f"HG System stopped - Closed {closed} positions")
        else:
            logger.info("HG System stopped - Positions remain open")
        
        # รีเซ็ต
        self.placed_hg = {}
    
    def get_hg_status(self) -> Dict:
        """
        ดึงสถานะ HG ทั้งหมด
        
        Returns:
            Dict ที่มีข้อมูลสถานะ
        """
        # นับจำนวน HG ที่ตั้ง breakeven แล้ว
        breakeven_count = sum(1 for hg in self.placed_hg.values() if hg['breakeven_set'])
        
        # คำนวณ total HG volume
        total_volume = sum(hg['lot'] for hg in self.placed_hg.values())
        
        return {
            'active': self.active,
            'start_price': self.start_price,
            'total_hg': len(self.placed_hg),
            'breakeven_count': breakeven_count,
            'total_volume': total_volume,
            'hg_positions': list(self.placed_hg.keys())
        }
    
    def get_hg_details(self) -> List[Dict]:
        """
        ดึงรายละเอียด HG positions ทั้งหมด
        
        Returns:
            List ของ HG position details
        """
        details = []
        position_monitor.update_all_positions()
        
        for level_key, hg_data in self.placed_hg.items():
            pos = position_monitor.get_position_by_ticket(hg_data['ticket'])
            
            if pos:
                # คำนวณกำไรเป็น pips
                if hg_data['type'] == 'buy':
                    pips_profit = config.price_to_pips(pos['current_price'] - pos['open_price'])
                else:
                    pips_profit = config.price_to_pips(pos['open_price'] - pos['current_price'])
                
                details.append({
                    'level_key': level_key,
                    'ticket': hg_data['ticket'],
                    'type': hg_data['type'],
                    'lot': hg_data['lot'],
                    'open_price': pos['open_price'],
                    'current_price': pos['current_price'],
                    'profit': pos['profit'],
                    'pips_profit': pips_profit,
                    'breakeven_set': hg_data['breakeven_set'],
                    'sl': pos['sl']
                })
        
        return details


# สร้าง instance หลักสำหรับใช้งาน
hg_manager = HGManager()

