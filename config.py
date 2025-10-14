# config.py
# ไฟล์จัดการการตั้งค่าระบบ Grid Trading with HG

import configparser
import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class GridSettings:
    """การตั้งค่า Grid Trading"""
    grid_distance: int = 200  # ระยะห่าง Grid (pips)
    direction: str = "buy"    # ทิศทาง: buy, sell, both
    lot_size: float = 0.01    # ขนาด lot ต่อ Grid
    take_profit: int = 100    # Take Profit (pips)
    
@dataclass
class HGSettings:
    """การตั้งค่า Hedge (HG)"""
    hg_distance: int = 2000   # ระยะห่างที่วาง HG (pips)
    hg_sl_trigger: int = 1000 # ระยะที่จะตั้ง SL breakeven (pips)
    sl_buffer: int = 20       # buffer สำหรับ SL (pips)
    hg_multiplier: float = 1.2 # ตัวคูณสำหรับคำนวณ HG lot
    
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
    
    def load_from_file(self):
        """โหลดการตั้งค่าจากไฟล์ .ini"""
        parser = configparser.ConfigParser()
        parser.read(self.config_file)
        
        try:
            # Grid Settings
            if 'Grid' in parser:
                self.grid.grid_distance = parser.getint('Grid', 'grid_distance', fallback=200)
                self.grid.direction = parser.get('Grid', 'direction', fallback='buy')
                self.grid.lot_size = parser.getfloat('Grid', 'lot_size', fallback=0.01)
                self.grid.take_profit = parser.getint('Grid', 'take_profit', fallback=100)
            
            # HG Settings
            if 'HG' in parser:
                self.hg.hg_distance = parser.getint('HG', 'hg_distance', fallback=2000)
                self.hg.hg_sl_trigger = parser.getint('HG', 'hg_sl_trigger', fallback=1000)
                self.hg.sl_buffer = parser.getint('HG', 'sl_buffer', fallback=20)
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
            'grid_distance': str(self.grid.grid_distance),
            'direction': self.grid.direction,
            'lot_size': str(self.grid.lot_size),
            'take_profit': str(self.grid.take_profit)
        }
        
        # HG Section
        parser['HG'] = {
            'hg_distance': str(self.hg.hg_distance),
            'hg_sl_trigger': str(self.hg.hg_sl_trigger),
            'sl_buffer': str(self.hg.sl_buffer),
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

