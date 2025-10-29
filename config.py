# config.py
# ไฟล์จัดการการตั้งค่าระบบ Grid Trading with HG

import configparser
import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class GridSettings:
    """การตั้งค่า Grid Trading"""
    # General
    direction: str = "both"        # ทิศทาง: buy, sell, both
    
    # Buy Settings
    buy_grid_distance: int = 50    # ระยะห่าง Grid Buy (pips)
    buy_lot_size: float = 0.01     # ขนาด lot Buy
    buy_take_profit: int = 50      # Take Profit Buy (pips)
    
    # Sell Settings
    sell_grid_distance: int = 50   # ระยะห่าง Grid Sell (pips)
    sell_lot_size: float = 0.01    # ขนาด lot Sell
    sell_take_profit: int = 50     # Take Profit Sell (pips)
    
    # Backward compatibility (ค่าเดิม)
    grid_distance: int = 50
    lot_size: float = 0.01
    take_profit: int = 50
    
@dataclass
class HGSettings:
    """การตั้งค่า Hedge (HG)"""
    # General
    enabled: bool = True           # เปิด/ปิดระบบ HG
    direction: str = "buy"         # ทิศทาง HG: buy, sell, both (ตั้งเป็น buy only)
    
    # Buy HG Settings
    buy_hg_distance: int = 200     # ระยะห่างที่วาง HG Buy (pips)
    buy_hg_sl_trigger: int = 100   # ระยะที่จะตั้ง SL breakeven Buy (pips)
    buy_hg_multiplier: float = 1.2 # ตัวคูณสำหรับคำนวณ HG lot Buy
    buy_hg_initial_lot: float = 0.01 # Lot เริ่มต้นของ HG Buy
    buy_sl_buffer: int = 10        # buffer สำหรับ SL Buy (pips)
    buy_max_hg_levels: int = 10    # จำนวน HG levels สูงสุด Buy
    
    # Sell HG Settings
    sell_hg_distance: int = 2000   # ระยะห่างที่วาง HG Sell (pips)
    sell_hg_sl_trigger: int = 1000 # ระยะที่จะตั้ง SL breakeven Sell (pips)
    sell_hg_multiplier: float = 1.2 # ตัวคูณสำหรับคำนวณ HG lot Sell
    sell_hg_initial_lot: float = 0.01 # Lot เริ่มต้นของ HG Sell
    sell_sl_buffer: int = 20       # buffer สำหรับ SL Sell (pips)
    sell_max_hg_levels: int = 10   # จำนวน HG levels สูงสุด Sell
    
    # Backward compatibility
    sl_buffer: int = 10
    max_hg_levels: int = 10
    hg_distance: int = 200
    hg_sl_trigger: int = 100
    hg_multiplier: float = 1.2
    
@dataclass
class MT5Settings:
    """การตั้งค่า MT5 Connection"""
    symbol: str = "XAUUSD"
    magic_number: int = 123456
    deviation: int = 20        # Slippage ที่ยอมรับได้
    comment_grid: str = "GridBot"
    comment_hg: str = "HG"
    
@dataclass
class RiskSettings:
    """การตั้งค่าความเสี่ยง"""
    max_margin_usage: float = 80.0  # Margin สูงสุดที่ใช้ได้ (%)
    max_drawdown: float = 1000.0    # Drawdown สูงสุด ($)
    alert_enabled: bool = True
    

