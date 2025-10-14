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
        
    def calculate_grid_levels(self, current_price: float, num_levels: int = 10) -> List[float]:
        """
        คำนวณตำแหน่ง Grid levels
        
        Args:
            current_price: ราคาปัจจุบัน
            num_levels: จำนวน levels ที่ต้องการคำนวณ (แต่ละด้าน)
            
        Returns:
            List ของราคา Grid levels
        """
        levels = []
        grid_distance_price = config.pips_to_price(config.grid.grid_distance)
        
        if config.grid.direction in ['buy', 'both']:
            # คำนวณ levels ด้านล่าง (Buy)
            for i in range(1, num_levels + 1):
                level_price = current_price - (grid_distance_price * i)
                levels.append({
                    'price': level_price,
                    'type': 'buy',
                    'level': -i
                })
        
        if config.grid.direction in ['sell', 'both']:
            # คำนวณ levels ด้านบน (Sell)
            for i in range(1, num_levels + 1):
                level_price = current_price + (grid_distance_price * i)
                levels.append({
                    'price': level_price,
                    'type': 'sell',
                    'level': i
                })
        
        return levels
    
    def place_initial_orders(self, current_price: float):
        """
        วางออเดอร์เริ่มต้น: Buy 1 ไม้ + Sell 1 ไม้ ที่ราคาปัจจุบัน
        
        Args:
            current_price: ราคาปัจจุบัน
        """
        if not self.active:
            return
        
        logger.info("Placing initial orders...")
        
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
                
                # วาง Grid ใหม่
                self.place_new_grid_when_price_moves()
    
    def place_new_grid_when_price_moves(self):
        """
        วาง Grid ใหม่เมื่อราคาเคลื่อนไหวตามระยะที่ตั้งไว้
        """
        if not self.active:
            return
        
        # ดึงราคาปัจจุบัน
        price_info = mt5_connection.get_current_price()
        if not price_info:
            return
        
        current_price = price_info['bid']
        grid_distance_price = config.pips_to_price(config.grid.grid_distance)
        
        # ตรวจสอบว่าต้องวาง Buy ใหม่หรือไม่
        if config.grid.direction in ['buy', 'both']:
            # หา Buy position ที่ต่ำสุด
            lowest_buy_price = None
            for grid in self.grid_levels:
                if grid['type'] == 'buy' and grid['placed']:
                    if lowest_buy_price is None or grid['price'] < lowest_buy_price:
                        lowest_buy_price = grid['price']
            
            # ถ้าราคาลงมากกว่า Grid Distance จาก Buy ต่ำสุด
            if lowest_buy_price and current_price <= (lowest_buy_price - grid_distance_price):
                self.place_new_buy_order(current_price)
        
        # ตรวจสอบว่าต้องวาง Sell ใหม่หรือไม่
        if config.grid.direction in ['sell', 'both']:
            # หา Sell position ที่สูงสุด
            highest_sell_price = None
            for grid in self.grid_levels:
                if grid['type'] == 'sell' and grid['placed']:
                    if highest_sell_price is None or grid['price'] > highest_sell_price:
                        highest_sell_price = grid['price']
            
            # ถ้าราคาขึ้นมากกว่า Grid Distance จาก Sell สูงสุด
            if highest_sell_price and current_price >= (highest_sell_price + grid_distance_price):
                self.place_new_sell_order(current_price)
    
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
                # แยก level_key จาก comment (format: "GridBot_buy_-1")
                parts = comment.split('_')
                if len(parts) >= 3:
                    order_type = parts[1]  # buy หรือ sell
                    level = parts[2]  # -1, -2, 1, 2, etc.
                    level_key = f"{order_type}_{level}"
                    
                    # บันทึกลง placed_orders
                    self.placed_orders[level_key] = pos['ticket']
                    
                    # เพิ่มลง grid_levels
                    self.grid_levels.append({
                        'level_key': level_key,
                        'price': pos['open_price'],
                        'type': order_type,
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
        self.restore_existing_positions()
        
        # วางออเดอร์เริ่มต้น (Buy + Sell 1 ไม้)
        self.place_initial_orders(self.start_price)
        
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

