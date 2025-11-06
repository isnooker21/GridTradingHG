# auto_config_manager.py
# คำนวณค่า Config อัตโนมัติสำหรับ Grid Trading with HG

from typing import Dict, Optional
import logging
from datetime import datetime
from config import config

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)  # Auto Config Manager ใช้ WARNING เพื่อลด log


# Risk Profiles (5 แบบ)
RISK_PROFILES = {
    "very_conservative": {
        "grid_atr_multiplier": 2.0,
        "hg_grid_multiplier": 5.0,
        "hg_sl_ratio": 0.7,
        "description": "Very Safe - Grid กว้างมาก, HG ไกลมาก"
    },
    "conservative": {
        "grid_atr_multiplier": 1.5,
        "hg_grid_multiplier": 4.0,
        "hg_sl_ratio": 0.6,
        "description": "Safe - Grid กว้าง, HG ไกล"
    },
    "moderate": {
        "grid_atr_multiplier": 1.0,
        "hg_grid_multiplier": 3.0,
        "hg_sl_ratio": 0.5,
        "description": "Balanced - สมดุล (แนะนำ)"
    },
    "aggressive": {
        "grid_atr_multiplier": 0.7,
        "hg_grid_multiplier": 2.5,
        "hg_sl_ratio": 0.4,
        "description": "Risky - Grid แคบ, HG ใกล้"
    },
    "very_aggressive": {
        "grid_atr_multiplier": 0.5,
        "hg_grid_multiplier": 2.0,
        "hg_sl_ratio": 0.35,
        "description": "Very Risky - Grid แคบมาก, HG ใกล้มาก"
    }
}


