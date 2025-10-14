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
        self.start_price = 0.0
        
    def check_hg_trigger(self, current_price: float) -> List[Dict]:
        """
        ตรวจสอบว่าถึงเงื่อนไขวาง HG หรือยัง
        
        Args:
            current_price: ราคาปัจจุบัน
            
        Returns:
            List ของ HG ที่ควรวาง
        """
        triggers = []
        hg_distance_price = config.pips_to_price(config.hg.hg_distance)
        
        # ตรวจสอบแต่ละ level
        for i in range(1, 11):  # สูงสุด 10 levels
            # HG Buy (ด้านล่าง)
            level_price_buy = self.start_price - (hg_distance_price * i)
            level_key_buy = f"HG_BUY_{i}"
            
            if current_price <= level_price_buy and level_key_buy not in self.placed_hg:
                triggers.append({
                    'level_key': level_key_buy,
                    'price': level_price_buy,
                    'type': 'buy',
                    'level': -i
                })
            
            # HG Sell (ด้านบน)
            level_price_sell = self.start_price + (hg_distance_price * i)
            level_key_sell = f"HG_SELL_{i}"
            
            if current_price >= level_price_sell and level_key_sell not in self.placed_hg:
                triggers.append({
                    'level_key': level_key_sell,
                    'price': level_price_sell,
                    'type': 'sell',
                    'level': i
                })
        
        return triggers
    
    def calculate_hg_lot(self) -> float:
        """
        คำนวณ lot size สำหรับ HG
        HG Lot = Total Grid Exposure × multiplier
        
        Returns:
            lot size สำหรับ HG
        """
        # ดึงข้อมูล Grid exposure
        exposure = position_monitor.get_net_grid_exposure()
        net_volume = exposure['net_volume']
        
        # คำนวณ HG lot
        hg_lot = net_volume * config.hg.hg_multiplier
        
        # ถ้า Grid ยังไม่มี exposure ใช้ค่าเริ่มต้น
        if hg_lot < 0.01:
            hg_lot = 0.01
        
        # ปัดเศษตาม step
        hg_lot = round(hg_lot, 2)
        
        logger.info(f"HG Lot calculated: {hg_lot} (Grid exposure: {net_volume})")
        
        return hg_lot
    
    def place_hg_order(self, hg_info: Dict) -> Optional[int]:
        """
        วาง HG order
        
        Args:
            hg_info: ข้อมูล HG ที่ต้องวาง
            
        Returns:
            ticket number หรือ None
        """
        # คำนวณ lot size
        hg_lot = self.calculate_hg_lot()
        
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
        if not self.active:
            return
        
        # อัพเดท positions
        position_monitor.update_all_positions()
        
        for level_key, hg_data in self.placed_hg.items():
            # ตรวจสอบว่า position ยังเปิดอยู่หรือไม่
            pos = position_monitor.get_position_by_ticket(hg_data['ticket'])
            
            if pos is None:
                # Position ถูกปิดแล้ว
                logger.info(f"HG closed: {level_key}")
                continue
            
            # ตรวจสอบว่าตั้ง breakeven แล้วหรือยัง
            if hg_data['breakeven_set']:
                continue
            
            # คำนวณกำไรเป็น pips
            if hg_data['type'] == 'buy':
                pips_profit = config.price_to_pips(pos['current_price'] - pos['open_price'])
            else:  # sell
                pips_profit = config.price_to_pips(pos['open_price'] - pos['current_price'])
            
            # ตรวจสอบว่าถึง trigger breakeven หรือยัง
            if pips_profit >= config.hg.hg_sl_trigger:
                self.set_hg_breakeven_sl(hg_data, pos)
    
    def set_hg_breakeven_sl(self, hg_data: Dict, position: Dict):
        """
        ตั้ง Stop Loss แบบ breakeven สำหรับ HG
        
        Args:
            hg_data: ข้อมูล HG
            position: ข้อมูล position จาก MT5
        """
        # คำนวณราคา breakeven (เพิ่ม buffer)
        buffer_price = config.pips_to_price(config.hg.sl_buffer)
        
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
            logger.info(f"Buffer: {config.hg.sl_buffer} pips")
    
    def manage_multiple_hg(self):
        """
        จัดการ HG หลายระดับ
        - ตรวจสอบและวาง HG ใหม่เมื่อถึง trigger
        - ติดตาม breakeven ของ HG ที่เปิดอยู่
        """
        if not self.active:
            return
        
        # ดึงราคาปัจจุบัน
        price_info = mt5_connection.get_current_price()
        if not price_info:
            return
        
        current_price = price_info['bid']
        
        # ตรวจสอบว่ามี HG ที่ต้องวางหรือไม่
        triggers = self.check_hg_trigger(current_price)
        
        for trigger in triggers:
            self.place_hg_order(trigger)
        
        # ติดตามกำไรและตั้ง breakeven
        self.monitor_hg_profit()
    
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
            return
        
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
        self.restore_existing_hg_positions()
        
        logger.info(f"HG System started at {self.start_price:.2f}")
        logger.info(f"HG Distance: {config.hg.hg_distance} pips")
        logger.info(f"HG SL Trigger: {config.hg.hg_sl_trigger} pips")
        logger.info(f"HG Multiplier: {config.hg.hg_multiplier}x")
    
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

