# grid_manager.py
# ไฟล์จัดการระบบ Grid Trading

from typing import List, Dict, Optional
import logging
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
        
        # คำนวณ TP (ใช้ระยะเท่ากับ Grid Distance)
        tp_distance = config.pips_to_price(config.grid.grid_distance)
        buy_tp = current_price + tp_distance
        sell_tp = current_price - tp_distance
        
        orders_placed = 0
        
        # วาง Buy order
        if config.grid.direction in ['buy', 'both']:
            comment = f"{config.mt5.comment_grid}_initial_buy"
            ticket = mt5_connection.place_order(
                order_type='buy',
                volume=config.grid.lot_size,
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
                logger.info(f"Initial BUY placed: {config.grid.lot_size} lots at {current_price:.2f} | TP: {buy_tp:.2f} | Ticket: {ticket}")
        
        # วาง Sell order
        if config.grid.direction in ['sell', 'both']:
            comment = f"{config.mt5.comment_grid}_initial_sell"
            ticket = mt5_connection.place_order(
                order_type='sell',
                volume=config.grid.lot_size,
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
                logger.info(f"Initial SELL placed: {config.grid.lot_size} lots at {current_price:.2f} | TP: {sell_tp:.2f} | Ticket: {ticket}")
        
        logger.info(f"✓ Initial orders placed: {orders_placed} orders")
    
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
    
    def place_new_buy_order(self, current_price: float):
        """
        วาง Buy order ใหม่
        """
        tp_distance = config.pips_to_price(config.grid.grid_distance)
        tp_price = current_price + tp_distance
        
        # สร้าง level_key ที่ไม่ซ้ำ
        buy_count = sum(1 for grid in self.grid_levels if grid['type'] == 'buy')
        level_key = f"buy_{buy_count}"
        
        comment = f"{config.mt5.comment_grid}_{level_key}"
        ticket = mt5_connection.place_order(
            order_type='buy',
            volume=config.grid.lot_size,
            tp=tp_price,
            comment=comment
        )
        
        if ticket:
            self.placed_orders[level_key] = ticket
            self.grid_levels.append({
                'level_key': level_key,
                'price': current_price,
                'type': 'buy',
                'tp': tp_price,
                'placed': True,
                'ticket': ticket
            })
            
            logger.info(f"New BUY placed: {config.grid.lot_size} lots at {current_price:.2f} | TP: {tp_price:.2f} | Ticket: {ticket}")
    
    def place_new_sell_order(self, current_price: float):
        """
        วาง Sell order ใหม่
        """
        tp_distance = config.pips_to_price(config.grid.grid_distance)
        tp_price = current_price - tp_distance
        
        # สร้าง level_key ที่ไม่ซ้ำ
        sell_count = sum(1 for grid in self.grid_levels if grid['type'] == 'sell')
        level_key = f"sell_{sell_count}"
        
        comment = f"{config.mt5.comment_grid}_{level_key}"
        ticket = mt5_connection.place_order(
            order_type='sell',
            volume=config.grid.lot_size,
            tp=tp_price,
            comment=comment
        )
        
        if ticket:
            self.placed_orders[level_key] = ticket
            self.grid_levels.append({
                'level_key': level_key,
                'price': current_price,
                'type': 'sell',
                'tp': tp_price,
                'placed': True,
                'ticket': ticket
            })
            
            logger.info(f"New SELL placed: {config.grid.lot_size} lots at {current_price:.2f} | TP: {tp_price:.2f} | Ticket: {ticket}")
    
    
    def update_grid_status(self):
        """
        อัพเดทสถานะ Grid ทั้งหมด
        """
        if not self.active:
            return
        
        # ติดตาม Grid positions
        self.monitor_grid_positions()
        
        # ตรวจสอบว่ามีไม้เหลืออยู่ไหม ถ้าไม่มีให้วางใหม่
        self.check_and_restart_if_no_positions()
        
        # ตรวจสอบ Grid Distance และวางไม้ใหม่
        self.check_grid_distance_and_place_orders()
    
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
        """
        if not self.active:
            return
        
        # ดึงราคาปัจจุบัน
        price_info = mt5_connection.get_current_price()
        if not price_info:
            return
        
        current_price = price_info['bid']
        grid_distance_price = config.pips_to_price(config.grid.grid_distance)
        
        # อัพเดท positions
        position_monitor.update_all_positions()
        grid_positions = position_monitor.grid_positions
        
        # หาไม้ Buy และ Sell ล่าสุดจาก MT5 positions
        latest_buy_price = None
        latest_sell_price = None
        
        for pos in grid_positions:
            if pos['type'] == 'buy' and config.mt5.comment_grid in pos['comment']:
                if latest_buy_price is None or pos['open_price'] > latest_buy_price:
                    latest_buy_price = pos['open_price']
            
            if pos['type'] == 'sell' and config.mt5.comment_grid in pos['comment']:
                if latest_sell_price is None or pos['open_price'] < latest_sell_price:
                    latest_sell_price = pos['open_price']
        
        # ตรวจสอบเงื่อนไขการวางไม้ Buy (ราคาลง)
        if config.grid.direction in ['buy', 'both']:
            if latest_sell_price and current_price <= (latest_sell_price - grid_distance_price):
                # ตรวจสอบว่ามีไม้ Buy อยู่ใกล้ราคาปัจจุบันไหม
                has_nearby_buy = False
                nearby_distance = grid_distance_price * 0.5
                
                for pos in grid_positions:
                    if pos['type'] == 'buy' and abs(pos['open_price'] - current_price) < nearby_distance:
                        has_nearby_buy = True
                        break
                
                if not has_nearby_buy:
                    self.place_new_buy_order(current_price)
                    logger.info(f"Grid Distance triggered (ราคาลง): New BUY placed at {current_price:.2f}")
                else:
                    logger.info(f"⚠ Skipped Grid BUY - nearby order exists at {current_price:.2f}")
        
        # ตรวจสอบเงื่อนไขการวางไม้ Sell (ราคาขึ้น)
        if config.grid.direction in ['sell', 'both']:
            if latest_buy_price and current_price >= (latest_buy_price + grid_distance_price):
                # ตรวจสอบว่ามีไม้ Sell อยู่ใกล้ราคาปัจจุบันไหม
                has_nearby_sell = False
                nearby_distance = grid_distance_price * 0.5
                
                for pos in grid_positions:
                    if pos['type'] == 'sell' and abs(pos['open_price'] - current_price) < nearby_distance:
                        has_nearby_sell = True
                        break
                
                if not has_nearby_sell:
                    self.place_new_sell_order(current_price)
                    logger.info(f"Grid Distance triggered (ราคาขึ้น): New SELL placed at {current_price:.2f}")
                else:
                    logger.info(f"⚠ Skipped Grid SELL - nearby order exists at {current_price:.2f}")
        
        # Recovery ไม้ที่ผิดทาง
        self.recovery_wrong_direction_orders(current_price)
    
    def recovery_wrong_direction_orders(self, current_price: float):
        """
        แก้ไม้ที่ผิดทางแบบเฉลี่ยราคา (Averaging)
        - จับแค่ไม้ล่าสุดของแต่ละฝั่ง (Buy/Sell)
        - ถ้าราคาห่างจากไม้ล่าสุด >= Grid Distance → ออกไม้เพิ่ม
        - ถ้าไม้ล่าสุด TP ปิดไป → ขยับมาจับไม้ถัดไป
        - เคารพโหมด Buy/Sell/Both ที่ตั้งไว้
        """
        if not self.active:
            return
        
        grid_distance_price = config.pips_to_price(config.grid.grid_distance)
        
        # อัพเดท positions เพื่อดูกำไร/ขาดทุน
        position_monitor.update_all_positions()
        
        # ตรวจสอบ Grid positions ทั้งหมดจาก MT5
        grid_positions = position_monitor.grid_positions
        
        # แก้ไม้ Buy (เฉพาะเมื่อโหมดเป็น 'buy' หรือ 'both')
        if config.grid.direction in ['buy', 'both']:
            # หาไม้ Buy ล่าสุด (ราคาต่ำสุด)
            latest_buy = None
            for pos in grid_positions:
                if pos['type'] == 'buy' and config.mt5.comment_grid in pos['comment']:
                    if latest_buy is None or pos['open_price'] < latest_buy['open_price']:
                        latest_buy = pos
            
            # ตรวจสอบว่าควรออก Buy เพิ่มไหม
            if latest_buy:
                distance_from_latest = config.price_to_pips(latest_buy['open_price'] - current_price)
                
                if distance_from_latest >= config.grid.grid_distance:
                    # ตรวจสอบว่ามีไม้ Buy อยู่ใกล้ราคาปัจจุบันไหม (ป้องกันการวางซ้ำ)
                    nearby_distance = grid_distance_price * 0.5
                    has_nearby_buy = False
                    
                    for pos in grid_positions:
                        if pos['type'] == 'buy' and abs(pos['open_price'] - current_price) < nearby_distance:
                            has_nearby_buy = True
                            break
                    
                    if not has_nearby_buy:
                        self.place_new_buy_order(current_price)
                        logger.info(f"✓ Recovery BUY: Latest buy {latest_buy['ticket']} at {latest_buy['open_price']:.2f}, current {current_price:.2f} ({distance_from_latest:.0f} pips) → Add BUY")
                    else:
                        logger.info(f"⚠ Skipped Recovery BUY - nearby order exists at {current_price:.2f}")
        
        # แก้ไม้ Sell (เฉพาะเมื่อโหมดเป็น 'sell' หรือ 'both')
        if config.grid.direction in ['sell', 'both']:
            # หาไม้ Sell ล่าสุด (ราคาสูงสุด)
            latest_sell = None
            for pos in grid_positions:
                if pos['type'] == 'sell' and config.mt5.comment_grid in pos['comment']:
                    if latest_sell is None or pos['open_price'] > latest_sell['open_price']:
                        latest_sell = pos
            
            # ตรวจสอบว่าควรออก Sell เพิ่มไหม
            if latest_sell:
                distance_from_latest = config.price_to_pips(current_price - latest_sell['open_price'])
                
                if distance_from_latest >= config.grid.grid_distance:
                    # ตรวจสอบว่ามีไม้ Sell อยู่ใกล้ราคาปัจจุบันไหม (ป้องกันการวางซ้ำ)
                    nearby_distance = grid_distance_price * 0.5
                    has_nearby_sell = False
                    
                    for pos in grid_positions:
                        if pos['type'] == 'sell' and abs(pos['open_price'] - current_price) < nearby_distance:
                            has_nearby_sell = True
                            break
                    
                    if not has_nearby_sell:
                        self.place_new_sell_order(current_price)
                        logger.info(f"✓ Recovery SELL: Latest sell {latest_sell['ticket']} at {latest_sell['open_price']:.2f}, current {current_price:.2f} ({distance_from_latest:.0f} pips) → Add SELL")
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
            return
        
        # จดจำ Grid positions ที่มีอยู่
        restored_count = 0
        for pos in grid_positions:
            # ดึง level_key จาก comment
            comment = pos['comment']
            if config.mt5.comment_grid in comment:
                # แยก level_key จาก comment (format: "GridBot_initial_buy", "GridBot_buy_0", etc.)
                parts = comment.split('_')
                if len(parts) >= 3:
                    # ดึง level_key ที่เหลือหลังจาก comment_grid
                    level_key = '_'.join(parts[1:])  # เอาตั้งแต่ส่วนที่ 2 เป็นต้นไป
                    
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
        logger.info(f"Direction: {config.grid.direction}, Distance: {config.grid.grid_distance} pips")
        logger.info(f"Lot Size: {config.grid.lot_size}, TP: {config.grid.grid_distance} pips (same as grid distance)")
        
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