class AutoConfigManager:
    """คลาสสำหรับคำนวณค่า Config อัตโนมัติ"""
    
    def __init__(self):
        pass
    
    def get_risk_profile_multipliers(self, profile: str) -> Dict:
        """
        ดึง multipliers ตาม risk profile
        
        Args:
            profile: ชื่อ risk profile
            
        Returns:
            Dict ที่มี multipliers
        """
        if profile not in RISK_PROFILES:
            logger.warning(f"Unknown risk profile: {profile}, using 'moderate'")
            profile = "moderate"
        
        return RISK_PROFILES[profile]
    
    def calculate_auto_settings(self, risk_profile: str = "moderate") -> Dict:
        """
        คำนวณค่า Config อัตโนมัติ
        
        Auto Calculation Formula:
        1. ดึง ATR จาก atr_calculator
        2. ดึง Direction จาก candle_volume_detector (Candle + Volume)
        3. คำนวณ Grid Distance = ATR * grid_atr_multiplier
        4. คำนวณ HG Distance = Grid Distance * hg_grid_multiplier
        5. คำนวณ HG SL Trigger = HG Distance * hg_sl_ratio
        6. ตั้ง Direction ตาม Candle + Volume Analysis
        
        Args:
            risk_profile: ชื่อ risk profile (very_conservative, conservative, moderate, aggressive, very_aggressive)
            
        Returns:
            Dict ที่มีค่า settings ทั้งหมด
        """
        try:
            from atr_calculator import atr_calculator
            from candle_volume_detector import candle_volume_detector
            
            # ดึงข้อมูล ATR และ Direction Analysis
            atr = atr_calculator.calculate_atr()
            direction_info = candle_volume_detector.get_full_analysis()
            
            if direction_info:
                direction = direction_info['direction']
                confidence = direction_info['confidence']
            else:
                direction = "both"
                confidence = "LOW"
            
            if atr is None:
                logger.error("Cannot calculate ATR, using default values")
                atr = 50  # ค่า default
            
            # ดึง multipliers ตาม risk profile
            multipliers = self.get_risk_profile_multipliers(risk_profile)
            
            # คำนวณ Grid Distance
            grid_distance = round(atr * multipliers["grid_atr_multiplier"], 0)
            grid_distance = max(20, min(200, grid_distance))  # Limit 20-200 pips
            
            # คำนวณ HG Distance
            hg_distance = round(grid_distance * multipliers["hg_grid_multiplier"], 0)
            hg_distance = max(100, min(1000, hg_distance))  # Limit 100-1000 pips
            
            # คำนวณ HG SL Trigger
            hg_sl_trigger = round(hg_distance * multipliers["hg_sl_ratio"], 0)
            
            # สร้าง settings dictionary
            settings = {
                # Direction
                "direction": direction,
                "confidence": confidence,
                
                # Grid Settings (ใช้ค่าเดียวกันสำหรับ Buy/Sell)
                "buy_grid_distance": int(grid_distance),
                "sell_grid_distance": int(grid_distance),
                
                # HG Settings (ใช้ค่าเดียวกันสำหรับ Buy/Sell)
                "buy_hg_distance": int(hg_distance),
                "sell_hg_distance": int(hg_distance),
                "buy_hg_sl_trigger": int(hg_sl_trigger),
                "sell_hg_sl_trigger": int(hg_sl_trigger),
                
                # ข้อมูลเพิ่มเติม
                "atr": atr,
                "risk_profile": risk_profile,
                "timestamp": datetime.now()
            }
            
            logger.info(f"Auto settings calculated:")
            logger.info(f"  Risk Profile: {risk_profile}")
            logger.info(f"  ATR: {atr:.1f} pips")
            logger.info(f"  Direction: {direction} ({confidence})")
            logger.info(f"  Grid Distance: {grid_distance} pips")
            logger.info(f"  HG Distance: {hg_distance} pips")
            logger.info(f"  HG SL Trigger: {hg_sl_trigger} pips")
            
            return settings
            
        except Exception as e:
            logger.error(f"Error calculating auto settings: {e}")
            # Return default safe settings
            return {
                "direction": "both",
                "confidence": "LOW",
                "buy_grid_distance": 50,
                "sell_grid_distance": 50,
                "buy_hg_distance": 200,
                "sell_hg_distance": 200,
                "buy_hg_sl_trigger": 100,
                "sell_hg_sl_trigger": 100,
                "atr": 0.0,
                "risk_profile": risk_profile,
                "timestamp": datetime.now()
            }
    
    def calculate_survivability(self, balance: float, price: float, 
                                leverage: int, settings: Dict) -> Dict:
        """
        คำนวณว่าระบบทนได้กี่ pips ก่อน Margin Call
        
        Worst Case: ราคาเดินทางเดียวไม่กลับ (เช่น ราคาลงเรื่อยๆ)
        
        Args:
            balance: ยอดเงินในบัญชี
            price: ราคาปัจจุบัน
            leverage: Leverage ของบัญชี
            settings: Dict ที่มีค่า settings (จาก calculate_auto_settings)
            
        Returns:
            Dict ที่มีข้อมูล survivability
        """
        try:
            # ข้อมูลพื้นฐาน
            grid_distance = settings.get("buy_grid_distance", 50)
            grid_lot = config.grid.buy_lot_size  # ใช้ค่าจาก config (ผู้ใช้ตั้งเอง)
            hg_distance = settings.get("buy_hg_distance", 200)
            hg_initial_lot = config.hg.buy_hg_initial_lot  # ใช้ค่าจาก config (ผู้ใช้ตั้งเอง)
            hg_multiplier = config.hg.buy_hg_multiplier  # ใช้ค่าจาก config (ผู้ใช้ตั้งเอง)
            
            # คำนวณ Margin Per Lot
            contract_size = 100  # XAUUSD
            margin_per_lot = (1.0 * contract_size * price) / leverage
            margin_per_grid_lot = margin_per_lot * grid_lot
            
            # Pip Value
            pip_value_per_lot = 10.0  # 1 lot = $10/pip สำหรับ XAUUSD
            pip_value_grid = grid_lot * pip_value_per_lot
            
            # Simulation Parameters
            max_margin_percent = 0.8  # ใช้ Margin สูงสุด 80%
            safe_margin_level = 1.5  # Margin Level ขั้นต่ำ 150%
            
            # Variables for simulation
            total_margin = 0.0
            total_drawdown = 0.0
            grid_positions = []
            hg_positions = []
            current_distance = 0
            hg_count = 0
            
            # Grid distance ใน price
            grid_distance_price = config.pips_to_price(grid_distance)
            hg_distance_price = config.pips_to_price(hg_distance)
            
            # Simulation Loop (Worst Case: ราคาลงเรื่อยๆ)
            max_iterations = 10000  # ป้องกัน infinite loop
            iteration = 0
            
            while iteration < max_iterations:
                iteration += 1
                current_distance += grid_distance
                
                # เพิ่ม Grid Position
                grid_positions.append({
                    "distance_pips": current_distance,
                    "lot": grid_lot,
                    "type": "buy"
                })
                total_margin += margin_per_grid_lot
                
                # เช็คว่าต้องออก HG หรือไม่
                if current_distance % hg_distance == 0 and hg_count < config.hg.buy_max_hg_levels:
                    # คำนวณ HG Lot (ใช้ total grid exposure * multiplier)
                    grid_exposure = sum(p["lot"] for p in grid_positions)
                    hg_lot = max(grid_exposure * hg_multiplier, hg_initial_lot)
                    
                    hg_positions.append({
                        "distance_pips": current_distance,
                        "lot": hg_lot,
                        "type": "sell"  # HG ตรงข้ามกับ Grid
                    })
                    total_margin += margin_per_lot * hg_lot
                    hg_count += 1
                
                # คำนวณ Drawdown (Worst Case: ราคาลงเรื่อยๆ)
                total_drawdown = 0.0
                
                # Drawdown จาก Grid positions (Buy positions ขาดทุนเมื่อราคาลง)
                for pos in grid_positions:
                    pips_loss = current_distance  # ราคาลงจากจุดเปิด
                    drawdown = pips_loss * (pos["lot"] * pip_value_per_lot)
                    total_drawdown += drawdown
                
                # Drawdown จาก HG positions (Sell positions กำไรเมื่อราคาลง - ลด drawdown)
                for pos in hg_positions:
                    pips_gain = current_distance  # Sell กำไรเมื่อราคาลง
                    profit = pips_gain * (pos["lot"] * pip_value_per_lot)
                    total_drawdown -= profit  # ลด drawdown
                
                # คำนวณ Equity และ Margin Level
                equity = balance - total_drawdown
                
                # ป้องกัน division by zero
                if total_margin > 0:
                    margin_level = equity / total_margin
                else:
                    margin_level = 999
                
                # เช็คว่าถึงขีดจำกัดหรือยัง
                if margin_level < safe_margin_level or equity <= 0 or current_distance > 10000:
                    # ถึงขีดจำกัดแล้ว
                    break
            
            # สถานะ
            if margin_level < safe_margin_level:
                status = "AT_LIMIT"
            elif equity <= 0:
                status = "MARGIN_CALL"
            else:
                status = "SAFE"
            
            # ผลลัพธ์
            result = {
                "max_distance_pips": current_distance - grid_distance,  # ลบ grid_distance สุดท้าย
                "max_grid_levels": len(grid_positions) - 1,
                "max_hg_levels": len(hg_positions),
                "max_margin": total_margin,
                "max_drawdown": total_drawdown,
                "final_margin_level": margin_level,
                "final_equity": equity,
                "status": status
            }
            
            logger.info(f"Survivability calculated:")
            logger.info(f"  Max Distance: {result['max_distance_pips']:,} pips")
            logger.info(f"  Max Grid Levels: {result['max_grid_levels']}")
            logger.info(f"  Max HG Levels: {result['max_hg_levels']}")
            logger.info(f"  Status: {status}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error calculating survivability: {e}")
            return {
                "max_distance_pips": 0,
                "max_grid_levels": 0,
                "max_hg_levels": 0,
                "max_margin": 0.0,
                "max_drawdown": 0.0,
                "final_margin_level": 0.0,
                "final_equity": 0.0,
                "status": "ERROR"
            }


# สร้าง instance หลักสำหรับใช้งาน
auto_config_manager = AutoConfigManager()

