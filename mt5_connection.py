# mt5_connection.py
# ไฟล์จัดการการเชื่อมต่อและคำสั่งซื้อขายกับ MetaTrader 5

import MetaTrader5 as mt5
from typing import Optional, Dict, List
import logging
from datetime import datetime
from config import config

# ตั้งค่า logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MT5Connection:
    """คลาสจัดการการเชื่อมต่อและคำสั่งกับ MT5"""
    
    def __init__(self):
        self.connected = False
        self.symbol = config.mt5.symbol
        self.magic_number = config.mt5.magic_number
        self.deviation = config.mt5.deviation
        
    def connect_to_mt5(self, login: Optional[int] = None, 
                      password: Optional[str] = None, 
                      server: Optional[str] = None) -> bool:
        """
        เชื่อมต่อกับ MetaTrader 5
        
        Args:
            login: หมายเลข account (ถ้าไม่ระบุจะใช้ account ที่เปิดอยู่)
            password: รหัสผ่าน
            server: ชื่อ server
            
        Returns:
            True ถ้าเชื่อมต่อสำเร็จ
        """
        try:
            # เริ่มต้น MT5
            if not mt5.initialize():
                logger.error(f"MT5 initialize failed: {mt5.last_error()}")
                return False
            
            # Login ถ้ามีการระบุข้อมูล
            if login and password and server:
                if not mt5.login(login, password, server):
                    logger.error(f"MT5 login failed: {mt5.last_error()}")
                    return False
            
            # ตรวจสอบว่า symbol มีอยู่
            symbol_info = mt5.symbol_info(self.symbol)
            if symbol_info is None:
                logger.error(f"Symbol {self.symbol} not found")
                return False
            
            # เปิด symbol สำหรับการเทรด
            if not symbol_info.visible:
                if not mt5.symbol_select(self.symbol, True):
                    logger.error(f"Failed to select {self.symbol}")
                    return False
            
            self.connected = True
            account_info = mt5.account_info()
            logger.info(f"Connected to MT5 - Account: {account_info.login}, Balance: ${account_info.balance}")
            return True
            
        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False
    
    def disconnect(self):
        """ตัดการเชื่อมต่อกับ MT5"""
        mt5.shutdown()
        self.connected = False
        logger.info("Disconnected from MT5")
    
    def get_current_price(self) -> Optional[Dict[str, float]]:
        """
        ดึงราคาปัจจุบันของ XAUUSD
        
        Returns:
            Dict ที่มี bid และ ask price หรือ None ถ้าเกิดข้อผิดพลาด
        """
        try:
            tick = mt5.symbol_info_tick(self.symbol)
            if tick is None:
                return None
            
            return {
                'bid': tick.bid,
                'ask': tick.ask,
                'time': datetime.fromtimestamp(tick.time)
            }
        except Exception as e:
            logger.error(f"Error getting price: {e}")
            return None
    
    def place_order(self, order_type: str, volume: float, 
                   price: Optional[float] = None,
                   sl: Optional[float] = None, 
                   tp: Optional[float] = None,
                   comment: str = "") -> Optional[int]:
        """
        วางคำสั่ง Buy/Sell order
        
        Args:
            order_type: "buy" หรือ "sell"
            volume: ขนาด lot
            price: ราคาที่ต้องการ (None = market price)
            sl: Stop Loss ราคา
            tp: Take Profit ราคา
            comment: คอมเมนต์
            
        Returns:
            ticket number ถ้าสำเร็จ หรือ None ถ้าล้มเหลว
        """
        try:
            symbol_info = mt5.symbol_info(self.symbol)
            if symbol_info is None:
                logger.error(f"Symbol {self.symbol} not found")
                return None
            
            # กำหนดประเภทคำสั่ง
            if order_type.lower() == "buy":
                trade_type = mt5.ORDER_TYPE_BUY
                if price is None:
                    price = mt5.symbol_info_tick(self.symbol).ask
            else:  # sell
                trade_type = mt5.ORDER_TYPE_SELL
                if price is None:
                    price = mt5.symbol_info_tick(self.symbol).bid
            
            # ปรับ volume ให้ถูกต้องตาม step
            volume = round(volume / symbol_info.volume_step) * symbol_info.volume_step
            
            # สร้าง request
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": volume,
                "type": trade_type,
                "price": price,
                "deviation": self.deviation,
                "magic": self.magic_number,
                "comment": comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            # เพิ่ม SL/TP ถ้ามี
            if sl is not None:
                request["sl"] = sl
            if tp is not None:
                request["tp"] = tp
            
            # ส่งคำสั่ง
            result = mt5.order_send(request)
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                logger.error(f"Order failed: {result.retcode} - {result.comment}")
                return None
            
            logger.info(f"Order placed: {order_type.upper()} {volume} lots at {price} | Ticket: {result.order}")
            return result.order
            
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return None
    
    def modify_order(self, ticket: int, sl: Optional[float] = None, 
                    tp: Optional[float] = None) -> bool:
        """
        แก้ไข SL/TP ของ position
        
        Args:
            ticket: ticket number
            sl: Stop Loss ราคาใหม่
            tp: Take Profit ราคาใหม่
            
        Returns:
            True ถ้าสำเร็จ
        """
        try:
            # ดึงข้อมูล position
            position = mt5.positions_get(ticket=ticket)
            if not position:
                logger.error(f"Position {ticket} not found")
                return False
            
            position = position[0]
            
            # สร้าง request
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "symbol": self.symbol,
                "position": ticket,
                "sl": sl if sl is not None else position.sl,
                "tp": tp if tp is not None else position.tp,
            }
            
            result = mt5.order_send(request)
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                logger.error(f"Modify failed: {result.retcode} - {result.comment}")
                return False
            
            logger.info(f"Position {ticket} modified - SL: {sl}, TP: {tp}")
            return True
            
        except Exception as e:
            logger.error(f"Error modifying order: {e}")
            return False
    
    def close_order(self, ticket: int) -> bool:
        """
        ปิด position
        
        Args:
            ticket: ticket number
            
        Returns:
            True ถ้าสำเร็จ
        """
        try:
            # ดึงข้อมูล position
            position = mt5.positions_get(ticket=ticket)
            if not position:
                logger.error(f"Position {ticket} not found")
                return False
            
            position = position[0]
            
            # กำหนดประเภทการปิด (ตรงข้ามกับการเปิด)
            if position.type == mt5.ORDER_TYPE_BUY:
                trade_type = mt5.ORDER_TYPE_SELL
                price = mt5.symbol_info_tick(self.symbol).bid
            else:
                trade_type = mt5.ORDER_TYPE_BUY
                price = mt5.symbol_info_tick(self.symbol).ask
            
            # สร้าง request
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": position.volume,
                "type": trade_type,
                "position": ticket,
                "price": price,
                "deviation": self.deviation,
                "magic": self.magic_number,
                "comment": f"Close {position.comment}",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            result = mt5.order_send(request)
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                logger.error(f"Close failed: {result.retcode} - {result.comment}")
                return False
            
            logger.info(f"Position {ticket} closed - Profit: ${position.profit}")
            return True
            
        except Exception as e:
            logger.error(f"Error closing order: {e}")
            return False
    
    def get_all_positions(self) -> List[Dict]:
        """
        ดึงข้อมูล positions ทั้งหมดที่เปิดอยู่
        
        Returns:
            List ของ position dictionaries
        """
        try:
            positions = mt5.positions_get(symbol=self.symbol)
            if positions is None:
                return []
            
            result = []
            for pos in positions:
                # กรองเฉพาะ positions ของ bot นี้
                if pos.magic == self.magic_number:
                    result.append({
                        'ticket': pos.ticket,
                        'type': 'buy' if pos.type == mt5.ORDER_TYPE_BUY else 'sell',
                        'volume': pos.volume,
                        'open_price': pos.price_open,
                        'current_price': pos.price_current,
                        'sl': pos.sl,
                        'tp': pos.tp,
                        'profit': pos.profit,
                        'comment': pos.comment,
                        'open_time': datetime.fromtimestamp(pos.time)
                    })
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []
    
    def get_account_info(self) -> Optional[Dict]:
        """
        ดึงข้อมูล account
        
        Returns:
            Dict ที่มีข้อมูล account
        """
        try:
            account = mt5.account_info()
            if account is None:
                return None
            
            return {
                'balance': account.balance,
                'equity': account.equity,
                'margin': account.margin,
                'free_margin': account.margin_free,
                'margin_level': account.margin_level if account.margin > 0 else 0,
                'profit': account.profit
            }
            
        except Exception as e:
            logger.error(f"Error getting account info: {e}")
            return None
    
    def close_all_positions(self) -> int:
        """
        ปิด positions ทั้งหมด (Emergency Stop)
        
        Returns:
            จำนวน positions ที่ปิดสำเร็จ
        """
        positions = self.get_all_positions()
        closed_count = 0
        
        for pos in positions:
            if self.close_order(pos['ticket']):
                closed_count += 1
        
        logger.info(f"Emergency Stop: Closed {closed_count} positions")
        return closed_count


# สร้าง instance หลักสำหรับใช้งาน
mt5_connection = MT5Connection()

