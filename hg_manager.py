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
        self.last_hg_entry_price = {'buy': None, 'sell': None}
        self.last_price: Optional[float] = None
    
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
        direction_setting = config.grid.direction if config.grid.auto_mode else config.hg.direction
        zone_map: Dict[str, str] = {}
        if direction_setting == 'buy':
            zone_map['sell'] = 'sell'
        elif direction_setting == 'sell':
            zone_map['buy'] = 'buy'
        elif direction_setting == 'both':
            zone_map = {'buy': 'buy', 'sell': 'sell'}
        
        prev_price = self.last_price
        for zone_type, hg_type in zone_map.items():
            for zone in self.zone_cache.get(zone_type, []):
                if zone['id'] in self.active_zone_ids:
                    continue
                
                in_zone = zone['lower'] <= current_price <= zone['upper']
                if not in_zone:
                    continue
                
                if prev_price is not None:
                    if zone_type == 'buy' and not (prev_price >= zone['upper']):
                        continue
                    if zone_type == 'sell' and not (prev_price <= zone['lower']):
                        continue
                
                last_price = self.last_hg_entry_price.get(hg_type)
                min_spacing_pips = max(5.0, (zone.get('width_pips') or 0) * 0.5)
                if last_price is not None:
                    if abs(current_price - last_price) < config.pips_to_price(min_spacing_pips):
                        continue
                
                trigger = self._build_zone_trigger(zone, hg_type, current_price)
                triggers.append(trigger)
                self.active_zone_ids.add(zone['id'])
        return triggers
        
    def check_hg_trigger(self, current_price: float, direction_mode: Optional[str] = None) -> List[Dict]:
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
        
        direction_setting = direction_mode or config.hg.direction
        
        # HG Buy (ด้านล่าง)
        if direction_setting in ['buy', 'both']:
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
        
        # HG Sell (ด้านบน)
        if direction_setting in ['sell', 'both']:
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
    
    def calculate_hg_lot(self, hg_type: str = 'buy', context: Optional[Dict] = None) -> float:
        """
        คำนวณ lot size สำหรับ HG (ใช้ multiplier และ initial lot แยก Buy/Sell)
        HG Lot = max(Grid Exposure × multiplier, Initial Lot)
        
        Args:
            hg_type: 'buy' หรือ 'sell'
        
        Returns:
            lot size สำหรับ HG
        """
        profile = self.current_profile or self._get_active_profile()
        plan = getattr(config.grid, "auto_plan", {}) or {}
        balance = float(plan.get('balance', 0.0) or 0.0)
        lot_size = max(config.grid.buy_lot_size if hg_type == 'buy' else config.grid.sell_lot_size, 0.01)
        margin_per_position = plan.get('margin_per_position')
        margin_per_lot = None
        if margin_per_position and lot_size > 0:
            margin_per_lot = margin_per_position / lot_size
        else:
            margin_per_lot = plan.get('margin_per_position') or 0.0
        balance_cap_lot = 0.0
        if balance > 0 and margin_per_lot:
            balance_cap_lot = (balance * profile['hg_lot_balance_pct']) / margin_per_lot
        
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
        
        # คำนวณ HG lot จาก exposure
        hg_lot = net_volume * multiplier
        
        # ปรับตาม zone score (ถ้ามี)
        if context and context.get('zone_score'):
            score_weight = 1.0 + context['zone_score'] * profile['score_lot_weight']
            hg_lot *= score_weight
        
        # ใช้ค่าที่มากกว่าระหว่าง calculated lot กับ initial lot
        hg_lot = max(hg_lot, initial_lot)
        
        if balance_cap_lot > 0:
            hg_lot = min(hg_lot, balance_cap_lot)
        
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
        hg_lot = self.calculate_hg_lot(hg_info['type'], context=hg_info)
        
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
            self.last_hg_entry_price[hg_info['type']] = hg_info['price']
            
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
        
        try:
            # อัพเดท positions
            position_monitor.update_all_positions()
        except Exception as e:
            logger.error(f"Error updating positions in monitor_hg_profit: {e}")
            return
        
        # ใช้ list() เพื่อสร้าง copy ของ keys เพื่อป้องกันปัญหาเมื่อลบ element ขณะ iterate
        for level_key in list(self.placed_hg.keys()):
            try:
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
                # แต่ถ้า SL ยังไม่ได้ถูกตั้งจริงใน MT5 ให้ตั้งใหม่
                if hg_data.get('breakeven_set'):
                    # ตรวจสอบว่า SL ถูกตั้งจริงหรือไม่ (อัพเดท position ใหม่)
                    if not pos.get('sl') or pos.get('sl') == 0.0:
                        # SL ไม่ได้ถูกตั้งจริง แม้ว่า flag จะบอกว่า set แล้ว
                        hg_data['breakeven_set'] = False
                    else:
                        # SL ถูกตั้งแล้ว ข้ามไป
                        continue
                
                # คำนวณกำไรเป็น pips
                if hg_data['type'] == 'buy':
                    pips_profit = config.price_to_pips(pos['current_price'] - pos['open_price'])
                    # ใน Auto Mode ให้ใช้ sl_trigger จาก auto plan (ถ้ามี) ไม่งั้นใช้จาก config
                    if config.grid.auto_mode:
                        plan = getattr(config.grid, "auto_plan", {}) or {}
                        sl_trigger = plan.get("buy_hg_sl_trigger") or config.hg.buy_hg_sl_trigger
                    else:
                        sl_trigger = config.hg.buy_hg_sl_trigger
                else:  # sell
                    pips_profit = config.price_to_pips(pos['open_price'] - pos['current_price'])
                    # ใน Auto Mode ให้ใช้ sl_trigger จาก auto plan (ถ้ามี) ไม่งั้นใช้จาก config
                    if config.grid.auto_mode:
                        plan = getattr(config.grid, "auto_plan", {}) or {}
                        sl_trigger = plan.get("sell_hg_sl_trigger") or config.hg.sell_hg_sl_trigger
                    else:
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
            except Exception as e:
                logger.error(f"Error monitoring HG profit for {level_key}: {e}", exc_info=True)
                # ทำงานต่อกับ HG ตัวถัดไป แม้ว่าตัวนี้จะมี error
                continue
    
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
        try:
            success = mt5_connection.modify_order(
                ticket=hg_data['ticket'],
                sl=sl_price
            )
            
            if success:
                # ตรวจสอบว่า SL ถูกตั้งจริงหรือไม่ (อัพเดท position ใหม่)
                position_monitor.update_all_positions()
                updated_pos = position_monitor.get_position_by_ticket(hg_data['ticket'])
                if updated_pos and updated_pos.get('sl'):
                    hg_data['breakeven_set'] = True
                else:
                    logger.warning(f"HG Breakeven SL not confirmed: Ticket {hg_data['ticket']}")
            else:
                logger.error(f"Failed to set HG Breakeven SL: Ticket {hg_data['ticket']}")
        except Exception as e:
            logger.error(f"Error setting HG Breakeven SL for ticket {hg_data['ticket']}: {e}", exc_info=True)
    
    def _execute_partial_close(self, hg_data: Dict, position: Dict, ratio: float):
        """
        ปิดบางส่วนของ HG position ตามอัตราส่วนที่กำหนด
        """
        try:
            volume = position['volume'] * ratio
            if volume <= 0:
                return
            volume_step = 0.01
            volume = max(volume_step, round(volume / volume_step) * volume_step)
            
            # คำนวณกำไรที่คาดว่าจะได้จาก partial close (ก่อนปิดจริง)
            # ใช้ profit ต่อ lot คูณด้วย volume ที่จะปิด
            profit_per_lot = position['profit'] / position['volume'] if position['volume'] > 0 else 0
            expected_profit = profit_per_lot * volume
            
            success = mt5_connection.close_partial_order(hg_data['ticket'], volume)
            if success:
                hg_data['partial_closed'] = True
                logger.info(f"Partial close executed for HG ticket {hg_data['ticket']} (ratio {ratio:.2f}, expected profit: ${expected_profit:.2f})")
                # ส่ง expected_profit ไปให้ _close_highest_loss_grid เพื่อเช็คว่าควรปิด Grid หรือไม่
                self._close_highest_loss_grid(expected_profit)
            else:
                logger.warning(f"Partial close failed for HG ticket {hg_data['ticket']}")
        except Exception as e:
            logger.error(f"Error during partial close: {e}")
    
    def _close_highest_loss_grid(self, available_profit: float = 0.0):
        """
        ปิดไม้ Grid ที่ขาดทุนมากที่สุดหนึ่งไม้ (ช่วยลด DD เมื่อ HG ทำกำไร)
        แต่จะปิดเฉพาะเมื่อกำไรจาก HG >= ขาดทุนของ Grid (ไม่ให้ขาดทุน)
        
        Args:
            available_profit: กำไรที่ได้จาก HG partial close (USD)
        """
        position_monitor.update_all_positions()
        worst = None
        for pos in position_monitor.grid_positions:
            if worst is None or pos['profit'] < worst['profit']:
                worst = pos
        
        if worst and worst['profit'] < 0:
            # เช็คว่ากำไรจาก HG >= ขาดทุนของ Grid (ใช้ค่าสัมบูรณ์)
            grid_loss = abs(worst['profit'])
            if available_profit >= grid_loss:
                logger.info(f"Closing worst grid position ticket {worst['ticket']} (loss: ${grid_loss:.2f}, covered by HG profit: ${available_profit:.2f})")
                mt5_connection.close_order(worst['ticket'])
            else:
                logger.debug(f"Skipping grid close: HG profit ${available_profit:.2f} < Grid loss ${grid_loss:.2f}")
        else:
            logger.debug("No grid position requires closing after partial HG profit.")
    
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
        
        prev_price = self.last_price
        self.last_price = current_price
        
        # อัพเดท zone profile และตรวจสอบ zone triggers
        self._refresh_zones_if_needed()
        triggers = self._get_zone_triggers(current_price)
        
        # ตรวจสอบ HG triggers จากระยะคงที่ (fallback) วิเคราะห์ทิศตรงข้าม
        direction_setting = config.grid.direction if config.grid.auto_mode else config.hg.direction
        if direction_setting == 'buy':
            fallback_direction = 'sell'
        elif direction_setting == 'sell':
            fallback_direction = 'buy'
        else:
            fallback_direction = 'both'
        triggers.extend(self.check_hg_trigger(current_price, fallback_direction))
        
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
        self.last_hg_entry_price = {'buy': None, 'sell': None}
        
        restored = self.restore_existing_hg_positions()
        
        logger.info(f"HG System started at price: {start_price:.2f}")
        logger.info(f"HG Direction: {config.hg.direction}")
        logger.info(f"Buy HG Distance: {config.hg.buy_hg_distance} pips")
        logger.info(f"Sell HG Distance: {config.hg.sell_hg_distance} pips")
        if restored:
            logger.info(f"✓ Restored {restored} HG positions from MT5")
        else:
            logger.info("No existing HG positions found - will start fresh")
    
    def stop_hg_system(self):
        """
        หยุดระบบ HG
        """
        self.active = False
        logger.info("HG System stopped")
    
    def restore_existing_hg_positions(self) -> int:
        """
        ตรวจจับ HG positions ที่เปิดอยู่ใน MT5 เพื่อให้ระบบสามารถทำงานต่อเนื่องหลังรีสตาร์ท
        
        Returns:
            จำนวน HG positions ที่กู้คืนได้
        """
        try:
            position_monitor.update_all_positions()
            profile = self.current_profile or self._get_active_profile()
            restored = 0
            
            for pos in position_monitor.hg_positions:
                ticket = pos['ticket']
                level_key = f"HG_RESTORE_{ticket}"
                
                # ตรวจสอบว่าเราเคยเก็บไว้แล้วหรือยัง
                if level_key in self.placed_hg:
                    continue
                
                entry_type = pos['type']
                has_sl = pos.get('sl') not in (None, 0.0)
                
                self.placed_hg[level_key] = {
                    'ticket': ticket,
                    'open_price': pos['open_price'],
                    'type': entry_type,
                    'lot': pos['volume'],
                    'breakeven_set': has_sl,
                    'level': None,
                    'source': 'restored',
                    'zone_id': None,
                    'zone_width_pips': None,
                    'partial_close_ratio': profile.get('partial_close_ratio'),
                    'partial_close_trigger_pips': None,
                    'partial_closed': False,
                }
                
                self.last_hg_entry_price[entry_type] = pos['open_price']
                restored += 1
            
            return restored
        except Exception as e:
            logger.error(f"Error restoring HG positions: {e}", exc_info=True)
            return 0
    
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