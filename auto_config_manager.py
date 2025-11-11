# auto_config_manager.py
# คำนวณค่า Config อัตโนมัติสำหรับ Grid Trading with HG

from typing import Dict
import logging
from datetime import datetime
from math import floor
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
        พิจารณา strategy แล้วคำนวณค่า config อัตโนมัติ
        """
        strategy = getattr(config.grid, "auto_strategy", "resilience")
        
        if strategy == "resilience":
            try:
                return self._calculate_resilience_settings()
            except Exception as e:
                logger.error(f"Resilience calculation failed: {e}", exc_info=True)
                # fallback ไปใช้ ATR profile
        
        return self._calculate_atr_profile_settings(risk_profile=risk_profile)

    def _calculate_atr_profile_settings(self, risk_profile: str = "moderate") -> Dict:
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
            logger.error(f"Error calculating ATR profile settings: {e}")
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

    def _calculate_resilience_settings(self) -> Dict:
        """
        คำนวณ Auto Settings ตามแนวคิด Resilience (ตั้งจาก balance + ระยะที่ทนได้)
        """
        from mt5_connection import mt5_connection
        from candle_volume_detector import candle_volume_detector
        from atr_calculator import atr_calculator  # ใช้เพื่อเก็บ reference ATR
        
        account_info = mt5_connection.get_account_info()
        price_info = mt5_connection.get_current_price()
        
        if not account_info or not price_info:
            raise ValueError("Account or price data unavailable (MT5 not connected?)")
        
        balance = float(account_info.get("balance", 0.0))
        equity = float(account_info.get("equity", balance))
        free_margin = float(account_info.get("free_margin", 0.0))
        leverage = int(account_info.get("leverage", 100)) or 100
        price = float(price_info.get("bid") or price_info.get("ask") or 0.0)
        if price <= 0:
            raise ValueError("Invalid price data from MT5")
        
        distance_pips = max(int(getattr(config.grid, "auto_resilience_distance", 5000)), 100)
        drawdown_ratio = getattr(config.grid, "auto_drawdown_ratio", 0.6)
        drawdown_ratio = max(0.1, min(drawdown_ratio, 0.95))
        max_levels_cap = max(1, int(getattr(config.grid, "auto_max_levels", 40)))
        
        lot_size = max(config.grid.buy_lot_size, 0.01)
        # ถ้า manual sell lot ไม่เท่ากัน ให้ใช้เฉลี่ย
        if config.grid.sell_lot_size > 0:
            lot_size = max(lot_size, config.grid.sell_lot_size)
        
        target_drawdown = balance * drawdown_ratio
        pip_value_per_lot = 10.0  # XAUUSD: 1 lot = $10/pip
        contract_size = 100  # XAUUSD
        margin_per_lot = (price * contract_size) / leverage
        margin_per_position = margin_per_lot * lot_size
        
        if lot_size <= 0 or distance_pips <= 0:
            raise ValueError("Invalid lot size or distance for resilience calculation")
        
        denominator = pip_value_per_lot * lot_size * distance_pips
        if denominator <= 0:
            raise ValueError("Invalid parameters for level calculation")
        
        # จำนวน level ที่ยังอยู่ในขอบเขต drawdown
        levels_from_drawdown = floor((2 * target_drawdown) / denominator - 1)
        max_margin_budget = balance * (config.risk.max_margin_usage / 100.0)
        if margin_per_position > 0:
            levels_from_margin = floor(max_margin_budget / margin_per_position)
        else:
            levels_from_margin = max_levels_cap
        
        levels = max(1, min(levels_from_drawdown, levels_from_margin, max_levels_cap))
        
        # ป้องกันกรณี levels_from_drawdown < 1
        if levels < 1:
            levels = 1
        
        grid_distance = max(int(round(distance_pips / levels)), 5)
        actual_distance = grid_distance * levels
        
        total_margin = margin_per_position * levels
        if balance > 0:
            margin_usage_percent = min(100.0, (total_margin / balance) * 100.0)
        else:
            margin_usage_percent = 0.0
        
        drawdown_per_level = pip_value_per_lot * lot_size * grid_distance
        estimated_drawdown = drawdown_per_level * (levels * (levels + 1) / 2)
        
        hg_distance = max(grid_distance * 4, grid_distance * 2)
        # อย่าให้ HG ไกลกว่าเป้าระยะที่ทนได้มากเกิน
        hg_distance = min(hg_distance, max(distance_pips, grid_distance * 2))
        hg_sl_trigger = max(int(hg_distance * 0.5), grid_distance)
        
        # Direction จาก Candle + Volume
        direction_info = candle_volume_detector.get_full_analysis()
        if direction_info:
            direction = direction_info.get("direction", "both")
            confidence = direction_info.get("confidence", "LOW")
        else:
            direction = "both"
            confidence = "LOW"
        
        atr_value = atr_calculator.calculate_atr() or 0.0
        
        settings = {
            "direction": direction,
            "confidence": confidence,
            "buy_grid_distance": int(grid_distance),
            "sell_grid_distance": int(grid_distance),
            "buy_hg_distance": int(hg_distance),
            "sell_hg_distance": int(hg_distance),
            "buy_hg_sl_trigger": int(hg_sl_trigger),
            "sell_hg_sl_trigger": int(hg_sl_trigger),
            "atr": atr_value,
            "risk_profile": config.grid.risk_profile,
            "timestamp": datetime.now(),
            "plan": {
                "requested_distance": int(distance_pips),
                "actual_distance": int(actual_distance),
                "grid_levels": int(levels),
                "lot_size": float(lot_size),
                "estimated_drawdown": float(estimated_drawdown),
                "target_drawdown": float(target_drawdown),
                "drawdown_ratio": float(drawdown_ratio),
                "margin_usage_percent": float(margin_usage_percent),
                "total_margin": float(total_margin),
                "balance": float(balance),
                "equity": float(equity),
                "free_margin": float(free_margin),
                "price": float(price),
                "margin_per_position": float(margin_per_position),
                "pip_value_per_lot": float(pip_value_per_lot),
                "grid_distance_price": float(config.pips_to_price(grid_distance)),
                "hg_distance_price": float(config.pips_to_price(hg_distance)),
                "levels_from_drawdown": int(max(levels_from_drawdown, 0)),
                "levels_from_margin": int(max(levels_from_margin, 0))
            }
        }
        
        logger.info("Resilience settings calculated:")
        logger.info(f"  Balance: ${balance:,.2f} | Distance Target: {distance_pips} pips")
        logger.info(f"  Levels: {levels} | Grid Distance: {grid_distance} pips")
        logger.info(f"  HG Distance: {hg_distance} pips | Margin Usage: {margin_usage_percent:.1f}%")
        logger.info(f"  Estimated Drawdown: ${estimated_drawdown:,.2f}")
        
        return settings
    
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

