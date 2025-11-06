# gui.py
# ไฟล์สร้าง GUI Interface ด้วย tkinter

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import logging
from datetime import datetime, timezone

import requests
from mt5_connection import mt5_connection
from grid_manager import grid_manager
from hg_manager import HGManager
from position_monitor import position_monitor
from config import config
from risk_calculator import risk_calculator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TradingGUI:
    """คลาสหลักสำหรับ GUI Interface"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Grid Trading System with HG - XAUUSD")
        self.root.geometry("1200x700")  # 🆕 ปรับขนาดให้พอดีและสมดุล
        self.root.minsize(1000, 600)  # 🆕 กำหนดขนาดขั้นต่ำ
        self.root.maxsize(1400, 900)  # 🆕 กำหนดขนาดสูงสุด (ป้องกันเกินหน้าจอ)
        
        self.api_base_url ="http://123.253.62.50:8080/api"

        # สถานะระบบ
        self.is_running = False
        self.monitoring_thread = None
        self.stop_monitoring = False
        
        # สร้าง HG Manager
        self.hg_manager = HGManager()
        
        # 🆕 Auto Mode: ตัวนับสำหรับ refresh (ทุก 60 วินาที = 120 cycles)
        self.auto_refresh_counter = 0
        self.auto_refresh_interval = 120  # รอบ (120 * 0.5s = 60 วินาที)
        
        # 🆕 Performance: Throttling สำหรับ GUI updates
        self.last_display_update = 0
        self.display_update_interval = 1.0  # อัพเดท GUI ทุก 1 วินาที (ไม่ใช่ทุก 0.5 วินาที)
        
        # สร้าง GUI components
        self.create_widgets()
        
        # โหลดการตั้งค่า
        self.load_settings_to_gui()
        
        # โหลดรายการบัญชี
        self.refresh_accounts()
    
    def create_widgets(self):
        """สร้าง GUI components ทั้งหมด"""
        
        # ============ Notebook (Tabs) ============
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # สร้าง tabs
        self.trading_tab = ttk.Frame(self.notebook)
        self.risk_tab = ttk.Frame(self.notebook)
        
        self.notebook.add(self.trading_tab, text="  📊 Trading  ")
        self.notebook.add(self.risk_tab, text="  🛡️ Risk Calculator  ")
        
        # สร้าง content ใน tabs
        self.create_trading_tab()
        self.create_risk_calculator_tab()
    
    def create_trading_tab(self):
        """สร้าง content สำหรับ Trading Tab"""
        
        # ============ Frame หลัก (ลด padding) ============
        main_frame = ttk.Frame(self.trading_tab, padding="8")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # ============ Mode Selection (ลด padding) ============
        mode_frame = ttk.LabelFrame(main_frame, text="🎮 Trading Mode", padding="8")
        mode_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=3)
        
        self.auto_mode_var = tk.BooleanVar(value=False)
        ttk.Radiobutton(mode_frame, text="📝 Manual Mode", 
                       variable=self.auto_mode_var, value=False,
                       command=self.toggle_mode).pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(mode_frame, text="🤖 Full Auto Mode", 
                       variable=self.auto_mode_var, value=True,
                       command=self.toggle_mode).pack(side=tk.LEFT, padx=10)
        
        # ============ Connection Status (ลด padding) ============
        status_frame = ttk.LabelFrame(main_frame, text="📡 Connection & Account Info", padding="8")
        status_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=3)
        
        # Row 0: Account Selection
        ttk.Label(status_frame, text="Select Account:").grid(row=0, column=0, sticky=tk.W)
        self.account_var = tk.StringVar(value="Auto")
        self.account_combo = ttk.Combobox(status_frame, textvariable=self.account_var, 
                                         width=20, state="readonly")
        self.account_combo.grid(row=0, column=1, sticky=tk.W, padx=5)
        
        ttk.Button(status_frame, text="Refresh Accounts", 
                  command=self.refresh_accounts).grid(row=0, column=2, padx=5)
        
        # Row 1: Connection Status
        self.connection_status = tk.StringVar(value="Disconnected")
        self.connection_color = tk.StringVar(value="red")
        
        ttk.Label(status_frame, text="Status:").grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
        self.status_label = ttk.Label(status_frame, textvariable=self.connection_status, 
                                foreground="red", font=("Arial", 10, "bold"))
        self.status_label.grid(row=1, column=1, sticky=tk.W, padx=5, pady=(5, 0))
        
        ttk.Button(status_frame, text="Connect MT5", 
                  command=self.connect_mt5).grid(row=1, column=2, padx=5, pady=(5, 0))
        ttk.Button(status_frame, text="Disconnect", 
                  command=self.disconnect_mt5).grid(row=1, column=3, padx=5, pady=(5, 0))
        
        # Row 2: Account Info
        ttk.Label(status_frame, text="Account:").grid(row=2, column=0, sticky=tk.W, pady=(5, 0))
        self.account_number_var = tk.StringVar(value="-")
        ttk.Label(status_frame, textvariable=self.account_number_var, 
                 font=("Arial", 9)).grid(row=2, column=1, sticky=tk.W, padx=5, pady=(5, 0))
        
        ttk.Label(status_frame, text="Balance:").grid(row=2, column=2, sticky=tk.W, pady=(5, 0))
        self.balance_var = tk.StringVar(value="-")
        ttk.Label(status_frame, textvariable=self.balance_var, 
                 font=("Arial", 9, "bold")).grid(row=2, column=3, sticky=tk.W, padx=5, pady=(5, 0))
        
        # Row 3: Broker & Symbol
        ttk.Label(status_frame, text="Broker:").grid(row=3, column=0, sticky=tk.W, pady=(2, 0))
        self.broker_var = tk.StringVar(value="-")
        ttk.Label(status_frame, textvariable=self.broker_var, 
                 font=("Arial", 9)).grid(row=3, column=1, sticky=tk.W, padx=5, pady=(2, 0))
        
        ttk.Label(status_frame, text="Symbol:").grid(row=3, column=2, sticky=tk.W, pady=(2, 0))
        self.symbol_var = tk.StringVar(value="-")
        ttk.Label(status_frame, textvariable=self.symbol_var, 
                 font=("Arial", 9, "bold"), foreground="blue").grid(row=3, column=3, sticky=tk.W, padx=5, pady=(2, 0))

        ttk.Label(status_frame, text="Expiry date:").grid(row=3, column=5, sticky=tk.W, pady=(2, 0))
        self.expiry_date_var = tk.StringVar(value="-")
        # Format expiry date to show only date part
        def format_expiry_date(*args):
            value = self.expiry_date_var.get()
            if value and len(value) >= 10:
                self.expiry_date_label.config(text=value[:10])
            else:
                self.expiry_date_label.config(text="-")

        self.expiry_date_label = ttk.Label(
            status_frame,
            font=("Arial", 9, "bold"),
            foreground="blue"
        )
        self.expiry_date_label.grid(row=3, column=7, sticky=tk.W, padx=5, pady=(2, 0))
        self.expiry_date_var.trace_add("write", format_expiry_date)

        # ============ Controls (ย้ายขึ้นมาก่อน Auto Display) ============
        control_frame = ttk.LabelFrame(main_frame, text="🎮 Controls", padding="8")
        control_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=3)
        
        self.start_button = ttk.Button(control_frame, text="▶ Start Trading", 
                                       command=self.start_trading, style="Start.TButton")
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(control_frame, text="⏸ Stop Trading", 
                                      command=self.stop_trading, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(control_frame, text="🛑 Emergency Stop", 
                  command=self.emergency_stop, style="Emergency.TButton").pack(side=tk.LEFT, padx=5)
        
        ttk.Button(control_frame, text="💾 Save Settings", 
                  command=self.save_settings).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(control_frame, text="🔄 Refresh", 
                  command=self.refresh_status).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(control_frame, text="🧪 Test Price", 
                  command=self.test_price_connection).pack(side=tk.LEFT, padx=5)
        
        # ============ Auto Mode Display (ลด padding และย้ายลงมา) ============
        self.auto_display_frame = ttk.LabelFrame(main_frame, text="🤖 Auto Mode Status", padding="8")
        self.auto_display_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=3)
        self.auto_display_frame.grid_remove()  # ซ่อนไว้ก่อน
        
        self.create_auto_mode_ui()
        
        # ============ Grid Settings ============
        self.grid_frame = ttk.LabelFrame(main_frame, text="📊 Grid Settings (แยก Buy/Sell)", padding="8")
        self.grid_frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N), pady=3, padx=(0, 5))
        
        # Direction
        ttk.Label(self.grid_frame, text="Direction:").grid(row=0, column=0, sticky=tk.W, pady=3)
        self.direction_var = tk.StringVar(value="both")
        direction_frame = ttk.Frame(self.grid_frame)
        direction_frame.grid(row=0, column=1, columnspan=3, sticky=tk.W, pady=3)
        ttk.Radiobutton(direction_frame, text="Buy Only", variable=self.direction_var, 
                       value="buy").pack(side=tk.LEFT)
        ttk.Radiobutton(direction_frame, text="Sell Only", variable=self.direction_var, 
                       value="sell").pack(side=tk.LEFT)
        ttk.Radiobutton(direction_frame, text="Both", variable=self.direction_var, 
                       value="both").pack(side=tk.LEFT)
        
        # Headers
        ttk.Label(self.grid_frame, text="", width=18).grid(row=1, column=0, pady=3)
        ttk.Label(self.grid_frame, text="🟢 BUY", font=("Arial", 9, "bold"), 
                 foreground="green").grid(row=1, column=1, pady=3)
        ttk.Label(self.grid_frame, text="🔴 SELL", font=("Arial", 9, "bold"),
                 foreground="red").grid(row=1, column=2, pady=3)
        
        # Grid Distance
        ttk.Label(self.grid_frame, text="Grid Distance (pips):").grid(row=2, column=0, sticky=tk.W, pady=3)
        self.buy_grid_distance_var = tk.IntVar(value=50)
        ttk.Entry(self.grid_frame, textvariable=self.buy_grid_distance_var, width=12).grid(row=2, column=1, pady=3, padx=2)
        self.sell_grid_distance_var = tk.IntVar(value=50)
        ttk.Entry(self.grid_frame, textvariable=self.sell_grid_distance_var, width=12).grid(row=2, column=2, pady=3, padx=2)
        
        # Lot Size
        ttk.Label(self.grid_frame, text="Lot Size:").grid(row=3, column=0, sticky=tk.W, pady=3)
        self.buy_lot_size_var = tk.DoubleVar(value=0.01)
        ttk.Entry(self.grid_frame, textvariable=self.buy_lot_size_var, width=12).grid(row=3, column=1, pady=3, padx=2)
        self.sell_lot_size_var = tk.DoubleVar(value=0.01)
        ttk.Entry(self.grid_frame, textvariable=self.sell_lot_size_var, width=12).grid(row=3, column=2, pady=3, padx=2)
        
        # Take Profit
        ttk.Label(self.grid_frame, text="Take Profit (pips):").grid(row=4, column=0, sticky=tk.W, pady=3)
        self.buy_tp_var = tk.IntVar(value=50)
        ttk.Entry(self.grid_frame, textvariable=self.buy_tp_var, width=12).grid(row=4, column=1, pady=3, padx=2)
        self.sell_tp_var = tk.IntVar(value=50)
        ttk.Entry(self.grid_frame, textvariable=self.sell_tp_var, width=12).grid(row=4, column=2, pady=3, padx=2)
        
        # ============ HG Settings ============
        self.hg_frame = ttk.LabelFrame(main_frame, text="🛡️ HG Settings (แยก Buy/Sell)", padding="8")
        self.hg_frame.grid(row=3, column=1, sticky=(tk.W, tk.E, tk.N), pady=3)
        
        # HG Enable/Disable
        self.hg_enabled_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.hg_frame, text="Enable HG System", 
                       variable=self.hg_enabled_var).grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=3)
        
        # HG Direction
        ttk.Label(self.hg_frame, text="HG Direction:").grid(row=1, column=0, sticky=tk.W, pady=3)
        self.hg_direction_var = tk.StringVar(value="buy")
        hg_direction_frame = ttk.Frame(self.hg_frame)
        hg_direction_frame.grid(row=1, column=1, columnspan=2, sticky=tk.W, pady=3)
        ttk.Radiobutton(hg_direction_frame, text="Buy Only", variable=self.hg_direction_var, 
                       value="buy").pack(side=tk.LEFT)
        ttk.Radiobutton(hg_direction_frame, text="Sell Only", variable=self.hg_direction_var, 
                       value="sell").pack(side=tk.LEFT)
        ttk.Radiobutton(hg_direction_frame, text="Both", variable=self.hg_direction_var, 
                       value="both").pack(side=tk.LEFT)
        
        
        # Headers
        ttk.Label(self.hg_frame, text="", width=18).grid(row=2, column=0, pady=3)
        ttk.Label(self.hg_frame, text="🟢 BUY", font=("Arial", 9, "bold"), 
                 foreground="green").grid(row=2, column=1, pady=3)
        ttk.Label(self.hg_frame, text="🔴 SELL", font=("Arial", 9, "bold"),
                 foreground="red").grid(row=2, column=2, pady=3)
        
        # HG Distance
        ttk.Label(self.hg_frame, text="HG Distance (pips):").grid(row=3, column=0, sticky=tk.W, pady=3)
        self.buy_hg_distance_var = tk.IntVar(value=200)
        ttk.Entry(self.hg_frame, textvariable=self.buy_hg_distance_var, width=12).grid(row=3, column=1, pady=3, padx=2)
        self.sell_hg_distance_var = tk.IntVar(value=2000)
        ttk.Entry(self.hg_frame, textvariable=self.sell_hg_distance_var, width=12).grid(row=3, column=2, pady=3, padx=2)
        
        # HG SL Trigger
        ttk.Label(self.hg_frame, text="HG SL Trigger (pips):").grid(row=4, column=0, sticky=tk.W, pady=3)
        self.buy_hg_sl_trigger_var = tk.IntVar(value=100)
        ttk.Entry(self.hg_frame, textvariable=self.buy_hg_sl_trigger_var, width=12).grid(row=4, column=1, pady=3, padx=2)
        self.sell_hg_sl_trigger_var = tk.IntVar(value=1000)
        ttk.Entry(self.hg_frame, textvariable=self.sell_hg_sl_trigger_var, width=12).grid(row=4, column=2, pady=3, padx=2)
        
        # HG Multiplier
        ttk.Label(self.hg_frame, text="HG Multiplier:").grid(row=5, column=0, sticky=tk.W, pady=3)
        self.buy_hg_multiplier_var = tk.DoubleVar(value=1.2)
        ttk.Entry(self.hg_frame, textvariable=self.buy_hg_multiplier_var, width=12).grid(row=5, column=1, pady=3, padx=2)
        self.sell_hg_multiplier_var = tk.DoubleVar(value=1.2)
        ttk.Entry(self.hg_frame, textvariable=self.sell_hg_multiplier_var, width=12).grid(row=5, column=2, pady=3, padx=2)
        
        # HG Initial Lot
        ttk.Label(self.hg_frame, text="HG Initial Lot:").grid(row=6, column=0, sticky=tk.W, pady=3)
        self.buy_hg_initial_lot_var = tk.DoubleVar(value=0.01)
        ttk.Entry(self.hg_frame, textvariable=self.buy_hg_initial_lot_var, width=12).grid(row=6, column=1, pady=3, padx=2)
        self.sell_hg_initial_lot_var = tk.DoubleVar(value=0.01)
        ttk.Entry(self.hg_frame, textvariable=self.sell_hg_initial_lot_var, width=12).grid(row=6, column=2, pady=3, padx=2)
        
        # SL Buffer
        ttk.Label(self.hg_frame, text="SL Buffer (pips):").grid(row=7, column=0, sticky=tk.W, pady=3)
        self.buy_sl_buffer_var = tk.IntVar(value=10)
        ttk.Entry(self.hg_frame, textvariable=self.buy_sl_buffer_var, width=12).grid(row=7, column=1, pady=3, padx=2)
        self.sell_sl_buffer_var = tk.IntVar(value=20)
        ttk.Entry(self.hg_frame, textvariable=self.sell_sl_buffer_var, width=12).grid(row=7, column=2, pady=3, padx=2)
        
        # Max HG Levels
        ttk.Label(self.hg_frame, text="Max HG Levels:").grid(row=8, column=0, sticky=tk.W, pady=3)
        self.buy_max_hg_levels_var = tk.IntVar(value=10)
        ttk.Entry(self.hg_frame, textvariable=self.buy_max_hg_levels_var, width=12).grid(row=8, column=1, pady=3, padx=2)
        self.sell_max_hg_levels_var = tk.IntVar(value=10)
        ttk.Entry(self.hg_frame, textvariable=self.sell_max_hg_levels_var, width=12).grid(row=8, column=2, pady=3, padx=2)
        
        # ============ Status Display (ลด padding และปรับ row) ============
        status_display_frame = ttk.LabelFrame(main_frame, text="📈 Status Display", padding="8")
        status_display_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=3)  # 🆕 ลบ expand=True
        
        # สร้าง grid สำหรับแสดงข้อมูล
        info_frame = ttk.Frame(status_display_frame)
        info_frame.pack(fill=tk.BOTH, expand=True)
        
        # Column 1
        col1 = ttk.Frame(info_frame)
        col1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        ttk.Label(col1, text="Active Grid Levels:", font=("Arial", 9, "bold")).pack(anchor=tk.W)
        self.grid_levels_var = tk.StringVar(value="0 levels")
        ttk.Label(col1, textvariable=self.grid_levels_var, foreground="blue").pack(anchor=tk.W)
        
        ttk.Label(col1, text="Active HG Positions:", font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(10, 0))
        self.hg_positions_var = tk.StringVar(value="0 positions")
        ttk.Label(col1, textvariable=self.hg_positions_var, foreground="green").pack(anchor=tk.W)
        
        ttk.Label(col1, text="Grid Exposure:", font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(10, 0))
        self.grid_exposure_var = tk.StringVar(value="0.00 lots")
        ttk.Label(col1, textvariable=self.grid_exposure_var).pack(anchor=tk.W)
        
        # Column 2
        col2 = ttk.Frame(info_frame)
        col2.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        ttk.Label(col2, text="Total P&L:", font=("Arial", 9, "bold")).pack(anchor=tk.W)
        self.total_pnl_var = tk.StringVar(value="$0.00")
        self.pnl_label = ttk.Label(col2, textvariable=self.total_pnl_var, 
                                   font=("Arial", 11, "bold"), foreground="black")
        self.pnl_label.pack(anchor=tk.W)
        
        ttk.Label(col2, text="Margin Used:", font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(10, 0))
        self.margin_var = tk.StringVar(value="0%")
        ttk.Label(col2, textvariable=self.margin_var, foreground="orange").pack(anchor=tk.W)
        
        ttk.Label(col2, text="Current Price:", font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(10, 0))
        self.price_var = tk.StringVar(value="0.00")
        ttk.Label(col2, textvariable=self.price_var).pack(anchor=tk.W)
        
        # ============ Log Display (ลด padding และปรับ row) ============
        log_frame = ttk.LabelFrame(main_frame, text="📝 Activity Log", padding="8")
        log_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=3)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=8, width=80,  # 🆕 ลด height จาก 10 เป็น 8
                                                  wrap=tk.WORD, font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # ตั้งค่า grid weights สำหรับ responsive (ปรับให้ Controls ไม่ถูกผลัก)
        self.trading_tab.columnconfigure(0, weight=1)
        self.trading_tab.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)  # 🆕 Auto Display Frame (row=3) ขยายได้
        main_frame.rowconfigure(5, weight=1)  # 🆕 Log Display (row=5) ขยายได้
        # 🆕 Controls (row=2) และ Status Display (row=4) ไม่ขยาย (ไม่ใช้ weight)
        
        # สไตล์ปุ่ม
        style = ttk.Style()
        style.configure("Start.TButton", foreground="green")
        style.configure("Emergency.TButton", foreground="red")
    
    def create_auto_mode_ui(self):
        """สร้าง UI สำหรับ Auto Mode"""
        # สร้าง 2 columns หลัก
        left_col = ttk.Frame(self.auto_display_frame)
        left_col.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        
        right_col = ttk.Frame(self.auto_display_frame)
        right_col.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0))
        
        # ===== LEFT COLUMN =====
        
        # Market Analysis (กระชับขึ้น)
        ttk.Label(left_col, text="📈 MARKET ANALYSIS", 
                 font=("Arial", 9, "bold")).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 3))
        
        # Direction
        ttk.Label(left_col, text="Direction:", font=("Arial", 8)).grid(row=1, column=0, sticky=tk.W, pady=1)
        self.auto_trend_var = tk.StringVar(value="-")
        self.auto_trend_label = ttk.Label(left_col, textvariable=self.auto_trend_var,
                                          font=("Arial", 8, "bold"), foreground="blue")
        self.auto_trend_label.grid(row=1, column=1, sticky=tk.W, padx=5, pady=1)
        
        # ATR
        ttk.Label(left_col, text="ATR(14):", font=("Arial", 8)).grid(row=2, column=0, sticky=tk.W, pady=1)
        self.auto_atr_var = tk.StringVar(value="-")
        ttk.Label(left_col, textvariable=self.auto_atr_var, font=("Arial", 8)).grid(row=2, column=1, sticky=tk.W, padx=5, pady=1)
        
        # Last Candle
        ttk.Label(left_col, text="Candle:", font=("Arial", 8)).grid(row=3, column=0, sticky=tk.W, pady=1)
        self.auto_candle_var = tk.StringVar(value="-")
        self.auto_candle_label = ttk.Label(left_col, textvariable=self.auto_candle_var, font=("Arial", 8, "bold"))
        self.auto_candle_label.grid(row=3, column=1, sticky=tk.W, padx=5, pady=1)
        
        # Volume Level
        ttk.Label(left_col, text="Volume:", font=("Arial", 8)).grid(row=4, column=0, sticky=tk.W, pady=1)
        self.auto_volume_var = tk.StringVar(value="-")
        self.auto_volume_label = ttk.Label(left_col, textvariable=self.auto_volume_var, font=("Arial", 8, "bold"))
        self.auto_volume_label.grid(row=4, column=1, sticky=tk.W, padx=5, pady=1)
        
        # Candle Size
        ttk.Label(left_col, text="Size:", font=("Arial", 8)).grid(row=5, column=0, sticky=tk.W, pady=1)
        self.auto_candle_pips_var = tk.StringVar(value="-")
        ttk.Label(left_col, textvariable=self.auto_candle_pips_var, font=("Arial", 8)).grid(row=5, column=1, sticky=tk.W, padx=5, pady=1)
        
        # Volume Ratio
        ttk.Label(left_col, text="Vol Ratio:", font=("Arial", 8)).grid(row=6, column=0, sticky=tk.W, pady=1)
        self.auto_volume_ratio_var = tk.StringVar(value="-")
        ttk.Label(left_col, textvariable=self.auto_volume_ratio_var, font=("Arial", 8)).grid(row=6, column=1, sticky=tk.W, padx=5, pady=1)
        
        # Last Update
        ttk.Label(left_col, text="Updated:", font=("Arial", 8)).grid(row=7, column=0, sticky=tk.W, pady=1)
        self.auto_update_time_var = tk.StringVar(value="-")
        ttk.Label(left_col, textvariable=self.auto_update_time_var,
                 foreground="gray", font=("Arial", 7)).grid(row=7, column=1, sticky=tk.W, padx=5, pady=1)
        
        # Separator
        ttk.Separator(left_col, orient='horizontal').grid(row=8, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=8)
        
        # Auto Calculated Settings (กระชับขึ้น)
        ttk.Label(left_col, text="⚙️ AUTO SETTINGS", 
                 font=("Arial", 9, "bold")).grid(row=9, column=0, columnspan=2, sticky=tk.W, pady=(0, 3))
        
        # Grid Distance
        ttk.Label(left_col, text="Grid:", font=("Arial", 8)).grid(row=10, column=0, sticky=tk.W, pady=1)
        self.auto_grid_dist_var = tk.StringVar(value="-")
        ttk.Label(left_col, textvariable=self.auto_grid_dist_var,
                 font=("Arial", 8, "bold"), foreground="green").grid(row=10, column=1, sticky=tk.W, padx=5, pady=1)
        
        # HG Distance
        ttk.Label(left_col, text="HG:", font=("Arial", 8)).grid(row=11, column=0, sticky=tk.W, pady=1)
        self.auto_hg_dist_var = tk.StringVar(value="-")
        ttk.Label(left_col, textvariable=self.auto_hg_dist_var,
                 font=("Arial", 8, "bold"), foreground="orange").grid(row=11, column=1, sticky=tk.W, padx=5, pady=1)
        
        # Active Direction (ย้ายขึ้นมาใกล้ Market Analysis)
        ttk.Label(left_col, text="Active:", font=("Arial", 8)).grid(row=12, column=0, sticky=tk.W, pady=1)
        self.auto_direction_var = tk.StringVar(value="-")
        ttk.Label(left_col, textvariable=self.auto_direction_var,
                 font=("Arial", 8, "bold"), foreground="blue").grid(row=12, column=1, sticky=tk.W, padx=5, pady=1)
        
        # Separator
        ttk.Separator(left_col, orient='horizontal').grid(row=13, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=8)
        
        # Risk Profile Selection (กระชับขึ้น)
        ttk.Label(left_col, text="🛡️ RISK PROFILE", 
                 font=("Arial", 9, "bold")).grid(row=14, column=0, columnspan=2, sticky=tk.W, pady=(0, 3))
        
        self.risk_profile_var = tk.StringVar(value="moderate")
        
        ttk.Radiobutton(left_col, text="Very Conservative", 
                       variable=self.risk_profile_var, value="very_conservative").grid(row=15, column=0, columnspan=2, sticky=tk.W, pady=1)
        ttk.Radiobutton(left_col, text="Conservative", 
                       variable=self.risk_profile_var, value="conservative").grid(row=16, column=0, columnspan=2, sticky=tk.W, pady=1)
        ttk.Radiobutton(left_col, text="Moderate ⭐", 
                       variable=self.risk_profile_var, value="moderate").grid(row=17, column=0, columnspan=2, sticky=tk.W, pady=1)
        ttk.Radiobutton(left_col, text="Aggressive", 
                       variable=self.risk_profile_var, value="aggressive").grid(row=18, column=0, columnspan=2, sticky=tk.W, pady=1)
        ttk.Radiobutton(left_col, text="Very Aggressive", 
                       variable=self.risk_profile_var, value="very_aggressive").grid(row=19, column=0, columnspan=2, sticky=tk.W, pady=1)
        
        # Refresh Button
        ttk.Button(left_col, text="🔄 Refresh Analysis", 
                  command=self.refresh_auto_analysis).grid(row=20, column=0, columnspan=2, pady=(8, 0), sticky=(tk.W, tk.E))
        
        # ===== RIGHT COLUMN =====
        
        # สร้าง Notebook สำหรับ Right Column (แบ่งเป็น 2 tabs)
        right_notebook = ttk.Notebook(right_col)
        right_notebook.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 5))
        
        # Tab 1: Survivability Analysis
        survival_tab = ttk.Frame(right_notebook)
        right_notebook.add(survival_tab, text="📊 Survivability")
        
        ttk.Label(survival_tab, text="📊 SURVIVABILITY ANALYSIS", 
                 font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(0, 5))
        
        self.survivability_text = scrolledtext.ScrolledText(survival_tab, height=10, width=50,  # 🆕 ลด height จาก 12 เป็น 10
                                                            wrap=tk.WORD, font=("Consolas", 8))
        self.survivability_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Tab 2: Trading Statistics
        stats_tab = ttk.Frame(right_notebook)
        right_notebook.add(stats_tab, text="📈 Statistics")
        
        # Statistics Section (ลด padding)
        stats_frame = ttk.LabelFrame(stats_tab, text="📊 Trading Statistics", padding="8")
        stats_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=3)
        
        # สร้าง grid สำหรับแสดงสถิติ
        stats_grid = ttk.Frame(stats_frame)
        stats_grid.pack(fill=tk.BOTH, expand=True)
        
        # Row 1: Total Orders (ลด padding)
        ttk.Label(stats_grid, text="Total Orders:", font=("Arial", 9)).grid(row=0, column=0, sticky=tk.W, padx=5, pady=3)
        self.total_orders_var = tk.StringVar(value="0")
        ttk.Label(stats_grid, textvariable=self.total_orders_var, 
                 font=("Arial", 9, "bold"), foreground="blue").grid(row=0, column=1, sticky=tk.W, padx=5, pady=3)
        
        # Row 2: Active Positions
        ttk.Label(stats_grid, text="Active Positions:", font=("Arial", 9)).grid(row=1, column=0, sticky=tk.W, padx=5, pady=3)
        self.active_positions_var = tk.StringVar(value="0")
        ttk.Label(stats_grid, textvariable=self.active_positions_var, 
                 font=("Arial", 9, "bold"), foreground="green").grid(row=1, column=1, sticky=tk.W, padx=5, pady=3)
        
        # Row 3: Total P&L
        ttk.Label(stats_grid, text="Total P&L:", font=("Arial", 9)).grid(row=2, column=0, sticky=tk.W, padx=5, pady=3)
        self.stats_pnl_var = tk.StringVar(value="$0.00")
        self.stats_pnl_label = ttk.Label(stats_grid, textvariable=self.stats_pnl_var, 
                                        font=("Arial", 10, "bold"), foreground="black")
        self.stats_pnl_label.grid(row=2, column=1, sticky=tk.W, padx=5, pady=3)
        
        # Row 4: Win Rate
        ttk.Label(stats_grid, text="Win Rate:", font=("Arial", 9)).grid(row=3, column=0, sticky=tk.W, padx=5, pady=3)
        self.win_rate_var = tk.StringVar(value="0.0%")
        ttk.Label(stats_grid, textvariable=self.win_rate_var, 
                 font=("Arial", 9, "bold"), foreground="green").grid(row=3, column=1, sticky=tk.W, padx=5, pady=3)
        
        # Row 5: Average Profit
        ttk.Label(stats_grid, text="Avg Profit:", font=("Arial", 9)).grid(row=4, column=0, sticky=tk.W, padx=5, pady=3)
        self.avg_profit_var = tk.StringVar(value="$0.00")
        ttk.Label(stats_grid, textvariable=self.avg_profit_var, 
                 font=("Arial", 9)).grid(row=4, column=1, sticky=tk.W, padx=5, pady=3)
        
        # Separator (ลด padding)
        ttk.Separator(stats_grid, orient='horizontal').grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Real-time Status Section (ลด padding)
        status_frame = ttk.LabelFrame(stats_tab, text="⚡ Real-time Status", padding="8")
        status_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=3)
        
        # Grid Status (ลด padding)
        ttk.Label(status_frame, text="Grid Status:", font=("Arial", 9)).pack(anchor=tk.W, pady=2)
        self.realtime_grid_var = tk.StringVar(value="Inactive")
        ttk.Label(status_frame, textvariable=self.realtime_grid_var, 
                 font=("Arial", 9, "bold"), foreground="gray").pack(anchor=tk.W, pady=2)
        
        # HG Status
        ttk.Label(status_frame, text="HG Status:", font=("Arial", 9)).pack(anchor=tk.W, pady=2)
        self.realtime_hg_var = tk.StringVar(value="Inactive")
        ttk.Label(status_frame, textvariable=self.realtime_hg_var, 
                 font=("Arial", 9, "bold"), foreground="gray").pack(anchor=tk.W, pady=2)
        
        # Current Price (Large Display - ลดขนาด font)
        ttk.Label(status_frame, text="Current Price:", font=("Arial", 9)).pack(anchor=tk.W, pady=(8, 2))
        self.realtime_price_var = tk.StringVar(value="0.00")
        price_label = ttk.Label(status_frame, textvariable=self.realtime_price_var, 
                               font=("Arial", 14, "bold"), foreground="blue")  # 🆕 ลดจาก 16 เป็น 14
        price_label.pack(anchor=tk.W, pady=2)
        
        # Margin Usage (Progress Bar Style - ลดขนาด)
        ttk.Label(status_frame, text="Margin Usage:", font=("Arial", 9)).pack(anchor=tk.W, pady=(8, 2))
        self.margin_progress_var = tk.DoubleVar(value=0.0)
        self.margin_progress = ttk.Progressbar(status_frame, variable=self.margin_progress_var, 
                                               maximum=100, length=180)  # 🆕 ลดจาก 200 เป็น 180
        self.margin_progress.pack(anchor=tk.W, pady=2)
        self.margin_progress_label = ttk.Label(status_frame, text="0.0%", 
                                               font=("Arial", 8))
        self.margin_progress_label.pack(anchor=tk.W, pady=1)
        
        # Configure column weights (ปรับให้สมดุลขึ้น)
        self.auto_display_frame.columnconfigure(0, weight=1, minsize=300)  # 🆕 กำหนดขนาดขั้นต่ำ
        self.auto_display_frame.columnconfigure(1, weight=1, minsize=400)  # 🆕 เปลี่ยนจาก 2 เป็น 1 (สมดุลขึ้น)
        self.auto_display_frame.rowconfigure(0, weight=1)
        right_col.columnconfigure(0, weight=1)
        right_col.rowconfigure(0, weight=1)
    
    def toggle_mode(self):
        """สลับระหว่าง Manual และ Auto Mode"""
        if self.auto_mode_var.get():
            # เปลี่ยนเป็น Auto Mode
            self.auto_display_frame.grid()
            self.grid_frame.grid_remove()
            self.hg_frame.grid_remove()
            self.refresh_auto_analysis()
            self.log_message("✓ Switched to Full Auto Mode")
        else:
            # เปลี่ยนเป็น Manual Mode
            self.auto_display_frame.grid_remove()
            self.grid_frame.grid()
            self.hg_frame.grid()
            self.log_message("✓ Switched to Manual Mode")
    
    def refresh_auto_analysis(self):
        """อัพเดทข้อมูลใน Auto Mode (Full - รวม Survivability)"""
        try:
            from auto_config_manager import auto_config_manager
            from candle_volume_detector import candle_volume_detector
            from atr_calculator import atr_calculator
            
            # ตรวจสอบการเชื่อมต่อ MT5
            from mt5_connection import mt5_connection
            if not mt5_connection.connected:
                self.log_message("✗ Please connect to MT5 first")
                return
            
            # ดึงข้อมูลตลาด
            atr_info = atr_calculator.get_atr_info()
            direction_info = candle_volume_detector.get_full_analysis()
            
            # แสดง Market Analysis
            self.auto_atr_var.set(f"{atr_info['atr']:.1f} pips")
            
            if direction_info:
                # แสดง Candle Info
                candle_text = f"{direction_info['candle_type']} ({direction_info['candle_strength']})"
                self.auto_candle_var.set(candle_text)
                
                # เปลี่ยนสี Candle
                if direction_info['candle_type'] == 'BULLISH':
                    self.auto_candle_label.configure(foreground="green")
                elif direction_info['candle_type'] == 'BEARISH':
                    self.auto_candle_label.configure(foreground="red")
                else:
                    self.auto_candle_label.configure(foreground="gray")
                
                # แสดง Volume Info
                vol_text = f"{direction_info['volume_level']} ({direction_info['volume_ratio']:.2f}x)"
                self.auto_volume_var.set(vol_text)
                
                # เปลี่ยนสี Volume
                if direction_info['volume_level'] in ['VERY HIGH', 'HIGH']:
                    self.auto_volume_label.configure(foreground="orange")
                elif direction_info['volume_level'] == 'MODERATE':
                    self.auto_volume_label.configure(foreground="blue")
                else:
                    self.auto_volume_label.configure(foreground="gray")
                
                # แสดง Candle Size และ Volume Ratio
                self.auto_candle_pips_var.set(f"{direction_info['candle_pips']:.1f} pips")
                self.auto_volume_ratio_var.set(f"{direction_info['volume_ratio']:.2f}x")
                
                # แสดง Direction
                dir_text = f"{direction_info['direction'].upper()} ({direction_info['confidence']})"
                self.auto_trend_var.set(dir_text)
                
                # เปลี่ยนสี Direction
                if direction_info['direction'] == 'buy':
                    self.auto_trend_label.configure(foreground="green")
                elif direction_info['direction'] == 'sell':
                    self.auto_trend_label.configure(foreground="red")
                else:
                    self.auto_trend_label.configure(foreground="blue")
            else:
                self.auto_candle_var.set("-")
                self.auto_volume_var.set("-")
                self.auto_candle_pips_var.set("-")
                self.auto_volume_ratio_var.set("-")
                self.auto_trend_var.set("BOTH (LOW)")
                self.auto_trend_label.configure(foreground="blue")
            
            # แสดงเวลาอัพเดท
            from datetime import timedelta
            self.auto_update_time_var.set(
                atr_info['timestamp'].strftime("%H:%M:%S") + 
                f" (Next: {(atr_info['timestamp'] + timedelta(minutes=15)).strftime('%H:%M:%S')})"
            )
            
            # คำนวณ Auto Settings
            settings = auto_config_manager.calculate_auto_settings(
                risk_profile=self.risk_profile_var.get()
            )
            
            # แสดง Auto Calculated Settings
            self.auto_grid_dist_var.set(f"{settings['buy_grid_distance']} pips")
            self.auto_hg_dist_var.set(f"{settings['buy_hg_distance']} pips")
            self.auto_direction_var.set(settings['direction'].upper())
            
            # คำนวณ Survivability
            account_info = mt5_connection.get_account_info()
            price_info = mt5_connection.get_current_price()
            
            if account_info and price_info:
                survival = auto_config_manager.calculate_survivability(
                    balance=account_info['balance'],
                    price=price_info['bid'],
                    leverage=account_info.get('leverage', 100),
                    settings=settings
                )
                
                # แสดงผล Survivability
                self.display_survivability(survival, account_info)
            
            self.log_message("✓ Auto analysis refreshed")
            
        except Exception as e:
            logger.error(f"Error refreshing auto analysis: {e}")
            self.log_message(f"✗ Error: {e}")
    
    def refresh_auto_analysis_light(self):
        """อัพเดทข้อมูลใน Auto Mode แบบเบา (ไม่คำนวณ Survivability)"""
        try:
            from auto_config_manager import auto_config_manager
            from candle_volume_detector import candle_volume_detector
            from atr_calculator import atr_calculator
            
            # ตรวจสอบการเชื่อมต่อ MT5
            from mt5_connection import mt5_connection
            if not mt5_connection.connected:
                return
            
            # ดึงข้อมูลตลาด (ใช้ cache ถ้ามี)
            atr_info = atr_calculator.get_atr_info()
            direction_info = candle_volume_detector.get_full_analysis()
            
            # แสดง Market Analysis
            self.auto_atr_var.set(f"{atr_info['atr']:.1f} pips")
            
            if direction_info:
                # แสดง Candle Info
                candle_text = f"{direction_info['candle_type']} ({direction_info['candle_strength']})"
                self.auto_candle_var.set(candle_text)
                
                # เปลี่ยนสี Candle
                if direction_info['candle_type'] == 'BULLISH':
                    self.auto_candle_label.configure(foreground="green")
                elif direction_info['candle_type'] == 'BEARISH':
                    self.auto_candle_label.configure(foreground="red")
                else:
                    self.auto_candle_label.configure(foreground="gray")
                
                # แสดง Volume Info
                vol_text = f"{direction_info['volume_level']} ({direction_info['volume_ratio']:.2f}x)"
                self.auto_volume_var.set(vol_text)
                
                # เปลี่ยนสี Volume
                if direction_info['volume_level'] in ['VERY HIGH', 'HIGH']:
                    self.auto_volume_label.configure(foreground="orange")
                elif direction_info['volume_level'] == 'MODERATE':
                    self.auto_volume_label.configure(foreground="blue")
                else:
                    self.auto_volume_label.configure(foreground="gray")
                
                # แสดง Candle Size และ Volume Ratio
                self.auto_candle_pips_var.set(f"{direction_info['candle_pips']:.1f} pips")
                self.auto_volume_ratio_var.set(f"{direction_info['volume_ratio']:.2f}x")
                
                # แสดง Direction
                dir_text = f"{direction_info['direction'].upper()} ({direction_info['confidence']})"
                self.auto_trend_var.set(dir_text)
                
                # เปลี่ยนสี Direction
                if direction_info['direction'] == 'buy':
                    self.auto_trend_label.configure(foreground="green")
                elif direction_info['direction'] == 'sell':
                    self.auto_trend_label.configure(foreground="red")
                else:
                    self.auto_trend_label.configure(foreground="blue")
            
            # แสดงเวลาอัพเดท
            from datetime import timedelta
            self.auto_update_time_var.set(
                atr_info['timestamp'].strftime("%H:%M:%S") + 
                f" (Next: {(atr_info['timestamp'] + timedelta(minutes=15)).strftime('%H:%M:%S')})"
            )
            
            # คำนวณ Auto Settings (เร็ว)
            settings = auto_config_manager.calculate_auto_settings(
                risk_profile=self.risk_profile_var.get()
            )
            
            # แสดง Auto Calculated Settings
            self.auto_grid_dist_var.set(f"{settings['buy_grid_distance']} pips")
            self.auto_hg_dist_var.set(f"{settings['buy_hg_distance']} pips")
            self.auto_direction_var.set(settings['direction'].upper())
            
            # ไม่คำนวณ Survivability เพื่อความเร็ว
            
        except Exception as e:
            logger.error(f"Error refreshing auto analysis (light): {e}")
    
    def display_survivability(self, survival, account_info):
        """แสดงผล Survivability Analysis"""
        self.survivability_text.config(state=tk.NORMAL)
        self.survivability_text.delete(1.0, tk.END)
        
        text = f"""╔═══════════════════════════════════════════════════╗
