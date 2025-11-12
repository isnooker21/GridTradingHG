# position_monitor.py
# ไฟล์ติดตามและจัดการ positions ทั้งหมด

from typing import Dict, List
import logging
from mt5_connection import mt5_connection
from config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PositionMonitor:
    """คลาสสำหรับติดตามและจัดการ positions"""
    
    def __init__(self):
        self.positions = []
        self.total_pnl = 0.0
        self.grid_positions = []
        self.hg_positions = []
        self.alerts = []
        
    def update_all_positions(self):
        """
        อัพเดทข้อมูล positions ทั้งหมดจาก MT5
        แยกเป็น Grid positions และ HG positions
        """
        try:
            self.positions = mt5_connection.get_all_positions()
            
            # แยก positions
            self.grid_positions = []
            self.hg_positions = []
            
            for pos in self.positions:
                if config.mt5.comment_hg in pos['comment']:
                    self.hg_positions.append(pos)
                elif (config.mt5.comment_grid in pos['comment'] or
                      config.mt5.comment_auto in pos['comment']):
                    self.grid_positions.append(pos)
            
            # อัพเดท P&L
            self.total_pnl = self.calculate_total_pnl()
            
        except Exception as e:
            logger.error(f"Error updating positions: {e}")
    
    def calculate_total_pnl(self) -> float:
        """
        คำนวณกำไร/ขาดทุนรวมทั้งหมด
        
        Returns:
            ยอดกำไร/ขาดทุนรวม
        """
        total = 0.0
        for pos in self.positions:
            total += pos['profit']
        return total
    
    def calculate_grid_pnl(self) -> float:
        """
        คำนวณกำไร/ขาดทุนของ Grid positions
        
        Returns:
            ยอดกำไร/ขาดทุนของ Grid
        """
        total = 0.0
        for pos in self.grid_positions:
            total += pos['profit']
        return total
    
    def calculate_hg_pnl(self) -> float:
        """
        คำนวณกำไร/ขาดทุนของ HG positions
        
        Returns:
            ยอดกำไร/ขาดทุนของ HG
        """
        total = 0.0
        for pos in self.hg_positions:
            total += pos['profit']
        return total
    
    def get_total_grid_volume(self) -> float:
        """
        คำนวณ volume รวมของ Grid positions
        
        Returns:
            volume รวม (lots)
        """
        total = 0.0
        for pos in self.grid_positions:
            if pos['type'] == 'buy':
                total += pos['volume']
            else:  # sell
                total -= pos['volume']
        return abs(total)
    
    def get_net_grid_exposure(self) -> Dict:
        """
        คำนวณ exposure สุทธิของ Grid
        
        Returns:
            Dict ที่มี buy_volume, sell_volume, net_volume
        """
        buy_volume = 0.0
        sell_volume = 0.0
        
        for pos in self.grid_positions:
            if pos['type'] == 'buy':
                buy_volume += pos['volume']
            else:
                sell_volume += pos['volume']
        
        return {
            'buy_volume': buy_volume,
            'sell_volume': sell_volume,
            'net_volume': abs(buy_volume - sell_volume),
            'net_direction': 'buy' if buy_volume > sell_volume else 'sell'
        }
    
    def check_margin_usage(self) -> Dict:
        """
        ตรวจสอบการใช้ margin
        
        Returns:
            Dict ที่มีข้อมูล margin
        """
        try:
            account = mt5_connection.get_account_info()
            if not account:
                return {'status': 'error', 'margin_percent': 0}
            
            # คำนวณเปอร์เซ็นต์การใช้ margin
            if account['equity'] > 0:
                margin_percent = (account['margin'] / account['equity']) * 100
            else:
                margin_percent = 0
            
            # ตรวจสอบว่าเกินขีดจำกัดหรือไม่
            warning = margin_percent > config.risk.max_margin_usage
            
            return {
                'status': 'warning' if warning else 'normal',
                'margin': account['margin'],
                'free_margin': account['free_margin'],
                'equity': account['equity'],
                'margin_percent': margin_percent,
                'margin_level': account['margin_level']
            }
            
        except Exception as e:
            logger.error(f"Error checking margin: {e}")
            return {'status': 'error', 'margin_percent': 0}
    
    def monitor_risk_limits(self) -> List[str]:
        """
        ตรวจสอบขีดจำกัดความเสี่ยงทั้งหมด
        
        Returns:
            List ของข้อความแจ้งเตือน
        """
        warnings = []
        
        # ตรวจสอบ margin
        # margin_info = self.check_margin_usage()
        # if margin_info['status'] == 'warning':
        #     warnings.append(f"⚠️ Margin Usage: {margin_info['margin_percent']:.1f}% (เกิน {config.risk.max_margin_usage}%)")
        
        # ตรวจสอบ drawdown (ปิดการแจ้งเตือน)
        # if self.total_pnl < -config.risk.max_drawdown:
        #     warnings.append(f"⚠️ Drawdown: ${abs(self.total_pnl):.2f} (เกิน ${config.risk.max_drawdown})")
        
        # ตรวจสอบจำนวน positions
        # if len(self.positions) > 50:
        #     warnings.append(f"⚠️ Positions: {len(self.positions)} positions (มากเกินไป)")
        
        return warnings
    
    def send_alerts(self):
        """
        ส่งการแจ้งเตือนเมื่อมีความเสี่ยง
        """
        if not config.risk.alert_enabled:
            return
        
        warnings = self.monitor_risk_limits()
        
        for warning in warnings:
            if warning not in self.alerts:
                logger.warning(warning)
                self.alerts.append(warning)
        
        # ล้างการแจ้งเตือนที่หมดอายุ
        self.alerts = [alert for alert in self.alerts if alert in warnings]
    
    def get_position_by_ticket(self, ticket: int) -> Dict:
        """
        ค้นหา position จาก ticket number
        
        Args:
            ticket: ticket number
            
        Returns:
            position dict หรือ None
        """
        for pos in self.positions:
            if pos['ticket'] == ticket:
                return pos
        return None
    
    def get_positions_summary(self) -> Dict:
        """
        สรุปข้อมูล positions ทั้งหมด
        
        Returns:
            Dict ที่มีข้อมูลสรุป
        """
        grid_exposure = self.get_net_grid_exposure()
        margin_info = self.check_margin_usage()
        
        return {
            'total_positions': len(self.positions),
            'grid_positions': len(self.grid_positions),
            'hg_positions': len(self.hg_positions),
            'total_pnl': self.total_pnl,
            'grid_pnl': self.calculate_grid_pnl(),
            'hg_pnl': self.calculate_hg_pnl(),
            'grid_buy_volume': grid_exposure['buy_volume'],
            'grid_sell_volume': grid_exposure['sell_volume'],
            'grid_net_volume': grid_exposure['net_volume'],
            'margin_usage': margin_info['margin_percent'],
            'warnings': self.monitor_risk_limits()
        }
    
    def close_positions_by_comment(self, comment: str) -> int:
        """
        ปิด positions ที่มี comment ตรงกัน
        
        Args:
            comment: comment ที่ต้องการค้นหา
            
        Returns:
            จำนวน positions ที่ปิด
        """
        closed = 0
        for pos in self.positions:
            if comment in pos['comment']:
                if mt5_connection.close_order(pos['ticket']):
                    closed += 1
        return closed
    
    def close_all_grid_positions(self) -> int:
        """
        ปิด Grid positions ทั้งหมด
        
        Returns:
            จำนวน positions ที่ปิด
        """
        return self.close_positions_by_comment(config.mt5.comment_grid)
    
    def close_all_hg_positions(self) -> int:
        """
        ปิด HG positions ทั้งหมด
        
        Returns:
            จำนวน positions ที่ปิด
        """
        return self.close_positions_by_comment(config.mt5.comment_hg)


# สร้าง instance หลักสำหรับใช้งาน
position_monitor = PositionMonitor()

