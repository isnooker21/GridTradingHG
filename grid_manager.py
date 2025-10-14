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
    
    def place_grid_orders(self, current_price: float):
        """
        วาง Grid orders ตามระดับที่คำนวณไว้
        
        Args:
            current_price: ราคาปัจจุบัน
        """
        if not self.active:
            return
        
        # คำนวณ levels
        levels = self.calculate_grid_levels(current_price, num_levels=5)
        
        for level in levels:
            # ตรวจสอบว่ามี order ที่ระดับนี้อยู่แล้วหรือไม่
            level_key = f"{level['type']}_{level['level']}"
            if level_key in self.placed_orders:
                continue
            
            # คำนวณ TP
            tp_distance = config.pips_to_price(config.grid.take_profit)
            if level['type'] == 'buy':
                tp_price = level['price'] + tp_distance
            else:
                tp_price = level['price'] - tp_distance
            
            # วาง order (ใช้ limit order)
            # หมายเหตุ: ในกรณีนี้เราจะใช้ market order เมื่อราคาถึง
            # สำหรับ limit order ต้องใช้ ORDER_TYPE_BUY_LIMIT / ORDER_TYPE_SELL_LIMIT
            # แต่เพื่อความง่ายเราจะวาง market order เมื่อราคาถึงระดับ
            
            self.grid_levels.append({
                'level_key': level_key,
                'price': level['price'],
                'type': level['type'],
                'tp': tp_price,
                'placed': False
            })
    
    def monitor_grid_levels(self):
        """
        ตรวจสอบว่าราคาถึง Grid levels หรือยัง และวาง order
        """
        if not self.active:
            return
        
        price_info = mt5_connection.get_current_price()
        if not price_info:
            return
        
        current_price = price_info['bid']
        
        for grid in self.grid_levels:
            if grid['placed']:
                continue
            
            # ตรวจสอบว่าราคาถึงระดับนี้หรือยัง
            should_place = False
            
            if grid['type'] == 'buy' and current_price <= grid['price']:
                should_place = True
            elif grid['type'] == 'sell' and current_price >= grid['price']:
                should_place = True
            
            if should_place:
                # วาง market order
                comment = f"{config.mt5.comment_grid}_{grid['level_key']}"
                ticket = mt5_connection.place_order(
                    order_type=grid['type'],
                    volume=config.grid.lot_size,
                    tp=grid['tp'],
                    comment=comment
                )
                
                if ticket:
                    grid['placed'] = True
                    grid['ticket'] = ticket
                    self.placed_orders[grid['level_key']] = ticket
                    logger.info(f"Grid order placed at {grid['price']:.2f} | {grid['type'].upper()}")
    
    def monitor_grid_tp(self):
        """
        ตรวจสอบและปิด positions ที่ถึง TP
        (MT5 จะปิด automatically ถ้าตั้ง TP ไว้)
        แต่เราจะอัพเดทสถานะ Grid
        """
        if not self.active:
            return
        
        # อัพเดท positions
        position_monitor.update_all_positions()
        
        # ตรวจสอบ Grid levels ที่ถูกปิดแล้ว
        for grid in self.grid_levels:
            if not grid['placed']:
                continue
            
            if 'ticket' not in grid:
                continue
            
            # ตรวจสอบว่า position ยังเปิดอยู่หรือไม่
            pos = position_monitor.get_position_by_ticket(grid['ticket'])
            
            if pos is None:
                # Position ถูกปิดแล้ว (ถึง TP หรือถูกปิดด้วยวิธีอื่น)
                logger.info(f"Grid closed: {grid['level_key']} at {grid['price']:.2f}")
                
                # รีเซ็ต Grid level นี้เพื่อวางใหม่
                grid['placed'] = False
                if grid['level_key'] in self.placed_orders:
                    del self.placed_orders[grid['level_key']]
    
    def update_grid_status(self):
        """
        อัพเดทสถานะ Grid ทั้งหมด
        """
        if not self.active:
            return
        
        # ตรวจสอบระดับที่ต้องวาง order
        self.monitor_grid_levels()
        
        # ตรวจสอบ TP
        self.monitor_grid_tp()
    
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
        
        # วาง Grid levels เริ่มต้น
        self.place_grid_orders(self.start_price)
        
        logger.info(f"Grid Trading started at {self.start_price:.2f}")
        logger.info(f"Direction: {config.grid.direction}, Distance: {config.grid.grid_distance} pips")
        logger.info(f"Lot Size: {config.grid.lot_size}, TP: {config.grid.take_profit} pips")
        
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

