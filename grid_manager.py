# grid_manager.py
# ไฟล์จัดการระบบ Grid Trading

from typing import List, Dict, Optional
import logging
import time
from mt5_connection import mt5_connection
from position_monitor import position_monitor
from config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GridManager:
    """คลาสจัดการระบบ Grid Trading"""
    
    def __init__(self):
        self.active = False
        self.grid_levels = []  # เก็บระดับราคา Grid ที่วางไว้
        self.placed_orders = {}  # เก็บ ticket และข้อมูล orders ที่วางไว้
        self.start_price = 0.0
        self.last_order_time = {}  # เก็บเวลาล่าสุดที่วางไม้แต่ละประเภท
        self.placing_order_lock = False  # Lock เพื่อป้องกันการวางไม้พร้อมกัน
        self.order_counter = 0  # นับจำนวนไม้ที่วางไปแล้วทั้งหมด (ไม่ซ้ำแน่นอน)
    
    def place_initial_orders(self, current_price: float):
        """
        วางออเดอร์เริ่มต้น: Buy 1 ไม้ + Sell 1 ไม้ ที่ราคาปัจจุบัน
        
        Args:
            current_price: ราคาปัจจุบัน
        """
        if not self.active:
            return
        
        logger.info("Placing initial orders...")
        logger.info(f"Direction setting: {config.grid.direction}")
        
        orders_placed = 0
        
        # วาง Buy order (ใช้ค่า Buy)
        if config.grid.direction in ['buy', 'both']:
            buy_tp_distance = config.pips_to_price(config.grid.buy_take_profit)
            buy_tp = current_price + buy_tp_distance
            
            # ใช้ comment ตาม mode
            comment = config.mt5.comment_auto if config.grid.auto_mode else config.mt5.comment_grid
            ticket = mt5_connection.place_order(
                order_type='buy',
                volume=config.grid.buy_lot_size,
                tp=buy_tp,
                comment=comment
            )
            
            if ticket:
                self.placed_orders['initial_buy'] = ticket
                self.grid_levels.append({
                    'level_key': 'initial_buy',
                    'price': current_price,
                    'type': 'buy',
                    'tp': buy_tp,
                    'placed': True,
                    'ticket': ticket
                })
                orders_placed += 1
                logger.info(f"Initial BUY placed: {config.grid.buy_lot_size} lots at {current_price:.2f} | TP: {buy_tp:.2f} | Ticket: {ticket}")
        
        # วาง Sell order (ใช้ค่า Sell)
        if config.grid.direction in ['sell', 'both']:
            sell_tp_distance = config.pips_to_price(config.grid.sell_take_profit)
            sell_tp = current_price - sell_tp_distance
            
            # ใช้ comment ตาม mode
            comment = config.mt5.comment_auto if config.grid.auto_mode else config.mt5.comment_grid
            ticket = mt5_connection.place_order(
                order_type='sell',
                volume=config.grid.sell_lot_size,
                tp=sell_tp,
                comment=comment
            )
            
            if ticket:
                self.placed_orders['initial_sell'] = ticket
                self.grid_levels.append({
                    'level_key': 'initial_sell',
                    'price': current_price,
                    'type': 'sell',
                    'tp': sell_tp,
                    'placed': True,
                    'ticket': ticket
                })
                orders_placed += 1
                logger.info(f"Initial SELL placed: {config.grid.sell_lot_size} lots at {current_price:.2f} | TP: {sell_tp:.2f} | Ticket: {ticket}")
        
        logger.info(f"✓ Initial orders placed: {orders_placed} orders")
        logger.info(f"Buy: Distance={config.grid.buy_grid_distance} pips, Lot={config.grid.buy_lot_size}, TP={config.grid.buy_take_profit} pips")
        logger.info(f"Sell: Distance={config.grid.sell_grid_distance} pips, Lot={config.grid.sell_lot_size}, TP={config.grid.sell_take_profit} pips")
    
    def monitor_grid_positions(self):
        """
        ติดตาม Grid positions และวางใหม่เมื่อปิด
        """
        if not self.active:
            return
        
        # อัพเดท positions
        position_monitor.update_all_positions()
        
        # ตรวจสอบ Grid positions ที่ถูกปิดแล้ว
        for grid in self.grid_levels[:]:  # ใช้ slice เพื่อป้องกันปัญหาเมื่อลบ element
            if not grid['placed'] or 'ticket' not in grid:
                continue
            
            # ตรวจสอบว่า position ยังเปิดอยู่หรือไม่
            pos = position_monitor.get_position_by_ticket(grid['ticket'])
            
            if pos is None:
                # Position ถูกปิดแล้ว (ถึง TP)
                logger.info(f"Grid closed: {grid['level_key']} at {grid['price']:.2f}")
                
                # ลบออกจาก list
                self.grid_levels.remove(grid)
                if grid['level_key'] in self.placed_orders:
                    del self.placed_orders[grid['level_key']]
                
                # วางไม้ใหม่ทันทีเมื่อไม้ TP (เพื่อให้มีไม้ต่อเนื่อง)
                self.place_replacement_order_after_tp(grid['type'])
    
    def place_replacement_order_after_tp(self, order_type: str):
        """
        วางไม้ใหม่เมื่อไม้ TP ปิดไป (มีป้องกันการวางซ้ำ)
        
        Args:
            order_type: 'buy' หรือ 'sell'
        """
        # ตรวจสอบว่ามี Order ใหม่เกิดขึ้นในระบบหรือไม่
        if self.check_recent_orders():
            logger.warning("Recent orders found - preventing duplicate replacement")
            return None
        
        # ตรวจสอบว่า Order ที่ส่งไปสำเร็จจริงหรือไม่
        if self.check_pending_orders():
            logger.warning("Pending orders found - waiting for completion")
            return None
        
        # ดึงราคาปัจจุบัน
        price_info = mt5_connection.get_current_price()
        if not price_info:
            return
        
        current_price = price_info['bid']
        
        # ตรวจสอบโหมดที่ตั้งไว้
        if order_type == 'buy' and config.grid.direction not in ['buy', 'both']:
            return
        if order_type == 'sell' and config.grid.direction not in ['sell', 'both']:
            return
        
        # อัพเดท positions เพื่อเช็คไม้ที่มีอยู่
        position_monitor.update_all_positions()
        grid_positions = position_monitor.grid_positions
        
        # ตรวจสอบว่ามีไม้อยู่ใกล้ราคาปัจจุบันไหม (ป้องกันการวางซ้ำ)
        grid_distance_price = config.pips_to_price(config.grid.grid_distance)
        nearby_distance = grid_distance_price * 0.5
        has_nearby_order = False
        
        for pos in grid_positions:
            if pos['type'] == order_type and abs(pos['open_price'] - current_price) < nearby_distance:
                has_nearby_order = True
                break
        
        # ถ้าไม่มีไม้อยู่ใกล้ → วางไม้ใหม่
        if not has_nearby_order:
            if order_type == 'buy':
                self.place_new_buy_order(current_price)
                logger.info(f"✓ Replacement BUY placed after TP at {current_price:.2f}")
            else:
                self.place_new_sell_order(current_price)
                logger.info(f"✓ Replacement SELL placed after TP at {current_price:.2f}")
        else:
            logger.info(f"⚠ Skipped replacement {order_type.upper()} - nearby order exists at {current_price:.2f}")
    
    def check_recent_orders(self) -> bool:
        """
        ตรวจสอบว่ามี Order ใหม่เกิดขึ้นในระบบหรือไม่
        ตรวจสอบจาก MT5 positions, placed_orders, grid_levels
        
        Returns:
            True ถ้ามี Order ใหม่เกิดขึ้น
        """
        try:
            # อัพเดท positions
            position_monitor.update_all_positions()
            grid_positions = position_monitor.grid_positions
            
            # ซิงค์ placed_orders กับ MT5 positions เพื่อลบ order ที่ปิดไปแล้ว
            tickets_in_mt5 = [pos['ticket'] for pos in grid_positions]
            for level_key, ticket in list(self.placed_orders.items()):
                if ticket not in tickets_in_mt5:
                    # Order นี้ปิดไปแล้ว ลบออก
                    del self.placed_orders[level_key]
                    logger.debug(f"Removed closed order: {level_key} ({ticket})")
            
            # ตรวจสอบจาก MT5 positions
            for pos in grid_positions:
                if pos['ticket'] not in self.placed_orders.values():
                    logger.warning(f"Recent order found in MT5: {pos['ticket']} - preventing duplicate")
                    return True
            
            # ตรวจสอบจาก placed_orders
            for level_key, ticket in self.placed_orders.items():
                if ticket not in [p['ticket'] for p in grid_positions]:
                    logger.warning(f"Recent order found in placed_orders: {ticket} - preventing duplicate")
                    return True
            
            # ตรวจสอบจาก grid_levels
            for grid in self.grid_levels:
                if grid['ticket'] not in [p['ticket'] for p in grid_positions]:
                    logger.warning(f"Recent order found in grid_levels: {grid['ticket']} - preventing duplicate")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking recent orders: {e}")
            return False
    
    def check_pending_orders(self) -> bool:
        """
        ตรวจสอบว่า Order ที่ส่งไปสำเร็จจริงหรือไม่
        
        Returns:
            True ถ้ามี Order ที่ยังไม่สำเร็จ
        """
        try:
            # อัพเดท positions
            position_monitor.update_all_positions()
            grid_positions = position_monitor.grid_positions
            
            # ตรวจสอบว่ามี position ใหม่เกิดขึ้นหรือไม่
            for pos in grid_positions:
                if pos['ticket'] not in self.placed_orders.values():
                    logger.warning(f"Pending order found: {pos['ticket']} - waiting for completion")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking pending orders: {e}")
            return False

    def place_new_buy_order(self, current_price: float):
        """
        วาง Buy order ใหม่ (ใช้ค่า Buy) พร้อมป้องกันการวางซ้ำ
        """
        # ตรวจสอบว่ามี Order ใหม่เกิดขึ้นในระบบหรือไม่
        if self.check_recent_orders():
            logger.warning("Recent orders found - preventing duplicate")
            return None
        
        # ตรวจสอบว่า Order ที่ส่งไปสำเร็จจริงหรือไม่
        if self.check_pending_orders():
            logger.warning("Pending orders found - waiting for completion")
            return None
        
        # ป้องกันการวางพร้อมกัน (Lock)
        if self.placing_order_lock:
            logger.warning("⚠️ Order placement locked - preventing duplicate order")
            return
        
        try:
            self.placing_order_lock = True
            
            # เช็คซ้ำอีกครั้งว่ามีไม้ใกล้เคียงหรือไม่ (ป้องกันการวางซ้ำ)
            position_monitor.update_all_positions()
            grid_positions = position_monitor.grid_positions
            
            buy_grid_distance_price = config.pips_to_price(config.grid.buy_grid_distance)
            min_distance = buy_grid_distance_price * 0.3  # ลดเหลือ 30% เพื่อป้องกันเข้มงวดขึ้น
            
            for pos in grid_positions:
                if pos['type'] == 'buy':
                    distance = abs(pos['open_price'] - current_price)
                    if distance < min_distance:
                        logger.warning(f"⚠️ DUPLICATE PREVENTED: BUY order too close ({distance:.2f} < {min_distance:.2f}) to existing position at {pos['open_price']:.2f}")
                        return
            
            tp_distance = config.pips_to_price(config.grid.buy_take_profit)
            tp_price = current_price + tp_distance
            
            # สร้าง level_key ที่ไม่ซ้ำแน่นอน (ใช้ counter)
            self.order_counter += 1
            level_key = f"buy_{self.order_counter}"
            
            # เช็คว่า level_key ซ้ำหรือไม่
            while level_key in self.placed_orders:
                self.order_counter += 1
                level_key = f"buy_{self.order_counter}"
            
            # ใช้ comment ตาม mode
            comment = config.mt5.comment_auto if config.grid.auto_mode else config.mt5.comment_grid
            
            # วาง order
            ticket = mt5_connection.place_order(
                order_type='buy',
                volume=config.grid.buy_lot_size,
                tp=tp_price,
                comment=comment
            )
            
            # ตรวจสอบว่า Order สำเร็จจริงหรือไม่
            if ticket:
                # สำเร็จแล้ว
                self.placed_orders[level_key] = ticket
                self.grid_levels.append({
                    'level_key': level_key,
                    'price': current_price,
                    'type': 'buy',
                    'tp': tp_price,
                    'placed': True,
                    'ticket': ticket
                })
                
                logger.info(f"✓ New BUY placed: {config.grid.buy_lot_size} lots at {current_price:.2f} | TP: {tp_price:.2f} | Ticket: {ticket} | ID: {level_key}")
            else:
                # ล้มเหลว ไม่ retry เพื่อป้องกัน hang (จะลองใหม่ในรอบถัดไป)
                logger.warning(f"Order placement failed - will retry in next cycle")
        finally:
            self.placing_order_lock = False
    
    def place_new_sell_order(self, current_price: float):
        """
        วาง Sell order ใหม่ (ใช้ค่า Sell) พร้อมป้องกันการวางซ้ำ
        """
        # ตรวจสอบว่ามี Order ใหม่เกิดขึ้นในระบบหรือไม่
        if self.check_recent_orders():
            logger.warning("Recent orders found - preventing duplicate")
            return None
        
        # ตรวจสอบว่า Order ที่ส่งไปสำเร็จจริงหรือไม่
        if self.check_pending_orders():
            logger.warning("Pending orders found - waiting for completion")
            return None
        
        # ป้องกันการวางพร้อมกัน (Lock)
        if self.placing_order_lock:
            logger.warning("⚠️ Order placement locked - preventing duplicate order")
            return
        
        try:
            self.placing_order_lock = True
            
            # เช็คซ้ำอีกครั้งว่ามีไม้ใกล้เคียงหรือไม่ (ป้องกันการวางซ้ำ)
            position_monitor.update_all_positions()
            grid_positions = position_monitor.grid_positions
            
            sell_grid_distance_price = config.pips_to_price(config.grid.sell_grid_distance)
            min_distance = sell_grid_distance_price * 0.3  # ลดเหลือ 30% เพื่อป้องกันเข้มงวดขึ้น
            
            for pos in grid_positions:
                if pos['type'] == 'sell':
                    distance = abs(pos['open_price'] - current_price)
                    if distance < min_distance:
                        logger.warning(f"⚠️ DUPLICATE PREVENTED: SELL order too close ({distance:.2f} < {min_distance:.2f}) to existing position at {pos['open_price']:.2f}")
                        return
            
            tp_distance = config.pips_to_price(config.grid.sell_take_profit)
            tp_price = current_price - tp_distance
            
            # สร้าง level_key ที่ไม่ซ้ำแน่นอน (ใช้ counter)
            self.order_counter += 1
            level_key = f"sell_{self.order_counter}"
            
            # เช็คว่า level_key ซ้ำหรือไม่
            while level_key in self.placed_orders:
                self.order_counter += 1
                level_key = f"sell_{self.order_counter}"
            
            # ใช้ comment ตาม mode
            comment = config.mt5.comment_auto if config.grid.auto_mode else config.mt5.comment_grid
            
            # วาง order
            ticket = mt5_connection.place_order(
                order_type='sell',
                volume=config.grid.sell_lot_size,
                tp=tp_price,
                comment=comment
            )
            
            # ตรวจสอบว่า Order สำเร็จจริงหรือไม่
            if ticket:
                # สำเร็จแล้ว
                self.placed_orders[level_key] = ticket
                self.grid_levels.append({
                    'level_key': level_key,
                    'price': current_price,
                    'type': 'sell',
                    'tp': tp_price,
                    'placed': True,
                    'ticket': ticket
                })
                
                logger.info(f"✓ New SELL placed: {config.grid.sell_lot_size} lots at {current_price:.2f} | TP: {tp_price:.2f} | Ticket: {ticket} | ID: {level_key}")
            else:
                # ล้มเหลว ไม่ retry เพื่อป้องกัน hang (จะลองใหม่ในรอบถัดไป)
                logger.warning(f"Order placement failed - will retry in next cycle")
        finally:
            self.placing_order_lock = False
    
    
    def update_grid_status(self):
        """
        อัพเดทสถานะ Grid ทั้งหมด
        """
        if not self.active:
            return
        
        # 🆕 ถ้าเปิด Auto Mode → ตรวจสอบว่าควรอัพเดทค่าหรือยัง
        if config.grid.auto_mode:
            self.check_and_update_auto_settings()
        
        # ติดตาม Grid positions
        self.monitor_grid_positions()
        
        # ตรวจสอบว่ามีไม้เหลืออยู่ไหม ถ้าไม่มีให้วางใหม่
        self.check_and_restart_if_no_positions()
        
        # ตรวจสอบ Grid Distance และวางไม้ใหม่
        self.check_grid_distance_and_place_orders()
    
    def check_and_update_auto_settings(self):
        """
        เช็คว่าควรอัพเดท Auto Settings หรือยัง (ทุก 15 นาที)
        """
        from datetime import datetime, timedelta
        
        try:
            current_time = datetime.now()
            
            # เช็คว่าผ่านไป 15 นาทีหรือยัง
            if config.grid.last_auto_update is None:
                should_update = True
            else:
                time_diff = (current_time - config.grid.last_auto_update).total_seconds()
                should_update = time_diff >= 900  # 15 minutes = 900 seconds
            
            if should_update:
                logger.info("🔄 Auto Mode: Updating settings...")
                
                # คำนวณค่าใหม่
                from auto_config_manager import auto_config_manager
                new_settings = auto_config_manager.calculate_auto_settings(
                    risk_profile=config.grid.risk_profile
                )
                
                # อัพเดทค่าใน config
                config.update_grid_settings(
                    direction=new_settings['direction'],
                    buy_grid_distance=new_settings['buy_grid_distance'],
                    sell_grid_distance=new_settings['sell_grid_distance']
                )
                config.update_hg_settings(
                    buy_hg_distance=new_settings['buy_hg_distance'],
                    sell_hg_distance=new_settings['sell_hg_distance'],
                    buy_hg_sl_trigger=new_settings['buy_hg_sl_trigger'],
                    sell_hg_sl_trigger=new_settings['sell_hg_sl_trigger']
                )
                config.grid.last_auto_update = current_time
                
                # บันทึกลงไฟล์
                config.save_to_file()
                
                logger.info(f"✓ Auto settings updated: Grid={new_settings['buy_grid_distance']}pips, "
                           f"HG={new_settings['buy_hg_distance']}pips, Direction={new_settings['direction']}")
                
        except Exception as e:
            logger.error(f"Error updating auto settings: {e}")
    
    def check_and_restart_if_no_positions(self):
        """
        ตรวจสอบว่ามีไม้ Grid เหลืออยู่ในพอร์ตไหม
        ถ้าไม่มีเลย ให้วางไม้ใหม่ทันที (Auto Restart)
        """
        if not self.active:
            return
        
        # อัพเดท positions
        position_monitor.update_all_positions()
        
        # นับจำนวน Grid positions ที่เปิดอยู่
        grid_positions = position_monitor.grid_positions
        
        # ถ้าไม่มีไม้เลย และ grid_levels ว่างเปล่า
        if len(grid_positions) == 0 and len(self.grid_levels) == 0:
            logger.info("=" * 60)
            logger.info("⚠️ No Grid positions found - Auto Restarting...")
            logger.info("=" * 60)
            
            # ดึงราคาปัจจุบัน
            price_info = mt5_connection.get_current_price()
            if not price_info:
                logger.error("Cannot get current price for restart")
                return
            
            current_price = price_info['bid']
            
            # วางไม้ใหม่
            self.place_initial_orders(current_price)
            
            logger.info(f"✓ Grid Auto Restarted at {current_price:.2f}")
    
    def check_grid_distance_and_place_orders(self):
        """
        ตรวจสอบ Grid Distance และวางไม้ใหม่:
        - ใช้ข้อมูลจาก MT5 positions โดยตรง (ไม่พึ่ง grid_levels)
        - วางไม้ใหม่เมื่อราคาห่างจากไม้ล่าสุด >= Grid Distance
        - วางไม้ใหม่อัตโนมัติเมื่อฝั่งใดฝั่งหนึ่งหายไป (แก้ปัญหาไม้ฝั่งเดียวหมด)
        """
        if not self.active:
            return
        
        # ดึงราคาปัจจุบัน
        price_info = mt5_connection.get_current_price()
        if not price_info:
            return
        
        current_price = price_info['bid']
        
        # ใช้ระยะห่างแยก Buy/Sell
        buy_grid_distance_price = config.pips_to_price(config.grid.buy_grid_distance)
        sell_grid_distance_price = config.pips_to_price(config.grid.sell_grid_distance)
        
        # อัพเดท positions
        position_monitor.update_all_positions()
        grid_positions = position_monitor.grid_positions
        
        # หาไม้ Buy และ Sell ล่าสุดจาก MT5 positions
        latest_buy_price = None
        latest_sell_price = None
        has_buy_position = False
        has_sell_position = False
        
        for pos in grid_positions:
            if pos['type'] == 'buy' and (config.mt5.comment_grid in pos['comment'] or config.mt5.comment_auto in pos['comment']):
                has_buy_position = True
                if latest_buy_price is None or pos['open_price'] > latest_buy_price:
                    latest_buy_price = pos['open_price']
            
            if pos['type'] == 'sell' and (config.mt5.comment_grid in pos['comment'] or config.mt5.comment_auto in pos['comment']):
                has_sell_position = True
                if latest_sell_price is None or pos['open_price'] < latest_sell_price:
                    latest_sell_price = pos['open_price']
        
        # ตรวจสอบเงื่อนไขการวางไม้ Buy (ใช้ระยะห่าง Buy)
        if config.grid.direction in ['buy', 'both']:
            should_place_buy = False
            
            # เงื่อนไขพิเศษสำหรับโหมด 'both': ถ้าไม่มีไม้ Buy เลย → วางทันที (แก้ปัญหาไม้ฝั่งเดียวหมด)
            if config.grid.direction == 'both' and not has_buy_position:
                should_place_buy = True
                logger.info(f"🔄 [BOTH Mode] No BUY positions found - placing new BUY at {current_price:.2f}")
            
            # เงื่อนไขปกติ: ราคาลงห่างจาก latest_sell >= Sell Grid Distance
            elif latest_sell_price and current_price <= (latest_sell_price - sell_grid_distance_price):
                should_place_buy = True
                logger.info(f"Grid Distance triggered (ราคาลง): New BUY at {current_price:.2f}")
            
            # วางไม้ Buy ถ้าเข้าเงื่อนไขข้อใดข้อหนึ่ง
            if should_place_buy:
                # ตรวจสอบว่ามีไม้ Buy อยู่ใกล้ราคาปัจจุบันไหม (ป้องกันการวางซ้ำ)
                has_nearby_buy = False
                nearby_distance = buy_grid_distance_price * 0.5
                
                for pos in grid_positions:
                    if pos['type'] == 'buy' and abs(pos['open_price'] - current_price) < nearby_distance:
                        has_nearby_buy = True
                        break
                
                if not has_nearby_buy:
                    self.place_new_buy_order(current_price)
                else:
                    logger.info(f"⚠ Skipped BUY - nearby order exists at {current_price:.2f}")
        
        # ตรวจสอบเงื่อนไขการวางไม้ Sell (ใช้ระยะห่าง Sell)
        if config.grid.direction in ['sell', 'both']:
            should_place_sell = False
            
            # เงื่อนไขพิเศษสำหรับโหมด 'both': ถ้าไม่มีไม้ Sell เลย → วางทันที (แก้ปัญหาไม้ฝั่งเดียวหมด)
            if config.grid.direction == 'both' and not has_sell_position:
                should_place_sell = True
                logger.info(f"🔄 [BOTH Mode] No SELL positions found - placing new SELL at {current_price:.2f}")
            
            # เงื่อนไขปกติ: ราคาขึ้นห่างจาก latest_buy >= Buy Grid Distance
            elif latest_buy_price and current_price >= (latest_buy_price + buy_grid_distance_price):
                should_place_sell = True
                logger.info(f"Grid Distance triggered (ราคาขึ้น): New SELL at {current_price:.2f}")
            
            # วางไม้ Sell ถ้าเข้าเงื่อนไขข้อใดข้อหนึ่ง
            if should_place_sell:
                # ตรวจสอบว่ามีไม้ Sell อยู่ใกล้ราคาปัจจุบันไหม (ป้องกันการวางซ้ำ)
                has_nearby_sell = False
                nearby_distance = sell_grid_distance_price * 0.5
                
                for pos in grid_positions:
                    if pos['type'] == 'sell' and abs(pos['open_price'] - current_price) < nearby_distance:
                        has_nearby_sell = True
                        break
                
                if not has_nearby_sell:
                    self.place_new_sell_order(current_price)
                else:
                    logger.info(f"⚠ Skipped SELL - nearby order exists at {current_price:.2f}")
        
        # Recovery ไม้ที่ผิดทาง
        self.recovery_wrong_direction_orders(current_price)
    
    def recovery_wrong_direction_orders(self, current_price: float):
        """
        แก้ไม้ที่ผิดทางแบบเฉลี่ยราคา (Averaging)
        - จับแค่ไม้ล่าสุดของแต่ละฝั่ง (Buy/Sell)
        - ถ้าราคาห่างจากไม้ล่าสุด >= Grid Distance → ออกไม้เพิ่ม
        - ถ้าไม้ล่าสุด TP ปิดไป → ขยับมาจับไม้ถัดไป
        
        🆕 Auto Mode:
        - ถ้า direction = "both" → แก้ไม้ทั้ง Buy และ Sell (เหมือนเดิม)
        - ถ้า direction = "buy" → แก้ไม้เฉพาะ Buy (เมื่อราคาลง)
        - ถ้า direction = "sell" → แก้ไม้เฉพาะ Sell (เมื่อราคาขึ้น)
        """
        if not self.active:
            return
        
        # Manual Mode: เฉพาะโหมด both เท่านั้น
        # Auto Mode: ทำงานทุก direction
        if not config.grid.auto_mode and config.grid.direction != 'both':
            return
        
        # ใช้ระยะห่างแยก Buy/Sell
        buy_grid_distance_price = config.pips_to_price(config.grid.buy_grid_distance)
        sell_grid_distance_price = config.pips_to_price(config.grid.sell_grid_distance)
        
        # อัพเดท positions เพื่อดูกำไร/ขาดทุน
        position_monitor.update_all_positions()
        
        # ตรวจสอบ Grid positions ทั้งหมดจาก MT5
        grid_positions = position_monitor.grid_positions
        
        # กำหนด comment ที่ใช้ตาม mode
        grid_comment = config.mt5.comment_auto if config.grid.auto_mode else config.mt5.comment_grid
        
        # แก้ไม้ Buy (โหมด both หรือ Auto Mode direction = "buy")
        if config.grid.direction in ['buy', 'both']:
            # หาไม้ Buy ล่าสุด (ราคาต่ำสุด)
            latest_buy = None
            for pos in grid_positions:
                if pos['type'] == 'buy' and (config.mt5.comment_grid in pos['comment'] or config.mt5.comment_auto in pos['comment']):
                    if latest_buy is None or pos['open_price'] < latest_buy['open_price']:
                        latest_buy = pos
            
            # ตรวจสอบว่าควรออก Buy เพิ่มไหม (ใช้ระยะห่าง Buy)
            if latest_buy:
                distance_from_latest = config.price_to_pips(latest_buy['open_price'] - current_price)
                
                if distance_from_latest >= config.grid.buy_grid_distance:
                    # ตรวจสอบว่ามีไม้ Buy อยู่ใกล้ราคาปัจจุบันไหม (ป้องกันการวางซ้ำ)
                    nearby_distance = buy_grid_distance_price * 0.5
                    has_nearby_buy = False
                    
                    for pos in grid_positions:
                        if pos['type'] == 'buy' and abs(pos['open_price'] - current_price) < nearby_distance:
                            has_nearby_buy = True
                            break
                    
                    if not has_nearby_buy:
                        self.place_new_buy_order(current_price)
                        mode_tag = "AUTO" if config.grid.auto_mode else "BOTH"
                        logger.info(f"✓ [{mode_tag}] Recovery BUY: Latest buy {latest_buy['ticket']} at {latest_buy['open_price']:.2f}, current {current_price:.2f} ({distance_from_latest:.0f} pips) → Add BUY")
                    else:
                        logger.info(f"⚠ Skipped Recovery BUY - nearby order exists at {current_price:.2f}")
        
        # แก้ไม้ Sell (โหมด both หรือ Auto Mode direction = "sell")
        if config.grid.direction in ['sell', 'both']:
            # หาไม้ Sell ล่าสุด (ราคาสูงสุด)
            latest_sell = None
            for pos in grid_positions:
                if pos['type'] == 'sell' and (config.mt5.comment_grid in pos['comment'] or config.mt5.comment_auto in pos['comment']):
                    if latest_sell is None or pos['open_price'] > latest_sell['open_price']:
                        latest_sell = pos
            
            # ตรวจสอบว่าควรออก Sell เพิ่มไหม (ใช้ระยะห่าง Sell)
            if latest_sell:
                distance_from_latest = config.price_to_pips(current_price - latest_sell['open_price'])
                
                if distance_from_latest >= config.grid.sell_grid_distance:
                    # ตรวจสอบว่ามีไม้ Sell อยู่ใกล้ราคาปัจจุบันไหม (ป้องกันการวางซ้ำ)
                    nearby_distance = sell_grid_distance_price * 0.5
                    has_nearby_sell = False
                    
                    for pos in grid_positions:
                        if pos['type'] == 'sell' and abs(pos['open_price'] - current_price) < nearby_distance:
                            has_nearby_sell = True
                            break
                    
                    if not has_nearby_sell:
                        self.place_new_sell_order(current_price)
                        mode_tag = "AUTO" if config.grid.auto_mode else "BOTH"
                        logger.info(f"✓ [{mode_tag}] Recovery SELL: Latest sell {latest_sell['ticket']} at {latest_sell['open_price']:.2f}, current {current_price:.2f} ({distance_from_latest:.0f} pips) → Add SELL")
                    else:
                        logger.info(f"⚠ Skipped Recovery SELL - nearby order exists at {current_price:.2f}")
    
    def restore_existing_positions(self):
        """
        จดจำ Grid positions ที่มีอยู่แล้วใน MT5 (ผ่าน magic number)
        เพื่อให้สามารถเปิดโปรแกรมใหม่ได้โดยไม่สูญเสียข้อมูล
        """
        logger.info("Restoring existing Grid positions...")
        
        # อัพเดท positions
        position_monitor.update_all_positions()
        
        # ดึง Grid positions ที่มีอยู่
        grid_positions = position_monitor.grid_positions
        
        if not grid_positions:
            logger.info("No existing Grid positions found")
            return 0
        
        # จดจำ Grid positions ที่มีอยู่
        restored_count = 0
        for pos in grid_positions:
            # ตรวจสอบว่าเป็น Grid position หรือไม่ (จาก comment)
            comment = pos['comment']
            if config.mt5.comment_grid in comment or config.mt5.comment_auto in comment:
                # สร้าง level_key ใหม่โดยใช้ ticket number (เพราะ comment ไม่มี level_key แล้ว)
                level_key = f"{pos['type']}_{pos['ticket']}"
                
                # บันทึกลง placed_orders
                self.placed_orders[level_key] = pos['ticket']
                
                # เพิ่มลง grid_levels
                self.grid_levels.append({
                    'level_key': level_key,
                    'price': pos['open_price'],
                    'type': pos['type'],
                    'tp': pos['tp'],
                    'placed': True,
                    'ticket': pos['ticket']
                })
                
                restored_count += 1
                logger.info(f"Restored Grid: {level_key} | Ticket: {pos['ticket']} | Price: {pos['open_price']:.2f}")
        
        logger.info(f"✓ Restored {restored_count} Grid positions")
        return restored_count
    
    def start_grid_trading(self):
        """
        เริ่มต้นระบบ Grid Trading
        """
        price_info = mt5_connection.get_current_price()
        if not price_info:
            logger.error("Cannot get current price")
            return False
        
        self.start_price = price_info['bid']
        self.active = True
        
        # จดจำ Grid positions ที่มีอยู่แล้ว (ถ้ามี)
        restored_count = self.restore_existing_positions()
        
        # วางออเดอร์เริ่มต้น (Buy + Sell 1 ไม้) เฉพาะเมื่อไม่มีไม้อยู่เลย
        if restored_count == 0:
            logger.info("No existing positions found - placing initial orders")
            self.place_initial_orders(self.start_price)
        else:
            logger.info(f"Found {restored_count} existing positions - continuing from existing")
        
        logger.info(f"Grid Trading started at {self.start_price:.2f}")
        logger.info(f"Direction: {config.grid.direction}")
        logger.info(f"Buy:  Distance={config.grid.buy_grid_distance} pips, Lot={config.grid.buy_lot_size}, TP={config.grid.buy_take_profit} pips")
        logger.info(f"Sell: Distance={config.grid.sell_grid_distance} pips, Lot={config.grid.sell_lot_size}, TP={config.grid.sell_take_profit} pips")
        
        return True
    
    def stop_grid_trading(self, close_positions: bool = False):
        """
        หยุดระบบ Grid Trading
        
        Args:
            close_positions: True = ปิด positions ทั้งหมด
        """
        self.active = False
        
        if close_positions:
            closed = position_monitor.close_all_grid_positions()
            logger.info(f"Grid Trading stopped - Closed {closed} positions")
        else:
            logger.info("Grid Trading stopped - Positions remain open")
        
        # รีเซ็ต
        self.grid_levels = []
        self.placed_orders = {}
    
    def get_total_grid_exposure(self) -> Dict:
        """
        คำนวณ exposure รวมของ Grid
        
        Returns:
            Dict ที่มีข้อมูล exposure
        """
        position_monitor.update_all_positions()
        return position_monitor.get_net_grid_exposure()
    
    def get_grid_status(self) -> Dict:
        """
        ดึงสถานะ Grid ทั้งหมด
        
        Returns:
            Dict ที่มีข้อมูลสถานะ
        """
        active_levels = sum(1 for g in self.grid_levels if g['placed'])
        pending_levels = sum(1 for g in self.grid_levels if not g['placed'])
        
        return {
            'active': self.active,
            'start_price': self.start_price,
            'total_levels': len(self.grid_levels),
            'active_levels': active_levels,
            'pending_levels': pending_levels,
            'placed_orders': len(self.placed_orders)
        }


# สร้าง instance หลักสำหรับใช้งาน
grid_manager = GridManager()

