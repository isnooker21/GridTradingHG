# hg_manager.py
# ไฟล์จัดการระบบ Hedge (HG)

from typing import List, Dict, Optional
import time
import logging
from mt5_connection import mt5_connection
from position_monitor import position_monitor
from config import config
from hg_profiles import get_hg_profile
from hg_zone_detector import detect_zones
from atr_calculator import atr_calculator

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
        self.zone_cache: Dict[str, List[Dict]] = {'buy': [], 'sell': [], 'generated_at': 0}
        self.last_zone_refresh = 0.0
        self.current_profile: Optional[Dict] = None
        self.active_zone_ids = set()
    
    def _get_active_profile(self) -> Dict:
        plan = getattr(config.grid, "auto_plan", {}) or {}
        distance = int(plan.get('requested_distance', config.grid.auto_resilience_distance))
        profile = get_hg_profile(distance)
        self.current_profile = profile
        return profile
    
    def _refresh_zones_if_needed(self):
        profile = self._get_active_profile()
        refresh_secs = profile['zone_refresh_secs']
        now = time.time()
        if now - self.last_zone_refresh < refresh_secs:
            return
        if not mt5_connection.connected:
            return
        
        rates = mt5_connection.get_recent_rates(count=profile['lookback_bars'])
        if not rates:
            return
        
        atr_value = atr_calculator.calculate_atr()
        if atr_value is None or atr_value <= 0:
            atr_value = profile['fallback_distance_factor'] * config.grid.buy_grid_distance
        
        zones = detect_zones(atr_value, profile, rates)
        self.zone_cache = zones
        self.last_zone_refresh = now
        current_ids = {zone['id'] for zone in zones.get('buy', [])} | {zone['id'] for zone in zones.get('sell', [])}
        self.active_zone_ids = {zone_id for zone_id in self.active_zone_ids if zone_id in current_ids}
    
    def _build_zone_trigger(self, zone: Dict, hg_type: str, current_price: float) -> Dict:
        profile = self.current_profile or self._get_active_profile()
        level_key = f"HG_ZONE_{hg_type.upper()}_{zone['id']}"
        partial_trigger = max(5.0, zone['width_pips'] * profile['partial_close_trigger_factor'])
        return {
            'level_key': level_key,
            'price': current_price,
            'type': hg_type,
            'level': 0,
            'source': 'zone',
            'zone_id': zone['id'],
            'zone_width_pips': zone['width_pips'],
            'partial_close_ratio': profile['partial_close_ratio'],
            'partial_close_trigger_pips': partial_trigger,
            'zone_score': zone['score'],
        }
    
    def _get_zone_triggers(self, current_price: float) -> List[Dict]:
        triggers: List[Dict] = []
        profile = self.current_profile or self._get_active_profile()
        if not self.zone_cache:
            return triggers
        
        allowed = []
        if config.hg.direction in ['buy', 'both']:
            allowed.append('buy')
        if config.hg.direction in ['sell', 'both']:
            allowed.append('sell')
        
        for zone_type in allowed:
            for zone in self.zone_cache.get(zone_type, []):
                if zone['id'] in self.active_zone_ids:
                    continue
                if zone['lower'] <= current_price <= zone['upper']:
                    trigger = self._build_zone_trigger(zone, zone_type, current_price)
                    triggers.append(trigger)
                    self.active_zone_ids.add(zone['id'])
        return triggers
        
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
        
        Args:
            hg_type: 'buy' หรือ 'sell'
        
        Returns:
            lot size สำหรับ HG
        """
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
        
        # กำหนด comment สำหรับ HG (ใช้ comment_hg เสมอเพื่อให้แยกประเภทได้ชัดเจน)
        comment = config.mt5.comment_hg
        
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
                'level': hg_info.get('level'),
                'source': hg_info.get('source', 'distance'),
                'zone_id': hg_info.get('zone_id'),
                'zone_width_pips': hg_info.get('zone_width_pips'),
                'partial_close_ratio': hg_info.get('partial_close_ratio'),
                'partial_close_trigger_pips': hg_info.get('partial_close_trigger_pips'),
                'partial_closed': False,
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
        
        # ใช้ list() เพื่อสร้าง copy ของ keys เพื่อป้องกันปัญหาเมื่อลบ element ขณะ iterate
        for level_key in list(self.placed_hg.keys()):
            hg_data = self.placed_hg[level_key]
            # ตรวจสอบว่า position ยังเปิดอยู่หรือไม่
            pos = position_monitor.get_position_by_ticket(hg_data['ticket'])
            
            if pos is None:
                # Position ถูกปิดแล้ว (SL/TP)
                logger.info(f"HG closed: {level_key}")
                # เพิ่มลง closed_hg_levels เพื่อไม่ให้วางซ้ำ
                self.closed_hg_levels.add(level_key)
                zone_id = hg_data.get('zone_id')
                if zone_id in self.active_zone_ids:
                    self.active_zone_ids.discard(zone_id)
                # ลบออกจาก placed_hg เพื่อไม่ให้ log ซ้ำอีก
                del self.placed_hg[level_key]
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
            
            # Partial close สำหรับ zone-based HG
            if hg_data.get('source') == 'zone' and not hg_data.get('partial_closed'):
                trigger_pips = hg_data.get('partial_close_trigger_pips')
                ratio = hg_data.get('partial_close_ratio') or (self.current_profile or {}).get('partial_close_ratio', 0.5)
                if trigger_pips and pips_profit >= trigger_pips and ratio > 0:
                    self._execute_partial_close(hg_data, pos, ratio)
            
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
    
    def _execute_partial_close(self, hg_data: Dict, position: Dict, ratio: float):
        """
        ปิดบางส่วนของ HG position ตามอัตราส่วนที่กำหนด
        """
        try:
            volume = position['volume'] * ratio
            if volume <= 0:
                return
            success = mt5_connection.close_partial_order(hg_data['ticket'], volume)
            if success:
                hg_data['partial_closed'] = True
                logger.info(f"Partial close executed for HG ticket {hg_data['ticket']} (ratio {ratio:.2f})")
            else:
                logger.warning(f"Partial close failed for HG ticket {hg_data['ticket']}")
        except Exception as e:
            logger.error(f"Error during partial close: {e}")
    
    def manage_multiple_hg(self, current_price: float):
        """
        จัดการระบบ HG แบบหลายระดับ
        
        Args:
            current_price: ราคาปัจจุบัน
        """
        if not self.active or not config.hg.enabled:
            return
        
        # อัพเดท start_price ถ้าจำเป็น
        self.update_hg_start_price_if_needed(current_price)
        
        # อัพเดท zone profile และตรวจสอบ zone triggers
        self._refresh_zones_if_needed()
        triggers = self._get_zone_triggers(current_price)
        
        # ตรวจสอบ HG triggers จากระยะคงที่ (fallback)
        triggers.extend(self.check_hg_trigger(current_price))
        
        # วาง HG orders
        for trigger in triggers:
            self.place_hg_order(trigger)
        
        # ติดตามกำไรและตั้ง breakeven
        self.monitor_hg_profit()
    
    def start_hg_system(self, start_price: float):
        """
        เริ่มระบบ HG
        
        Args:
            start_price: ราคาเริ่มต้น
        """
        self.active = True
        self.start_price = start_price
        self.placed_hg = {}
        self.closed_hg_levels = set()
        
        logger.info(f"HG System started at price: {start_price:.2f}")
        logger.info(f"HG Direction: {config.hg.direction}")
        logger.info(f"Buy HG Distance: {config.hg.buy_hg_distance} pips")
        logger.info(f"Sell HG Distance: {config.hg.sell_hg_distance} pips")
    
    def stop_hg_system(self):
        """
        หยุดระบบ HG
        """
        self.active = False
        logger.info("HG System stopped")
    
    def get_hg_status(self) -> Dict:
        """
        รับสถานะของระบบ HG
        
        Returns:
            ข้อมูลสถานะ HG
        """
        return {
            'active': self.active,
            'start_price': self.start_price,
            'placed_hg_count': len(self.placed_hg),
            'closed_hg_count': len(self.closed_hg_levels),
            'placed_hg': self.placed_hg,
            'closed_hg_levels': list(self.closed_hg_levels)
        }
    
    # ========================================
    # END OF HG FUNCTIONS
    # ========================================