class Config:
    """คลาสหลักสำหรับจัดการการตั้งค่าทั้งหมด"""
    
    def __init__(self, config_file: str = "settings.ini"):
        self.config_file = config_file
        self.grid = GridSettings()
        self.hg = HGSettings()
        self.mt5 = MT5Settings()
        self.risk = RiskSettings()
        
        # โหลดการตั้งค่าจากไฟล์ถ้ามี
        if os.path.exists(config_file):
            self.load_from_file()
        else:
            # ถ้าไม่มีไฟล์ ให้สร้างไฟล์ default
            self.save_to_file()
    
    def load_from_file(self):
        """โหลดการตั้งค่าจากไฟล์ .ini"""
        parser = configparser.ConfigParser()
        parser.read(self.config_file)
        
        try:
            # Grid Settings
            if 'Grid' in parser:
                self.grid.direction = parser.get('Grid', 'direction', fallback='both')
                
                # Buy Settings
                self.grid.buy_grid_distance = parser.getint('Grid', 'buy_grid_distance', fallback=200)
                self.grid.buy_lot_size = parser.getfloat('Grid', 'buy_lot_size', fallback=0.01)
                self.grid.buy_take_profit = parser.getint('Grid', 'buy_take_profit', fallback=100)
                
                # Sell Settings
                self.grid.sell_grid_distance = parser.getint('Grid', 'sell_grid_distance', fallback=200)
                self.grid.sell_lot_size = parser.getfloat('Grid', 'sell_lot_size', fallback=0.01)
                self.grid.sell_take_profit = parser.getint('Grid', 'sell_take_profit', fallback=100)
                
                # Backward compatibility
                self.grid.grid_distance = parser.getint('Grid', 'grid_distance', fallback=200)
                self.grid.lot_size = parser.getfloat('Grid', 'lot_size', fallback=0.01)
                self.grid.take_profit = parser.getint('Grid', 'take_profit', fallback=100)
            
            # HG Settings
            if 'HG' in parser:
                self.hg.enabled = parser.getboolean('HG', 'enabled', fallback=True)
                self.hg.direction = parser.get('HG', 'direction', fallback='both')
                
                # Buy HG Settings
                self.hg.buy_hg_distance = parser.getint('HG', 'buy_hg_distance', fallback=2000)
                self.hg.buy_hg_sl_trigger = parser.getint('HG', 'buy_hg_sl_trigger', fallback=1000)
                self.hg.buy_hg_multiplier = parser.getfloat('HG', 'buy_hg_multiplier', fallback=1.2)
                self.hg.buy_hg_initial_lot = parser.getfloat('HG', 'buy_hg_initial_lot', fallback=0.01)
                self.hg.buy_sl_buffer = parser.getint('HG', 'buy_sl_buffer', fallback=20)
                self.hg.buy_max_hg_levels = parser.getint('HG', 'buy_max_hg_levels', fallback=10)
                
                # Sell HG Settings
                self.hg.sell_hg_distance = parser.getint('HG', 'sell_hg_distance', fallback=2000)
                self.hg.sell_hg_sl_trigger = parser.getint('HG', 'sell_hg_sl_trigger', fallback=1000)
                self.hg.sell_hg_multiplier = parser.getfloat('HG', 'sell_hg_multiplier', fallback=1.2)
                self.hg.sell_hg_initial_lot = parser.getfloat('HG', 'sell_hg_initial_lot', fallback=0.01)
                self.hg.sell_sl_buffer = parser.getint('HG', 'sell_sl_buffer', fallback=20)
                self.hg.sell_max_hg_levels = parser.getint('HG', 'sell_max_hg_levels', fallback=10)
                
                # Backward compatibility
                self.hg.sl_buffer = parser.getint('HG', 'sl_buffer', fallback=20)
                self.hg.max_hg_levels = parser.getint('HG', 'max_hg_levels', fallback=10)
                self.hg.hg_distance = parser.getint('HG', 'hg_distance', fallback=2000)
                self.hg.hg_sl_trigger = parser.getint('HG', 'hg_sl_trigger', fallback=1000)
                self.hg.hg_multiplier = parser.getfloat('HG', 'hg_multiplier', fallback=1.2)
            
            # MT5 Settings
            if 'MT5' in parser:
                self.mt5.symbol = parser.get('MT5', 'symbol', fallback='XAUUSD')
                self.mt5.magic_number = parser.getint('MT5', 'magic_number', fallback=123456)
                self.mt5.deviation = parser.getint('MT5', 'deviation', fallback=20)
            
            # Risk Settings
            if 'Risk' in parser:
                self.risk.max_margin_usage = parser.getfloat('Risk', 'max_margin_usage', fallback=80.0)
                self.risk.max_drawdown = parser.getfloat('Risk', 'max_drawdown', fallback=1000.0)
                self.risk.alert_enabled = parser.getboolean('Risk', 'alert_enabled', fallback=True)
                
        except Exception as e:
            print(f"Error loading config: {e}")
    
    def save_to_file(self):
        """บันทึกการตั้งค่าลงไฟล์ .ini"""
        parser = configparser.ConfigParser()
        
        # Grid Section
        parser['Grid'] = {
            'direction': self.grid.direction,
            # Buy Settings
            'buy_grid_distance': str(self.grid.buy_grid_distance),
            'buy_lot_size': str(self.grid.buy_lot_size),
            'buy_take_profit': str(self.grid.buy_take_profit),
            # Sell Settings
            'sell_grid_distance': str(self.grid.sell_grid_distance),
            'sell_lot_size': str(self.grid.sell_lot_size),
            'sell_take_profit': str(self.grid.sell_take_profit),
            # Backward compatibility
            'grid_distance': str(self.grid.grid_distance),
            'lot_size': str(self.grid.lot_size),
            'take_profit': str(self.grid.take_profit)
        }
        
        # HG Section
        parser['HG'] = {
            'enabled': str(self.hg.enabled),
            'direction': self.hg.direction,
            # Buy HG Settings
            'buy_hg_distance': str(self.hg.buy_hg_distance),
            'buy_hg_sl_trigger': str(self.hg.buy_hg_sl_trigger),
            'buy_hg_multiplier': str(self.hg.buy_hg_multiplier),
            'buy_hg_initial_lot': str(self.hg.buy_hg_initial_lot),
            'buy_sl_buffer': str(self.hg.buy_sl_buffer),
            'buy_max_hg_levels': str(self.hg.buy_max_hg_levels),
            # Sell HG Settings
            'sell_hg_distance': str(self.hg.sell_hg_distance),
            'sell_hg_sl_trigger': str(self.hg.sell_hg_sl_trigger),
            'sell_hg_multiplier': str(self.hg.sell_hg_multiplier),
            'sell_hg_initial_lot': str(self.hg.sell_hg_initial_lot),
            'sell_sl_buffer': str(self.hg.sell_sl_buffer),
            'sell_max_hg_levels': str(self.hg.sell_max_hg_levels),
            # Backward compatibility
            'sl_buffer': str(self.hg.sl_buffer),
            'max_hg_levels': str(self.hg.max_hg_levels),
            'hg_distance': str(self.hg.hg_distance),
            'hg_sl_trigger': str(self.hg.hg_sl_trigger),
            'hg_multiplier': str(self.hg.hg_multiplier)
        }
        
        # MT5 Section
        parser['MT5'] = {
            'symbol': self.mt5.symbol,
            'magic_number': str(self.mt5.magic_number),
            'deviation': str(self.mt5.deviation),
            'comment_grid': self.mt5.comment_grid,
            'comment_hg': self.mt5.comment_hg
        }
        
        # Risk Section
        parser['Risk'] = {
            'max_margin_usage': str(self.risk.max_margin_usage),
            'max_drawdown': str(self.risk.max_drawdown),
            'alert_enabled': str(self.risk.alert_enabled)
        }
        
        with open(self.config_file, 'w') as f:
            parser.write(f)
    
    def update_grid_settings(self, **kwargs):
        """อัพเดทการตั้งค่า Grid"""
        for key, value in kwargs.items():
            if hasattr(self.grid, key):
                setattr(self.grid, key, value)
    
    def update_hg_settings(self, **kwargs):
        """อัพเดทการตั้งค่า HG"""
        for key, value in kwargs.items():
            if hasattr(self.hg, key):
                setattr(self.hg, key, value)
    
    def get_pip_value(self) -> float:
        """คืนค่า pip สำหรับ XAUUSD (0.1 = 1 pip)"""
        return 0.1
    
    def pips_to_price(self, pips: float) -> float:
        """แปลง pips เป็นราคา"""
        return pips * self.get_pip_value()
    
    def price_to_pips(self, price: float) -> float:
        """แปลงราคาเป็น pips"""
        return price / self.get_pip_value()


# สร้าง instance หลักสำหรับใช้งาน
config = Config()