║        📊 SURVIVABILITY ANALYSIS                  ║
╠═══════════════════════════════════════════════════╣

💰 ACCOUNT INFO:
   Balance:      ${account_info['balance']:,.2f}
   Equity:       ${account_info['equity']:,.2f}
   Used Margin:  ${account_info['margin']:,.2f} ({account_info['margin']/account_info['equity']*100:.1f}%)
   Free Margin:  ${account_info['free_margin']:,.2f}

─────────────────────────────────────────────────────

🎯 SYSTEM CAPACITY (Worst Case):
   Max Distance:     {survival['max_distance_pips']:,} pips
   Max Grid Levels:  {survival['max_grid_levels']} levels
   Max HG Levels:    {survival['max_hg_levels']} levels
   
   Max Margin Used:  ${survival['max_margin']:,.2f}
   Max Drawdown:     ${survival['max_drawdown']:,.2f}
   Final Equity:     ${survival['final_equity']:,.2f}
   Margin Level:     {survival['final_margin_level']:.1f}%

   Status:           {survival['status']}

─────────────────────────────────────────────────────

⚠️  IMPORTANT:
   • Worst case: ราคาเดินทางเดียวไม่กลับ
   • ไม่รวม Spread/Commission
   • แนะนำเหลือ Buffer 30-50%

