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
        """คำนวณมูลค่าต่อ pip สำหรับ lot ที่กำหนด"""
        return lot * self.pip_value_per_lot
    
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
        total_drawdown = 0
        safe_margin_level = 1.5
        
        while True:
            current_distance += min(buy_distance, sell_distance)  # ใช้ระยะที่เล็กกว่า
            
            # เพิ่มไม้ตามทิศทาง
            if direction == "both":
                positions.append({'distance': current_distance, 'lot': buy_lot, 'type': 'buy', 'pip_value': pip_value_buy})
                total_margin += margin_per_buy
            elif direction == "buy":
                positions.append({'distance': current_distance, 'lot': buy_lot, 'type': 'buy', 'pip_value': pip_value_buy})
                total_margin += margin_per_buy
            else:  # sell
                positions.append({'distance': current_distance, 'lot': sell_lot, 'type': 'sell', 'pip_value': pip_value_sell})
                total_margin += margin_per_sell
            
            # คำนวณ Drawdown
            total_drawdown = sum((current_distance - p['distance']) * p['pip_value'] for p in positions)
            
            equity = balance - total_drawdown
            margin_level = equity / total_margin if total_margin > 0 else 999
            
            if margin_level < safe_margin_level or equity < total_margin or current_distance > 10000:
                return {
                    'max_distance_pips': current_distance - min(buy_distance, sell_distance),
                    'max_levels': len(positions) - 1,
                    'max_margin': total_margin - (margin_per_buy if direction != "sell" else margin_per_sell),
                    'max_drawdown': total_drawdown,
                    'final_margin_level': margin_level,
                    'final_equity': equity,
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
            
            grid_dd = sum((current_distance - p['distance']) * self.calculate_pip_value_for_lot(p['lot']) 
                         for p in grid_positions)
            hg_dd = sum((current_distance - p['distance']) * self.calculate_pip_value_for_lot(p['lot']) 
                       for p in hg_positions)
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

