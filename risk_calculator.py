# risk_calculator.py
# ไฟล์คำนวณความเสี่ยงและทนได้กี่ pips (รองรับ Buy/Sell แยกกัน)

import logging
from typing import Dict
from config import config
from mt5_connection import mt5_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RiskCalculator:
    """คลาสคำนวณความเสี่ยงและจุดทนทาน (รองรับ Buy/Sell แยกกัน)"""
    
    def __init__(self):
        self.contract_size = 100  # XAUUSD: 100 oz
        self.pip_value_per_lot = 10.0  # 1 lot = $10 per pip, 0.01 lot = $0.10 per pip
    
    def calculate_margin_per_lot(self, price: float, lot: float, leverage: int = 100) -> float:
        """คำนวณ Margin ที่ต้องใช้ต่อ lot"""
        return (lot * self.contract_size * price) / leverage
    
    def calculate_pip_value_for_lot(self, lot: float) -> float:
        """
        คำนวณมูลค่าต่อ pip สำหรับ lot ที่กำหนด
        สำหรับ XAUUSD: 0.01 lot = $0.10 per pip
        """
        return lot * self.pip_value_per_lot
    
    def calculate_drawdown_for_position(self, position_distance: int, current_distance: int, 
                                       pip_value: float, position_type: str) -> float:
        """
        คำนวณ drawdown สำหรับ position เดียว (worst case scenario)
        
        สำหรับ worst case: ราคาลงไปเรื่อยๆ (สำหรับ Buy positions)
        
        Args:
            position_distance: ระยะห่างจากราคาเริ่มต้นที่เปิด position (pips)
                               เช่น ถ้าเปิดที่ 50 pips จากราคาเริ่มต้น = 50
            current_distance: ระยะห่างปัจจุบันจากราคาเริ่มต้น (pips)
                             เช่น ถ้าราคาลง 500 pips จากราคาเริ่มต้น = 500
            pip_value: มูลค่าต่อ pip ของ position นี้ ($0.10 สำหรับ 0.01 lot)
            position_type: 'buy' หรือ 'sell'
        
        Returns:
            drawdown ในหน่วยดอลลาร์
        """
        if position_type == 'buy':
            # Buy position: drawdown เมื่อราคาลง (current_distance > position_distance)
            # ตัวอย่าง: position_distance = 50, current_distance = 500
            #          drawdown = (500 - 50) × $0.10 = $45
            if current_distance > position_distance:
                drawdown_pips = current_distance - position_distance
                return drawdown_pips * pip_value
            else:
                # ราคายังไม่ถึงหรือผ่านราคาเปิด position (ไม่มี drawdown)
                return 0.0
        else:  # sell
            # Sell position: ใน worst case (ราคาลงไปเรื่อยๆ) sell position จะมีกำไร
            # เพราะ sell position เปิดที่ราคาสูงกว่า และราคาลง
            # ดังนั้นไม่นับ drawdown สำหรับ sell ใน worst case scenario (ราคาลง)
            return 0.0
    
    def simulate_grid_only(self, balance: float, price: float, leverage: int = 100) -> Dict:
        """Simulate ระบบ Grid อย่างเดียว (รองรับ Buy/Sell แยกกัน)"""
        
        direction = config.grid.direction
        buy_lot = config.grid.buy_lot_size
        sell_lot = config.grid.sell_lot_size
        buy_distance = config.grid.buy_grid_distance
        sell_distance = config.grid.sell_grid_distance
        
        margin_per_buy = self.calculate_margin_per_lot(price, buy_lot, leverage)
        margin_per_sell = self.calculate_margin_per_lot(price, sell_lot, leverage)
        pip_value_buy = self.calculate_pip_value_for_lot(buy_lot)
        pip_value_sell = self.calculate_pip_value_for_lot(sell_lot)
        
        positions = []
        current_distance = 0
        total_margin = 0
        safe_margin_level = 1.5
        
        # ใช้ระยะที่เล็กกว่าเป็น step
        step_distance = min(buy_distance, sell_distance) if direction == "both" else (buy_distance if direction == "buy" else sell_distance)
        
        while True:
            current_distance += step_distance
            
            # เพิ่มไม้ตามทิศทาง
            if direction == "both":
                # วางทั้ง Buy และ Sell ทุกๆ step
                positions.append({'distance': current_distance, 'lot': buy_lot, 'type': 'buy', 'pip_value': pip_value_buy})
                positions.append({'distance': current_distance, 'lot': sell_lot, 'type': 'sell', 'pip_value': pip_value_sell})
                total_margin += margin_per_buy + margin_per_sell
            elif direction == "buy":
                positions.append({'distance': current_distance, 'lot': buy_lot, 'type': 'buy', 'pip_value': pip_value_buy})
                total_margin += margin_per_buy
            else:  # sell
                positions.append({'distance': current_distance, 'lot': sell_lot, 'type': 'sell', 'pip_value': pip_value_sell})
                total_margin += margin_per_sell
            
            # คำนวณ Drawdown (worst case: ราคาลงไปเรื่อยๆ)
            # สำหรับ Buy positions: drawdown = ระยะห่างจากราคาเปิด × pip_value
            # สำหรับ Sell positions: ใน worst case (ราคาลง) จะมีกำไร ไม่นับ drawdown
            total_drawdown = sum(
                self.calculate_drawdown_for_position(
                    p['distance'], current_distance, p['pip_value'], p['type']
                ) for p in positions
            )
            
            equity = balance - total_drawdown
            margin_level = equity / total_margin if total_margin > 0 else 999
            
            # หยุดเมื่อ margin level ต่ำเกินไป หรือ equity ไม่พอใช้ margin หรือเกิน 10000 pips
            if margin_level < safe_margin_level or equity < total_margin or current_distance > 10000:
                # คำนวณผลลัพธ์ก่อนที่จะเพิ่ม position ล่าสุด
                prev_distance = current_distance - step_distance
                prev_drawdown = sum(
                    self.calculate_drawdown_for_position(
                        p['distance'], prev_distance, p['pip_value'], p['type']
                    ) for p in (positions[:-2] if direction == "both" else positions[:-1])
                )
                prev_margin = total_margin - (margin_per_buy + margin_per_sell if direction == "both" else (margin_per_buy if direction == "buy" else margin_per_sell))
                
                return {
                    'max_distance_pips': prev_distance,
                    'max_levels': len(positions) - (2 if direction == "both" else 1),
                    'max_margin': prev_margin,
                    'max_drawdown': prev_drawdown,
                    'final_margin_level': (balance - prev_drawdown) / prev_margin if prev_margin > 0 else 999,
                    'final_equity': balance - prev_drawdown,
                    'status': 'AT_LIMIT' if margin_level < safe_margin_level else 'SAFE'
                }
    
    def simulate_grid_with_hg(self, balance: float, price: float, leverage: int = 100) -> Dict:
        """Simulate ระบบ Grid + HG (รองรับ Buy/Sell แยกกัน)"""
        
        direction = config.grid.direction
        buy_lot = config.grid.buy_lot_size
        sell_lot = config.grid.sell_lot_size
        buy_distance = config.grid.buy_grid_distance
        sell_distance = config.grid.sell_grid_distance
        buy_hg_distance = config.hg.buy_hg_distance
        sell_hg_distance = config.hg.sell_hg_distance
        buy_hg_mult = config.hg.buy_hg_multiplier
        sell_hg_mult = config.hg.sell_hg_multiplier
        max_hg_levels = config.hg.max_hg_levels
        
        grid_positions = []
        hg_positions = []
        current_distance = 0
        hg_buy_count = 0
        hg_sell_count = 0
        safe_margin_level = 1.5
        
        while True:
            current_distance += min(buy_distance, sell_distance)
            
            # เพิ่มไม้ Grid
            if direction == "both":
                grid_positions.append({'distance': current_distance, 'lot': buy_lot, 'type': 'buy'})
            elif direction == "buy":
                grid_positions.append({'distance': current_distance, 'lot': buy_lot, 'type': 'buy'})
            else:
                grid_positions.append({'distance': current_distance, 'lot': sell_lot, 'type': 'sell'})
            
            # เช็ค HG trigger
            if current_distance % buy_hg_distance == 0 and hg_buy_count < max_hg_levels:
                net_exposure = sum(p['lot'] for p in grid_positions if p['type'] == 'buy')
                hg_lot = net_exposure * buy_hg_mult
                hg_positions.append({'distance': current_distance, 'lot': hg_lot, 'type': 'buy'})
                hg_buy_count += 1
            
            if current_distance % sell_hg_distance == 0 and hg_sell_count < max_hg_levels:
                net_exposure = sum(p['lot'] for p in grid_positions if p['type'] == 'sell')
                hg_lot = net_exposure * sell_hg_mult
                hg_positions.append({'distance': current_distance, 'lot': hg_lot, 'type': 'sell'})
                hg_sell_count += 1
            
            # คำนวณ Margin และ Drawdown
            total_margin = sum(self.calculate_margin_per_lot(price, p['lot'], leverage) 
                             for p in grid_positions + hg_positions)
            
            # คำนวณ Drawdown ด้วยฟังก์ชันที่ถูกต้อง (worst case: ราคาลงไปเรื่อยๆ)
            grid_dd = sum(
                self.calculate_drawdown_for_position(
                    p['distance'], current_distance, 
                    self.calculate_pip_value_for_lot(p['lot']), 
                    p['type']
                ) for p in grid_positions
            )
            hg_dd = sum(
                self.calculate_drawdown_for_position(
                    p['distance'], current_distance, 
                    self.calculate_pip_value_for_lot(p['lot']), 
                    p['type']
                ) for p in hg_positions
            )
            total_drawdown = grid_dd + hg_dd
            
            equity = balance - total_drawdown
            margin_level = equity / total_margin if total_margin > 0 else 999
            
            if margin_level < safe_margin_level or equity < total_margin or current_distance > 10000:
                return {
                    'max_distance_pips': current_distance - min(buy_distance, sell_distance),
                    'max_grid_levels': len(grid_positions) - 1,
                    'max_hg_levels': len(hg_positions),
                    'max_margin': total_margin,
                    'max_drawdown': total_drawdown,
                    'grid_drawdown': grid_dd,
                    'hg_drawdown': hg_dd,
                    'final_margin_level': margin_level,
                    'final_equity': equity,
                    'status': 'AT_LIMIT' if margin_level < safe_margin_level else 'SAFE'
                }
    
    def calculate_risk(self, balance: float = None, price: float = None, leverage: int = 100) -> Dict:
        """คำนวณความเสี่ยงทั้งหมด"""
        
        if balance is None or price is None:
            account_info = mt5_connection.get_account_info()
            price_info = mt5_connection.get_current_price()
            
            if not account_info or not price_info:
                return {'error': 'Cannot get MT5 data', 'message': 'Please connect to MT5 first'}
            
            balance = balance or account_info.get('balance', 10000)
            price = price or price_info.get('bid', 2600)
            leverage = account_info.get('leverage', 100)
        
        result_grid_only = self.simulate_grid_only(balance, price, leverage)
        result_with_hg = self.simulate_grid_with_hg(balance, price, leverage) if config.hg.enabled else None
        
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