╚═══════════════════════════════════════════════════╝
"""
        
        self.survivability_text.insert(tk.END, text)
        self.survivability_text.config(state=tk.DISABLED)
    
    def create_risk_calculator_tab(self):
        """สร้าง content สำหรับ Risk Calculator Tab"""
        
        # ============ Frame หลัก ============
        main_frame = ttk.Frame(self.risk_tab, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # ============ Title ============
        title_label = ttk.Label(main_frame, text="🛡️ Risk Calculator", 
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=10)
        
        desc_label = ttk.Label(main_frame, 
                              text="คำนวณว่าระบบจะทนได้กี่ pips ก่อน Margin Call ตาม Settings ปัจจุบัน",
                              font=("Arial", 9), foreground="gray")
        desc_label.pack(pady=5)
        
        # ============ Info Frame ============
        info_frame = ttk.LabelFrame(main_frame, text="ℹ️ Information", padding="15")
        info_frame.pack(fill=tk.X, padx=20, pady=10)
        
        info_text = ttk.Label(info_frame, 
                             text="✨ Auto Calculate: ระบบจะคำนวณอัตโนมัติเมื่อเปิด Tab หรือ Save Settings\n" +
                                  "📊 ใช้ข้อมูลจาก MT5 โดยตรง (Balance, Price, Leverage)\n" +
                                  "🔄 กด Refresh เพื่อคำนวณใหม่ด้วยตนเอง",
                             foreground="gray", justify=tk.LEFT)
        info_text.pack(pady=5)
        
        # Refresh Button
        refresh_button = ttk.Button(info_frame, text="🔄 Refresh Risk Analysis", 
                                command=self.calculate_risk_analysis, style="Start.TButton")
        refresh_button.pack(pady=10)
        
        # ============ Results Frame ============
        results_frame = ttk.LabelFrame(main_frame, text="📊 Risk Analysis Results", padding="15")
        results_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # สร้าง ScrolledText สำหรับแสดงผล
        self.risk_result_text = scrolledtext.ScrolledText(results_frame, height=25, width=90, 
                                                          wrap=tk.WORD, font=("Consolas", 10))
        self.risk_result_text.pack(fill=tk.BOTH, expand=True)
        
        # แสดงข้อความเริ่มต้น
        self.risk_result_text.insert(tk.END, "⏳ กำลังเตรียมข้อมูล...\n\n")
        self.risk_result_text.insert(tk.END, "กรุณารอสักครู่...\n")
        self.risk_result_text.config(state=tk.DISABLED)
        
        # Auto calculate หลังจากสร้าง UI เสร็จ (ใช้ after เพื่อรอให้ UI render เสร็จก่อน)
        self.root.after(500, self.auto_calculate_risk)
    
    def update_risk_calculator_display(self):
        """อัพเดทค่าที่แสดงใน Risk Calculator หลัง Save Settings"""
        # Auto calculate ใหม่ทันที
        self.auto_calculate_risk()
    
    def auto_calculate_risk(self):
        """คำนวณ Risk Analysis อัตโนมัติ"""
        try:
            # เช็คว่า Risk Calculator tab ถูกสร้างแล้วหรือยัง
            if not hasattr(self, 'risk_result_text'):
                return
            
            self.calculate_risk_analysis()
        except Exception as e:
            logger.error(f"Auto calculate risk error: {e}")
    
    def calculate_risk_analysis(self):
        """คำนวณ Risk Analysis"""
        try:
            # Auto ใช้ข้อมูลจาก MT5 โดยตรง
            balance = None
            price = None
            leverage = 100  # default
            
            # คำนวณ
            self.risk_result_text.config(state=tk.NORMAL)
            self.risk_result_text.delete(1.0, tk.END)
            self.risk_result_text.insert(tk.END, "⏳ กำลังคำนวณ...\n")
            self.risk_result_text.update()
            
            result = risk_calculator.calculate_risk(balance, price, leverage)
            
            # แสดงผล
            self.risk_result_text.delete(1.0, tk.END)
            
            if 'error' in result:
                self.risk_result_text.insert(tk.END, f"❌ Error: {result['message']}\n")
                self.risk_result_text.config(state=tk.DISABLED)
                return
            
            # Header
            self.risk_result_text.insert(tk.END, "=" * 80 + "\n")
            self.risk_result_text.insert(tk.END, "                    🛡️ RISK CALCULATOR RESULTS\n")
            self.risk_result_text.insert(tk.END, "=" * 80 + "\n\n")
            
            # Account Info
            self.risk_result_text.insert(tk.END, "📋 ACCOUNT INFORMATION:\n")
            self.risk_result_text.insert(tk.END, f"   Balance:      ${result['balance']:,.2f}\n")
            self.risk_result_text.insert(tk.END, f"   Current Price: {result['price']:.2f}\n")
            self.risk_result_text.insert(tk.END, f"   Leverage:     1:{result['leverage']}\n\n")
            
            # Settings
            self.risk_result_text.insert(tk.END, "⚙️  CURRENT SETTINGS:\n")
            self.risk_result_text.insert(tk.END, f"   Grid Distance:  {config.grid.grid_distance} pips\n")
            self.risk_result_text.insert(tk.END, f"   Grid Lot Size:  {config.grid.lot_size} lots\n")
            self.risk_result_text.insert(tk.END, f"   Grid Direction: {config.grid.direction}\n")
            self.risk_result_text.insert(tk.END, f"   HG Enabled:     {config.hg.enabled}\n")
            if config.hg.enabled:
                self.risk_result_text.insert(tk.END, f"   HG Distance:    {config.hg.hg_distance} pips\n")
                self.risk_result_text.insert(tk.END, f"   HG Multiplier:  {config.hg.hg_multiplier}x\n")
                self.risk_result_text.insert(tk.END, f"   Max HG Levels:  {config.hg.max_hg_levels}\n")
            self.risk_result_text.insert(tk.END, "\n")
            
            # Grid Only Results
            grid_only = result['grid_only']
            self.risk_result_text.insert(tk.END, "=" * 80 + "\n")
            self.risk_result_text.insert(tk.END, "📊 GRID ONLY (Without HG):\n")
            self.risk_result_text.insert(tk.END, "=" * 80 + "\n")
            self.risk_result_text.insert(tk.END, f"   ✅ Max Distance:       {grid_only['max_distance_pips']:,} pips\n")
            self.risk_result_text.insert(tk.END, f"   ✅ Max Levels:         {grid_only['max_levels']} levels\n")
            self.risk_result_text.insert(tk.END, f"   ⚠️  Max Margin Used:    ${grid_only['max_margin']:,.2f}\n")
            self.risk_result_text.insert(tk.END, f"   ⚠️  Max Drawdown:       ${grid_only['max_drawdown']:,.2f}\n")
            self.risk_result_text.insert(tk.END, f"   📊 Final Margin Level: {grid_only['final_margin_level']:.1f}%\n")
            self.risk_result_text.insert(tk.END, f"   💰 Final Equity:       ${grid_only['final_equity']:,.2f}\n")
            self.risk_result_text.insert(tk.END, f"   🛡️  Status:             {grid_only['status']}\n\n")
            
            # With HG Results
            if result['hg_enabled'] and result['with_hg']:
                with_hg = result['with_hg']
                self.risk_result_text.insert(tk.END, "=" * 80 + "\n")
                self.risk_result_text.insert(tk.END, "🛡️ GRID + HG (With Hedge):\n")
                self.risk_result_text.insert(tk.END, "=" * 80 + "\n")
                self.risk_result_text.insert(tk.END, f"   ⚠️  Max Distance:       {with_hg['max_distance_pips']:,} pips\n")
                self.risk_result_text.insert(tk.END, f"   📊 Max Grid Levels:    {with_hg['max_grid_levels']} levels\n")
                self.risk_result_text.insert(tk.END, f"   🛡️  Max HG Levels:      {with_hg['max_hg_levels']} levels\n")
                self.risk_result_text.insert(tk.END, f"   ⚠️  Max Margin Used:    ${with_hg['max_margin']:,.2f}\n")
                self.risk_result_text.insert(tk.END, f"   ⚠️  Max Drawdown:       ${with_hg['max_drawdown']:,.2f}\n")
                self.risk_result_text.insert(tk.END, f"       - Grid Drawdown:   ${with_hg['grid_drawdown']:,.2f}\n")
                self.risk_result_text.insert(tk.END, f"       - HG Drawdown:     ${with_hg['hg_drawdown']:,.2f}\n")
                self.risk_result_text.insert(tk.END, f"   📊 Final Margin Level: {with_hg['final_margin_level']:.1f}%\n")
                self.risk_result_text.insert(tk.END, f"   💰 Final Equity:       ${with_hg['final_equity']:,.2f}\n")
                self.risk_result_text.insert(tk.END, f"   🛡️  Status:             {with_hg['status']}\n\n")
                
                # Comparison (ป้องกัน division by zero)
                if grid_only['max_distance_pips'] > 0:
                    reduction = ((grid_only['max_distance_pips'] - with_hg['max_distance_pips']) 
                                / grid_only['max_distance_pips'] * 100)
                else:
                    reduction = 0
                
                self.risk_result_text.insert(tk.END, "=" * 80 + "\n")
                self.risk_result_text.insert(tk.END, "⚖️  COMPARISON:\n")
                self.risk_result_text.insert(tk.END, "=" * 80 + "\n")
                self.risk_result_text.insert(tk.END, f"   ⚠️  HG reduces safe distance by: {reduction:.1f}%\n")
                self.risk_result_text.insert(tk.END, f"   📊 Distance reduction: {grid_only['max_distance_pips'] - with_hg['max_distance_pips']:,} pips\n\n")
            
            # Warnings
            self.risk_result_text.insert(tk.END, "=" * 80 + "\n")
            self.risk_result_text.insert(tk.END, "⚠️  IMPORTANT WARNINGS:\n")
            self.risk_result_text.insert(tk.END, "=" * 80 + "\n")
            self.risk_result_text.insert(tk.END, "   1. การคำนวณนี้เป็น Worst Case (ราคาเดินทางเดียวไม่กลับ)\n")
            self.risk_result_text.insert(tk.END, "   2. Safe Margin Level = 150% (ปลอดภัย)\n")
            self.risk_result_text.insert(tk.END, "   3. ไม่รวมค่า Spread และ Commission\n")
            self.risk_result_text.insert(tk.END, "   4. ราคาทองคำเคลื่อนไหวเร็ว ระวังความเสี่ยง!\n")
            self.risk_result_text.insert(tk.END, "   5. แนะนำให้เหลือ Buffer อย่างน้อย 30-50%\n\n")
            
            self.risk_result_text.config(state=tk.DISABLED)
            
        except ValueError:
            messagebox.showerror("Error", "กรุณาใส่ตัวเลขที่ถูกต้อง")
        except Exception as e:
            self.risk_result_text.config(state=tk.NORMAL)
            self.risk_result_text.insert(tk.END, f"\n❌ Error: {str(e)}\n")
            self.risk_result_text.config(state=tk.DISABLED)
            messagebox.showerror("Error", f"เกิดข้อผิดพลาด: {str(e)}")
    
    def log_message(self, message: str):
        """
        แสดงข้อความใน log display
        
        Args:
            message: ข้อความที่ต้องการแสดง
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        
        self.log_text.insert(tk.END, log_entry)
        self.log_text.see(tk.END)  # Auto-scroll
        
        # จำกัดจำนวนบรรทัด (เก็บแค่ 100 บรรทัดล่าสุด)
        lines = self.log_text.get("1.0", tk.END).split("\n")
        if len(lines) > 100:
            self.log_text.delete("1.0", "2.0")
    
    def connect_mt5(self):
        """เชื่อมต่อกับ MT5"""
        self.log_message("Connecting to MT5...")
        
        # ดึงบัญชีที่เลือก
        selected_account = self.account_var.get()
        if selected_account == "Auto":
            account_login = None
            self.log_message("Using Auto account selection")
        else:
            # แยก account login จาก "12345 - ServerName"
            account_login = int(selected_account.split(" - ")[0])
            self.log_message(f"Connecting to account: {account_login}")
        
        if mt5_connection.connect_to_mt5(login=account_login):
            self.connection_status.set("Connected ✓")
            self.status_label.configure(foreground="green")
            
            # ดึงข้อมูล account
            account_info = mt5_connection.get_account_info()
            if account_info:
                # แสดง account number
                import MetaTrader5 as mt5
                account = mt5.account_info()
                self.account_number_var.set(str(account.login))
                
                # แสดง balance
                self.balance_var.set(f"${account_info['balance']:,.2f}")
                
                # แสดง broker (server name)
                self.broker_var.set(account.server if account.server else "Unknown")
                
                # แสดง symbol ที่ใช้งาน
                self.symbol_var.set(mt5_connection.symbol)
                
                self.log_message("✓ Connected to MT5 successfully")
                self.log_message(f"  Account: {account.login} | Broker: {account.server}")
                self.log_message(f"  Balance: ${account_info['balance']:,.2f} | Symbol: {mt5_connection.symbol}")
                
                # Auto calculate risk หลังจาก connect สำเร็จ
                self.root.after(500, self.auto_calculate_risk)
            else:
                self.log_message("✓ Connected to MT5 (cannot retrieve account info)")
                
        else:
            self.connection_status.set("Connection Failed ✗")
            self.status_label.configure(foreground="red")
            self.log_message("✗ Failed to connect to MT5")
            messagebox.showerror("Connection Error", "Cannot connect to MT5. Please check if MT5 is running.")
    
    def _update_label_color(self, widget, color):
        """อัพเดทสีของ label แบบ recursive"""
        for child in widget.winfo_children():
            if isinstance(child, ttk.Label) and child.cget("textvariable") == str(self.connection_status):
                child.configure(foreground=color)
            self._update_label_color(child, color)
    
    def disconnect_mt5(self):
        """ตัดการเชื่อมต่อ MT5"""
        if self.is_running:
            messagebox.showwarning("Warning", "Please stop trading before disconnecting.")
            return
        
        mt5_connection.disconnect()
        self.connection_status.set("Disconnected")
        self.status_label.configure(foreground="red")
        
        # รีเซ็ตข้อมูล account
        self.account_number_var.set("-")
        self.balance_var.set("-")
        self.broker_var.set("-")
        self.symbol_var.set("-")
        
        self.log_message("Disconnected from MT5")
    
    def save_settings(self):
        """บันทึกการตั้งค่า"""
        try:
            self._save_settings()
            self.log_message("✓ Settings saved and applied immediately!")
            
            # อัพเดท Risk Calculator ถ้าอยู่ใน tab นั้น
            self.update_risk_calculator_display()
            
            messagebox.showinfo("Success", 
                              "Settings saved successfully!\n\n" +
                              "✅ ค่าใหม่ถูกใช้งานทันที (ไม่ต้องรีสตาร์ท)\n" +
                              "✅ ระบบจะใช้ค่าใหม่สำหรับไม้ที่วางหลังจากนี้")
            
        except Exception as e:
            self.log_message(f"✗ Error saving settings: {e}")
            messagebox.showerror("Error", f"Failed to save settings: {e}")

    def _save_settings(self):
        """บันทึกการตั้งค่า (internal)"""
        # Validation: เตือนถ้า Take Profit มากกว่า Grid Distance (เฉพาะ Manual Mode)
        if not self.auto_mode_var.get():
            buy_grid_dist = self.buy_grid_distance_var.get()
            buy_tp = self.buy_tp_var.get()
            sell_grid_dist = self.sell_grid_distance_var.get()
            sell_tp = self.sell_tp_var.get()
            
            warnings = []
            if buy_tp > buy_grid_dist:
                warnings.append(f"Buy TP ({buy_tp}) > Buy Grid Distance ({buy_grid_dist})")
            if sell_tp > sell_grid_dist:
                warnings.append(f"Sell TP ({sell_tp}) > Sell Grid Distance ({sell_grid_dist})")
            
            if warnings:
                response = messagebox.askyesno(
                    "⚠️ Warning",
                    "พบปัญหา:\n" + "\n".join(warnings) + "\n\n" +
                    "แนะนำ: TP ควรน้อยกว่าหรือเท่ากับ Grid Distance\n" +
                    "ต้องการบันทึกต่อไหม?"
                )
                if not response:
                    return
        
        # อัพเดทค่าใน config
        if self.auto_mode_var.get():
            # Auto Mode: บันทึกเฉพาะ risk_profile และ auto_mode
            config.update_grid_settings(
                auto_mode=True,
                risk_profile=self.risk_profile_var.get()
            )
        else:
            # Manual Mode: บันทึกค่าทั้งหมด
            buy_grid_dist = self.buy_grid_distance_var.get()
            buy_tp = self.buy_tp_var.get()
            sell_grid_dist = self.sell_grid_distance_var.get()
            sell_tp = self.sell_tp_var.get()
            
            config.update_grid_settings(
                auto_mode=False,
                direction=self.direction_var.get(),
                # Buy Settings
                buy_grid_distance=buy_grid_dist,
                buy_lot_size=self.buy_lot_size_var.get(),
                buy_take_profit=buy_tp,
                # Sell Settings
                sell_grid_distance=sell_grid_dist,
                sell_lot_size=self.sell_lot_size_var.get(),
                sell_take_profit=sell_tp,
                # Backward compatibility
                grid_distance=buy_grid_dist,  # ใช้ค่า buy เป็น default
                lot_size=self.buy_lot_size_var.get(),
                take_profit=buy_tp
            )
        
        config.update_hg_settings(
            enabled=self.hg_enabled_var.get(),
            direction=self.hg_direction_var.get(),
            # Buy HG Settings
            buy_hg_distance=self.buy_hg_distance_var.get(),
            buy_hg_sl_trigger=self.buy_hg_sl_trigger_var.get(),
            buy_hg_multiplier=self.buy_hg_multiplier_var.get(),
            buy_hg_initial_lot=self.buy_hg_initial_lot_var.get(),
            buy_sl_buffer=self.buy_sl_buffer_var.get(),
            buy_max_hg_levels=self.buy_max_hg_levels_var.get(),
            # Sell HG Settings
            sell_hg_distance=self.sell_hg_distance_var.get(),
            sell_hg_sl_trigger=self.sell_hg_sl_trigger_var.get(),
            sell_hg_multiplier=self.sell_hg_multiplier_var.get(),
            sell_hg_initial_lot=self.sell_hg_initial_lot_var.get(),
            sell_sl_buffer=self.sell_sl_buffer_var.get(),
            sell_max_hg_levels=self.sell_max_hg_levels_var.get(),
            # Backward compatibility
            sl_buffer=self.buy_sl_buffer_var.get(),
            max_hg_levels=self.buy_max_hg_levels_var.get(),
            hg_distance=self.buy_hg_distance_var.get(),
            hg_sl_trigger=self.buy_hg_sl_trigger_var.get(),
            hg_multiplier=self.buy_hg_multiplier_var.get()
        )
        
        # บันทึกลงไฟล์
        config.save_to_file()
    
    
    def load_settings_to_gui(self):
        """โหลดการตั้งค่าจาก config มาแสดงใน GUI"""
        # Auto Mode Settings
        self.auto_mode_var.set(config.grid.auto_mode)
        if hasattr(self, 'risk_profile_var'):
            self.risk_profile_var.set(config.grid.risk_profile)
        
        # Grid Settings
        self.direction_var.set(config.grid.direction)
        self.buy_grid_distance_var.set(config.grid.buy_grid_distance)
        self.buy_lot_size_var.set(config.grid.buy_lot_size)
        self.buy_tp_var.set(config.grid.buy_take_profit)
        self.sell_grid_distance_var.set(config.grid.sell_grid_distance)
        self.sell_lot_size_var.set(config.grid.sell_lot_size)
        self.sell_tp_var.set(config.grid.sell_take_profit)
        
        # HG Settings
        self.hg_enabled_var.set(config.hg.enabled)
        self.hg_direction_var.set(config.hg.direction)
        self.buy_hg_distance_var.set(config.hg.buy_hg_distance)
        self.buy_hg_sl_trigger_var.set(config.hg.buy_hg_sl_trigger)
        self.buy_hg_multiplier_var.set(config.hg.buy_hg_multiplier)
        self.buy_hg_initial_lot_var.set(config.hg.buy_hg_initial_lot)
        self.buy_sl_buffer_var.set(config.hg.buy_sl_buffer)
        self.buy_max_hg_levels_var.set(config.hg.buy_max_hg_levels)
        self.sell_hg_distance_var.set(config.hg.sell_hg_distance)
        self.sell_hg_sl_trigger_var.set(config.hg.sell_hg_sl_trigger)
        self.sell_hg_multiplier_var.set(config.hg.sell_hg_multiplier)
        self.sell_hg_initial_lot_var.set(config.hg.sell_hg_initial_lot)
        self.sell_sl_buffer_var.set(config.hg.sell_sl_buffer)
        self.sell_max_hg_levels_var.set(config.hg.sell_max_hg_levels)
        
        # Toggle mode UI
        self.toggle_mode()
        
    
    def refresh_accounts(self):
        """รีเฟรชรายการบัญชี MT5 ที่มีอยู่"""
        try:
            import MetaTrader5 as mt5
            
            # เริ่มต้น MT5
            if not mt5.initialize():
                logger.error("MT5 initialize failed")
                return
            
            # ดึงข้อมูลบัญชีปัจจุบัน
            account = mt5.account_info()
            if account is None:
                logger.warning("No account info available")
                account_list = ["Auto"]
            else:
                account_list = ["Auto"]  # เพิ่ม Auto เป็นตัวเลือกแรก
                # เพิ่มบัญชีปัจจุบัน
                current_account = f"{account.login} - {account.server}"
                account_list.append(current_account)
            
            # อัพเดท combobox
            self.account_combo['values'] = account_list
            if not self.account_var.get() or self.account_var.get() not in account_list:
                self.account_var.set("Auto")
            
            logger.info(f"Found current MT5 account: {account.login}")
            self.log_message(f"✓ Found current MT5 account: {account.login}")
            
        except Exception as e:
            logger.error(f"Error refreshing accounts: {e}")
            self.log_message(f"✗ Error refreshing accounts: {e}")
            # ตั้งค่า default
            self.account_combo['values'] = ["Auto"]
            self.account_var.set("Auto")
    
    def should_report_status(self):
        """Check if it's time to report status"""
        if hasattr(self, 'next_report_time') and self.next_report_time:
            current_utc = datetime.now(timezone.utc)
            next_report_utc = self.next_report_time.astimezone(timezone.utc)
            
            return current_utc >= next_report_utc
        return True  # Report if no scheduled time

    def report_status(self):
        """Report the current status to the API"""

        try:
            account_info = mt5_connection.get_account_info()
        except Exception as e:
            raise Exception(f"Failed to get account data: {str(e)}")
        
        status_response = requests.post(
            f"{self.api_base_url}/customer-clients/status",
            json={
                "tradingAccountId": str(account_info['login']),
                "name": account_info['name'],
                "brokerName": account_info['company'],
                "currentBalance":  str(account_info['balance']),
                "currentProfit": str(account_info['profit']),
                "currency": account_info['currency'],
                "botName": "Grid Trading AI",
                "botVersion": "0.0.1"
            },
            timeout=10
        )
        
        if status_response.status_code == 200:
            response_data = status_response.json()
            
            expiry_date_var = response_data.get("expiryDate")
            if expiry_date_var:
                self.expiry_date_var.set(expiry_date_var)
            else:
                self.expiry_date_var.set("-")

            # Check if trading is inactive
            if response_data.get("processedStatus") == "inactive":
                # message = response_data.get("message", "Unknown reason")
                raise Exception(f"ไม่สามารถเริ่มระบบเทรดได้: หมดอายุไอฟาย ^^")
                
            # Store next report time for scheduling
            next_report_time = response_data.get("nextReportTime")
            if next_report_time:
                # Fix microseconds to 6 digits
                if '.' in next_report_time and '+' in next_report_time:
                    parts = next_report_time.split('.')
                    microseconds = parts[1].split('+')[0]
                    timezone_part = '+' + parts[1].split('+')[1]
                    
                    # Truncate microseconds to 6 digits
                    if len(microseconds) > 6:
                        microseconds = microseconds[:6]
                    
                    next_report_time = f"{parts[0]}.{microseconds}{timezone_part}"
                
                self.next_report_time = datetime.fromisoformat(next_report_time)
                print(f"Next report scheduled for: {self.next_report_time}")
                
        else:
            raise Exception(f"Failed to check status: {status_response.status_code}")

    def start_trading(self):
        """เริ่มต้นระบบเทรด"""
        if not mt5_connection.connected:
            messagebox.showerror("Error", "Please connect to MT5 first!")
            return
        
        # บันทึกการตั้งค่าก่อนเริ่ม
        self._save_settings()

        try:
            self.report_status()
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        
        # ดึงราคาปัจจุบัน
        price_info = mt5_connection.get_current_price()
        if not price_info:
            error_msg = "Cannot get current price!\n\nPossible causes:\n"
            error_msg += "1. Symbol not available in broker\n"
            error_msg += "2. Market closed\n"
            error_msg += "3. Symbol not selected in MT5\n"
            error_msg += "4. Network connection issue\n\n"
            error_msg += "Please check MT5 terminal and try again."
            messagebox.showerror("Error", error_msg)
            self.log_message("✗ Failed to get current price - check MT5 terminal")
            return
        
        current_price = price_info['bid']
        
        # แสดงราคาใน GUI ทันที
        self.price_var.set(f"{current_price:.2f}")
        
        # เริ่ม Grid System
        if grid_manager.start_grid_trading():
            self.log_message(f"✓ Grid Trading started at {current_price:.2f}")
        else:
            messagebox.showerror("Error", "Failed to start Grid Trading")
            return
        
        # เริ่ม HG System
        if config.hg.enabled:
            self.hg_manager.start_hg_system(current_price)
            self.log_message(f"✓ HG System started at {current_price:.2f}")
        
        # เริ่ม monitoring
        self.is_running = True
        self.stop_monitoring = False
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
        # เริ่ม monitoring thread
        self.monitoring_thread = threading.Thread(target=self.monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        
        self.log_message("🚀 Trading System ACTIVE")
    
    def stop_trading(self):
        """หยุดระบบเทรด"""
        response = messagebox.askyesno("Confirm", "Stop trading?")
        if not response:
            return
        
        self._stop_trading_internal()

    def _stop_trading_internal(self):
        self.is_running = False
        self.stop_monitoring = True
        
        grid_manager.stop_grid_trading(close_positions=False)
        self.hg_manager.stop_hg_system()
        
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        
        self.log_message("⏸ Trading System STOPPED (positions remain open)")
    
    def emergency_stop(self):
        """หยุดฉุกเฉินและปิด positions ทั้งหมด"""
        response = messagebox.askyesno("⚠️ EMERGENCY STOP", 
                                       "This will close ALL positions immediately!\n\nAre you sure?",
                                       icon='warning')
        if not response:
            return
        
        self.log_message("🛑 EMERGENCY STOP ACTIVATED")
        
        # หยุดระบบ
        self.is_running = False
        self.stop_monitoring = True
        
        # ปิด positions ทั้งหมด
        closed = mt5_connection.close_all_positions()
        
        grid_manager.stop_grid_trading(close_positions=False)
        
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        
        self.log_message(f"🛑 Emergency Stop: Closed {closed} positions")
        messagebox.showinfo("Emergency Stop", f"Closed {closed} positions")
    
    def refresh_status(self):
        """รีเฟรชสถานะทั้งหมด"""
        self.update_display()
        self.log_message("🔄 Status refreshed")
    
    def test_price_connection(self):
        """ทดสอบการเชื่อมต่อและดึงราคา"""
        self.log_message("🧪 Testing price connection...")
        
        if not mt5_connection.connected:
            self.log_message("✗ MT5 not connected")
            messagebox.showerror("Error", "Please connect to MT5 first!")
            return
        
        # ทดสอบดึงราคา
        price_info = mt5_connection.get_current_price()
        
        if price_info:
            self.log_message(f"✓ Price test successful: {price_info['bid']:.2f}")
            messagebox.showinfo("Success", f"Price connection OK!\n\nBid: {price_info['bid']:.2f}\nAsk: {price_info['ask']:.2f}\nSymbol: {mt5_connection.symbol}")
        else:
            self.log_message("✗ Price test failed")
            messagebox.showerror("Error", "Cannot get price data!\n\nPlease check:\n1. Symbol is available in MT5\n2. Market is open\n3. Symbol is selected in MT5")
    
    def monitoring_loop(self):
        """
        Loop หลักสำหรับ monitoring ระบบ
        ทำงานใน background thread
        Optimized: ลดการเรียกซ้ำ get_current_price และ update_all_positions
        """
        while not self.stop_monitoring and self.is_running:
            # API Status Check (หยุดระบบถ้า API error เพราะถูก lock จากภายนอก)
            try:
                if self.should_report_status():
                    self.report_status()
            except Exception as e:
                # หยุดการทำงาน ถ้า API error (ระบบถูก lock จากภายนอก)
                logger.error(f"API Status Error: {e}")
                self._stop_trading_internal()
                self.log_message(f"✗ Trading stopped: {e}")
                # ย้าย messagebox ไปใช้ root.after() เพื่อป้องกัน hang ใน background thread
                self.root.after(0, lambda err=str(e): messagebox.showerror("Error", f"Trading stopped: {err}"))
                break

            # 🆕 Auto Mode: อัพเดท UI เฉพาะทุก 60 วินาที (ไม่ใช่ทุกรอบ)
            if config.grid.auto_mode:
                self.auto_refresh_counter += 1
                if self.auto_refresh_counter >= self.auto_refresh_interval:
                    self.auto_refresh_counter = 0
                    # เรียกแบบ non-blocking
                    self.root.after(0, lambda: self.refresh_auto_analysis_light())

            # Main Monitoring Section
            try:
                # ดึงราคาเพียงครั้งเดียวแล้วใช้ต่อ (ลดการเรียกซ้ำ)
                price_info = mt5_connection.get_current_price()
                if not price_info:
                    logger.warning("Cannot get price info - skipping this cycle")
                    threading.Event().wait(0.5)
                    continue
                
                current_price = price_info['bid']
                
                # อัพเดท positions ครั้งเดียว (ใช้ร่วมกันทั้ง Grid และ HG)
                try:
                    position_monitor.update_all_positions()
                except Exception as e:
                    logger.error(f"Error updating positions: {e}")
                    # ยังทำงานต่อ แต่ข้ามส่วนที่ใช้ positions
                
                # อัพเดท Grid (มี error handling แยก - ไม่หยุดระบบ)
                try:
                    grid_manager.update_grid_status()
                except Exception as e:
                    logger.error(f"Error in grid manager: {e}", exc_info=True)
                    self.root.after(0, lambda err=str(e): self.log_message(f"✗ Grid Error: {err}"))
                
                # อัพเดท HG (ถ้าเปิดใช้งาน) - ใช้ราคาที่ดึงไว้แล้ว
                if config.hg.enabled:
                    try:
                        self.hg_manager.manage_multiple_hg(current_price)
                    except Exception as e:
                        logger.error(f"Error in HG manager: {e}", exc_info=True)
                        self.root.after(0, lambda err=str(e): self.log_message(f"✗ HG Error: {err}"))
                
                # ตรวจสอบความเสี่ยง
                try:
                    position_monitor.send_alerts()
                except Exception as e:
                    logger.error(f"Error in risk alerts: {e}")
                
                # 🆕 อัพเดท GUI (ใช้ throttling เพื่อลดการอัพเดทบ่อยเกินไป)
                try:
                    import time
                    current_time = time.time()
                    if current_time - self.last_display_update >= self.display_update_interval:
                        self.last_display_update = current_time
                        self.root.after(0, self.update_display)
                except Exception as e:
                    logger.error(f"Error scheduling GUI update: {e}")
                
                # รอ 0.5 วินาที
                threading.Event().wait(0.5)
                
            except Exception as e:
                # Error handling สำหรับ main section (ไม่หยุด loop)
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                import traceback
                logger.error(traceback.format_exc())
                self.root.after(0, lambda err=str(e): self.log_message(f"✗ Monitoring Error: {err}"))
                # รอสักครู่ก่อน retry (ป้องกัน infinite error loop)
                threading.Event().wait(1.0)
    
    def update_display(self):
        """อัพเดทการแสดงผลใน GUI (Optimized - ลดการอัพเดทบ่อยเกินไป)"""
        try:
            # อัพเดท Account Balance (real-time)
            if mt5_connection.connected:
                account_info = mt5_connection.get_account_info()
                if account_info:
                    self.balance_var.set(f"${account_info['balance']:,.2f}")
            
            # อัพเดท Grid status
            grid_status = grid_manager.get_grid_status()
            self.grid_levels_var.set(f"{grid_status['active_levels']} levels")
            
            # อัพเดท HG status
            hg_status = self.hg_manager.get_hg_status()
            self.hg_positions_var.set(f"{hg_status['placed_hg_count']} positions")
            
            # อัพเดท positions summary
            summary = position_monitor.get_positions_summary()
            
            # Total P&L
            pnl = summary['total_pnl']
            self.total_pnl_var.set(f"${pnl:.2f}")
            
            # เปลี่ยนสีตาม P&L
            if pnl > 0:
                self.pnl_label.configure(foreground="green")
            elif pnl < 0:
                self.pnl_label.configure(foreground="red")
            else:
                self.pnl_label.configure(foreground="black")
            
            # Margin
            margin_usage = summary['margin_usage']
            self.margin_var.set(f"{margin_usage:.1f}%")
            
            # Grid Exposure
            self.grid_exposure_var.set(f"{summary['grid_net_volume']:.2f} lots")
            
            # Current Price
            price_info = mt5_connection.get_current_price()
            if price_info:
                current_price = price_info['bid']
                self.price_var.set(f"{current_price:.2f}")
            else:
                self.price_var.set("No Price Data")
                current_price = 0
            
            # 🆕 อัพเดท Statistics Tab (ถ้าเปิด Auto Mode)
            if config.grid.auto_mode and hasattr(self, 'total_orders_var'):
                try:
                    # Total Orders
                    total_orders = grid_status['active_levels'] + hg_status['placed_hg_count']
                    self.total_orders_var.set(str(total_orders))
                    
                    # Active Positions
                    active_positions = len(position_monitor.grid_positions) + len(position_monitor.hg_positions)
                    self.active_positions_var.set(str(active_positions))
                    
                    # Total P&L (Statistics)
                    self.stats_pnl_var.set(f"${pnl:.2f}")
                    if pnl > 0:
                        self.stats_pnl_label.configure(foreground="green")
                    elif pnl < 0:
                        self.stats_pnl_label.configure(foreground="red")
                    else:
                        self.stats_pnl_label.configure(foreground="black")
                    
                    # Win Rate (คำนวณจาก closed positions - ถ้ามี)
                    # TODO: เพิ่มการติดตาม closed positions เพื่อคำนวณ win rate
                    self.win_rate_var.set("N/A")
                    
                    # Average Profit
                    if active_positions > 0:
                        avg_profit = pnl / active_positions
                        self.avg_profit_var.set(f"${avg_profit:.2f}")
                    else:
                        self.avg_profit_var.set("$0.00")
                    
                    # Real-time Status
                    if grid_manager.active:
                        self.realtime_grid_var.set(f"Active ({grid_status['active_levels']} levels)")
                    else:
                        self.realtime_grid_var.set("Inactive")
                    
                    if config.hg.enabled and self.hg_manager.active:
                        self.realtime_hg_var.set(f"Active ({hg_status['placed_hg_count']} positions)")
                    else:
                        self.realtime_hg_var.set("Inactive")
                    
                    # Current Price (Large Display)
                    if current_price > 0:
                        self.realtime_price_var.set(f"{current_price:.2f}")
                    
                    # Margin Usage (Progress Bar)
                    self.margin_progress_var.set(margin_usage)
                    self.margin_progress_label.config(text=f"{margin_usage:.1f}%")
                    
                    # เปลี่ยนสี progress bar ตาม margin usage
                    if hasattr(self, 'margin_progress'):
                        if margin_usage >= 80:
                            self.margin_progress_label.configure(foreground="red")
                        elif margin_usage >= 60:
                            self.margin_progress_label.configure(foreground="orange")
                        else:
                            self.margin_progress_label.configure(foreground="green")
                except Exception as e:
                    logger.debug(f"Error updating statistics: {e}")
            
            # แสดง warnings
            if summary['warnings']:
                for warning in summary['warnings']:
                    self.log_message(warning)
            
        except Exception as e:
            logger.error(f"Error updating display: {e}")


def run_gui():
    """ฟังก์ชันสำหรับรัน GUI"""
    root = tk.Tk()
    app = TradingGUI(root)
    root.mainloop()


if __name__ == "__main__":
    run_gui()

