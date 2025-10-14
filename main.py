# main.py
# ไฟล์หลักสำหรับรันโปรแกรม Grid Trading System with HG

"""
Grid Trading System with Hedge (HG) for XAUUSD
===============================================

ระบบเทรด Grid แบบอัตโนมัติพร้อม Hedge (HG) สำหรับ XAUUSD
เชื่อมต่อกับ MetaTrader 5 สำหรับการเทรดบน DEMO account

Features:
- Grid Trading System (ระยะห่างปรับได้)
- Hedge (HG) System (คำนวณ lot อัตโนมัติ)
- Real-time Position Monitoring
- Risk Management
- GUI Interface

Author: Grid Trading Bot
Version: 1.0
"""

import sys
import logging
from gui import run_gui

# ตั้งค่า logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def main():
    """
    ฟังก์ชันหลักของโปรแกรม
    """
    try:
        logger.info("=" * 60)
        logger.info("Grid Trading System with HG - Starting...")
        logger.info("=" * 60)
        logger.info("Symbol: XAUUSD")
        logger.info("Mode: DEMO Trading")
        logger.info("=" * 60)
        
        # รัน GUI
        run_gui()
        
    except KeyboardInterrupt:
        logger.info("\n" + "=" * 60)
        logger.info("Program interrupted by user")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    
    finally:
        logger.info("=" * 60)
        logger.info("Grid Trading System - Shutdown")
        logger.info("=" * 60)


if __name__ == "__main__":
    main()

