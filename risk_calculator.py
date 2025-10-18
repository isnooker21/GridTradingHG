# risk_calculator.py
# ไฟล์คำนวณความเสี่ยงและทนได้กี่ pips

import logging
from typing import Dict
from config import config
from mt5_connection import mt5_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RiskCalculator:
    """คลาสคำนวณความเสี่ยงและจุดทนทาน"""
    
    def __init__(self):
        self.contract_size = 100  # XAUUSD: 100 oz
        self.pip_value = 0.10  # XAUUSD 0.01 lot = $0.10 per pip
    
    def calculate_margin_per_lot(self, price: float, lot: float, leverage: int = 100) -> float:
        """
        คำนวณ Margin ที่ต้องใช้ต่อ lot
        
        Args:
            price: ราคาปัจจุบัน
            lot: ขนาด lot
            leverage: Leverage ที่ใช้
            
        Returns:
            Margin ที่ต้องใช้ ($)
        """
        return (lot * self.contract_size * price) / leverage
    
    def calculate_pip_value_for_lot(self, lot: float) -> float:
        """
        คำนวณมูลค่าต่อ pip สำหรับ lot ที่กำหนด
        
        Args:
            lot: ขนาด lot
            
        Returns:
            มูลค่าต่อ pip ($)
        """
        # XAUUSD: 0.01 lot = $0.10 per pip
        return lot * 10.0
    
    def simulate_grid_only(self, balance: float, price: float, leverage: int = 100) -> Dict:
        """
        Simulate ระบบ Grid อย่างเดียว (ไม่มี HG)
        
        Args:
            balance: ยอดเงินในบัญชี
            price: ราคาปัจจุบัน
            leverage: Leverage
            
        Returns:
            Dict ของผลลัพธ์
        """
        lot_size = config.grid.lot_size
        grid_distance = config.grid.grid_distance
        direction = config.grid.direction
        
        margin_per_position = self.calculate_margin_per_lot(price, lot_size, leverage)
        pip_value = self.calculate_pip_value_for_lot(lot_size)
        
        # Simulate ราคาเคลื่อนไหว
        positions = []
        current_distance = 0
        total_margin = 0
        total_drawdown = 0
        
        # Safe limit: Margin Level > 150% (ปลอดภัย)
        safe_margin_level = 1.5
        
        while True:
            current_distance += grid_distance
            
            # เพิ่มไม้ใหม่ตามทิศทาง
            if direction == "both":
                # ออกทั้ง Buy และ Sell ต้องคิด Worst Case
                # สมมติว่าราคาเดินทางเดียว (ไม้ฝั่งหนึ่งจะ TP, อีกฝั่งจะสะสม)
                positions.append({
                    'distance': current_distance,
                    'lot': lot_size,
                    'type': 'average'
                })
            else:
                # ออกฝั่งเดียว
                positions.append({
                    'distance': current_distance,
                    'lot': lot_size,
                    'type': direction
                })
            
            # คำนวณ Margin
            total_margin = len(positions) * margin_per_position
            
            # คำนวณ Drawdown (Worst Case: ราคาเดินทางเดียว)
            total_drawdown = 0
            for i, pos in enumerate(positions):
                distance_from_open = current_distance - pos['distance']
                drawdown = distance_from_open * pip_value
                total_drawdown += drawdown
            
            # คำนวณ Equity และ Margin Level
            equity = balance - total_drawdown
            
            if total_margin > 0:
                margin_level = equity / total_margin
            else:
                margin_level = 999
            
            # เช็คว่าถึงขีดจำกัดหรือยัง
            if margin_level < safe_margin_level or equity < total_margin:
                # ถึงจุดอันตราย
                return {
                    'max_distance_pips': current_distance - grid_distance,  # ถอยกลับ 1 level
                    'max_levels': len(positions) - 1,
                    'max_margin': total_margin - margin_per_position,
                    'max_drawdown': total_drawdown - (grid_distance * pip_value),
                    'final_margin_level': margin_level,
                    'final_equity': equity,
                    'status': 'AT_LIMIT'
                }
            
            # ป้องกัน infinite loop (ถ้าคำนวณเกิน 10,000 pips หยุด)
            if current_distance > 10000:
                return {
                    'max_distance_pips': 10000,
                    'max_levels': len(positions),
                    'max_margin': total_margin,
                    'max_drawdown': total_drawdown,
                    'final_margin_level': margin_level,
                    'final_equity': equity,
                    'status': 'SAFE'
                }
    
    def simulate_grid_with_hg(self, balance: float, price: float, leverage: int = 100) -> Dict:
        """
        Simulate ระบบ Grid + HG
        
        Args:
            balance: ยอดเงินในบัญชี
            price: ราคาปัจจุบัน
            leverage: Leverage
            
        Returns:
            Dict ของผลลัพธ์
        """
        lot_size = config.grid.lot_size
        grid_distance = config.grid.grid_distance
        hg_distance = config.hg.hg_distance
        hg_multiplier = config.hg.hg_multiplier
        max_hg_levels = config.hg.max_hg_levels
        direction = config.grid.direction
        
        margin_per_grid = self.calculate_margin_per_lot(price, lot_size, leverage)
        pip_value_grid = self.calculate_pip_value_for_lot(lot_size)
        
        # Simulate
        grid_positions = []
        hg_positions = []
        current_distance = 0
        total_margin = 0
        total_drawdown = 0
        hg_count = 0
        
        safe_margin_level = 1.5
        
        while True:
            current_distance += grid_distance
            
            # เพิ่มไม้ Grid
            grid_positions.append({
                'distance': current_distance,
                'lot': lot_size
            })
            
            # ตรวจสอบว่าถึง HG trigger หรือยัง
            if current_distance % hg_distance == 0 and hg_count < max_hg_levels:
                # คำนวณ Net Exposure
                net_exposure = len(grid_positions) * lot_size
                
                # คำนวณ HG lot
                hg_lot = net_exposure * hg_multiplier
                
                hg_positions.append({
                    'distance': current_distance,
                    'lot': hg_lot,
                    'trigger_distance': current_distance
                })
                
                hg_count += 1
            
            # คำนวณ Margin รวม
            grid_margin = len(grid_positions) * margin_per_grid
            
            hg_margin = 0
            for hg in hg_positions:
                hg_margin += self.calculate_margin_per_lot(price, hg['lot'], leverage)
            
            total_margin = grid_margin + hg_margin
            
            # คำนวณ Drawdown
            grid_drawdown = 0
            for i, pos in enumerate(grid_positions):
                distance_from_open = current_distance - pos['distance']
                drawdown = distance_from_open * pip_value_grid
                grid_drawdown += drawdown
            
            hg_drawdown = 0
            for hg in hg_positions:
                distance_from_open = current_distance - hg['trigger_distance']
                pip_value_hg = self.calculate_pip_value_for_lot(hg['lot'])
                drawdown = distance_from_open * pip_value_hg
                hg_drawdown += drawdown
            
            total_drawdown = grid_drawdown + hg_drawdown
            
            # คำนวณ Equity และ Margin Level
            equity = balance - total_drawdown
            
            if total_margin > 0:
                margin_level = equity / total_margin
            else:
                margin_level = 999
            
            # เช็คขีดจำกัด
            if margin_level < safe_margin_level or equity < total_margin:
                return {
                    'max_distance_pips': current_distance - grid_distance,
                    'max_grid_levels': len(grid_positions) - 1,
                    'max_hg_levels': len(hg_positions),
                    'max_margin': total_margin - margin_per_grid,
                    'max_drawdown': total_drawdown,
                    'grid_drawdown': grid_drawdown,
                    'hg_drawdown': hg_drawdown,
                    'final_margin_level': margin_level,
                    'final_equity': equity,
                    'status': 'AT_LIMIT'
                }
            
            # ป้องกัน infinite loop
            if current_distance > 10000:
                return {
                    'max_distance_pips': 10000,
                    'max_grid_levels': len(grid_positions),
                    'max_hg_levels': len(hg_positions),
                    'max_margin': total_margin,
                    'max_drawdown': total_drawdown,
                    'grid_drawdown': grid_drawdown,
                    'hg_drawdown': hg_drawdown,
                    'final_margin_level': margin_level,
                    'final_equity': equity,
                    'status': 'SAFE'
                }
    
    def calculate_risk(self, balance: float = None, price: float = None, leverage: int = 100) -> Dict:
        """
        คำนวณความเสี่ยงทั้งหมด
        
        Args:
            balance: ยอดเงิน (ถ้าไม่ระบุจะดึงจาก MT5)
            price: ราคาปัจจุบัน (ถ้าไม่ระบุจะดึงจาก MT5)
            leverage: Leverage
            
        Returns:
            Dict ของผลลัพธ์
        """
        # ถ้าไม่ระบุ balance หรือ price ให้ดึงจาก MT5
        if balance is None or price is None:
            account_info = mt5_connection.get_account_info()
            price_info = mt5_connection.get_current_price()
            
            if not account_info or not price_info:
                return {
                    'error': 'Cannot get MT5 data',
                    'message': 'Please connect to MT5 first'
                }
            
            if balance is None:
                balance = account_info.get('balance', 10000)
            if price is None:
                price = price_info.get('bid', 2600)
            
            # ดึง leverage จาก MT5
            leverage = account_info.get('leverage', 100)
        
        # คำนวณทั้ง 2 กรณี
        result_grid_only = self.simulate_grid_only(balance, price, leverage)
        
        if config.hg.enabled:
            result_with_hg = self.simulate_grid_with_hg(balance, price, leverage)
        else:
            result_with_hg = None
        
        return {
            'balance': balance,
            'price': price,
            'leverage': leverage,
            'grid_only': result_grid_only,
            'with_hg': result_with_hg,
            'hg_enabled': config.hg.enabled
        }


# สร้าง instance หลักสำหรับใช้งาน
risk_calculator = RiskCalculator()

