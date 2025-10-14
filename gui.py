# gui.py
# ไฟล์สร้าง GUI Interface ด้วย tkinter

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import logging
from datetime import datetime
from mt5_connection import mt5_connection
from grid_manager import grid_manager
from hg_manager import hg_manager
from position_monitor import position_monitor
from config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TradingGUI:
    """คลาสหลักสำหรับ GUI Interface"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Grid Trading System with HG - XAUUSD")
        self.root.geometry("900x700")
        
        # สถานะระบบ
        self.is_running = False
        self.monitoring_thread = None
        self.stop_monitoring = False
        
        # สร้าง GUI components
        self.create_widgets()
        
        # โหลดการตั้งค่า
        self.load_settings_to_gui()
    
    def create_widgets(self):
        """สร้าง GUI components ทั้งหมด"""
        
        # ============ Frame หลัก ============
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # ============ Connection Status ============
        status_frame = ttk.LabelFrame(main_frame, text="📡 Connection Status", padding="10")
        status_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        self.connection_status = tk.StringVar(value="Disconnected")
        self.connection_color = tk.StringVar(value="red")
        
        ttk.Label(status_frame, text="Status:").grid(row=0, column=0, sticky=tk.W)
        status_label = ttk.Label(status_frame, textvariable=self.connection_status, 
                                foreground="red", font=("Arial", 10, "bold"))
        status_label.grid(row=0, column=1, sticky=tk.W, padx=5)
        
        ttk.Button(status_frame, text="Connect MT5", 
                  command=self.connect_mt5).grid(row=0, column=2, padx=5)
        ttk.Button(status_frame, text="Disconnect", 
                  command=self.disconnect_mt5).grid(row=0, column=3, padx=5)
        
        # ============ Grid Settings ============
        grid_frame = ttk.LabelFrame(main_frame, text="📊 Grid Settings", padding="10")
        grid_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N), pady=5, padx=(0, 5))
        
        # Grid Distance
        ttk.Label(grid_frame, text="Grid Distance (pips):").grid(row=0, column=0, sticky=tk.W, pady=3)
        self.grid_distance_var = tk.IntVar(value=200)
        ttk.Entry(grid_frame, textvariable=self.grid_distance_var, width=15).grid(row=0, column=1, pady=3)
        
        # Direction
        ttk.Label(grid_frame, text="Direction:").grid(row=1, column=0, sticky=tk.W, pady=3)
        self.direction_var = tk.StringVar(value="buy")
        direction_frame = ttk.Frame(grid_frame)
        direction_frame.grid(row=1, column=1, sticky=tk.W, pady=3)
        ttk.Radiobutton(direction_frame, text="Buy Only", variable=self.direction_var, 
                       value="buy").pack(side=tk.LEFT)
        ttk.Radiobutton(direction_frame, text="Sell Only", variable=self.direction_var, 
                       value="sell").pack(side=tk.LEFT)
        ttk.Radiobutton(direction_frame, text="Both", variable=self.direction_var, 
                       value="both").pack(side=tk.LEFT)
        
        # Lot Size (แสดงเป็น label)
        ttk.Label(grid_frame, text="Lot Size:").grid(row=2, column=0, sticky=tk.W, pady=3)
        self.lot_size_var = tk.DoubleVar(value=0.01)
        lot_frame = ttk.Frame(grid_frame)
        lot_frame.grid(row=2, column=1, sticky=tk.W, pady=3)
        ttk.Label(lot_frame, textvariable=self.lot_size_var, 
                 font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        ttk.Label(lot_frame, text=" lots", 
                 foreground="gray").pack(side=tk.LEFT)
        
        # Take Profit
        ttk.Label(grid_frame, text="Take Profit (pips):").grid(row=3, column=0, sticky=tk.W, pady=3)
        self.tp_var = tk.IntVar(value=100)
        ttk.Entry(grid_frame, textvariable=self.tp_var, width=15).grid(row=3, column=1, pady=3)
        
        # ============ HG Settings ============
        hg_frame = ttk.LabelFrame(main_frame, text="🛡️ HG Settings", padding="10")
        hg_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N), pady=5)
        
        # HG Distance
        ttk.Label(hg_frame, text="HG Distance (pips):").grid(row=0, column=0, sticky=tk.W, pady=3)
        self.hg_distance_var = tk.IntVar(value=2000)
        ttk.Entry(hg_frame, textvariable=self.hg_distance_var, width=15).grid(row=0, column=1, pady=3)
        
        # HG SL Trigger
        ttk.Label(hg_frame, text="HG SL Trigger (pips):").grid(row=1, column=0, sticky=tk.W, pady=3)
        self.hg_sl_trigger_var = tk.IntVar(value=1000)
        ttk.Entry(hg_frame, textvariable=self.hg_sl_trigger_var, width=15).grid(row=1, column=1, pady=3)
        
        # SL Buffer
        ttk.Label(hg_frame, text="SL Buffer (pips):").grid(row=2, column=0, sticky=tk.W, pady=3)
        self.sl_buffer_var = tk.IntVar(value=20)
        ttk.Entry(hg_frame, textvariable=self.sl_buffer_var, width=15).grid(row=2, column=1, pady=3)
        
        # HG Multiplier
        ttk.Label(hg_frame, text="HG Multiplier:").grid(row=3, column=0, sticky=tk.W, pady=3)
        self.hg_multiplier_var = tk.DoubleVar(value=1.2)
        ttk.Entry(hg_frame, textvariable=self.hg_multiplier_var, width=15).grid(row=3, column=1, pady=3)
        
        # ============ Controls ============
        control_frame = ttk.LabelFrame(main_frame, text="🎮 Controls", padding="10")
        control_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
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
        
        # ============ Status Display ============
        status_display_frame = ttk.LabelFrame(main_frame, text="📈 Status Display", padding="10")
        status_display_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
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
        
        # ============ Log Display ============
        log_frame = ttk.LabelFrame(main_frame, text="📝 Activity Log", padding="10")
        log_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, width=80, 
                                                  wrap=tk.WORD, font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # ตั้งค่า grid weights สำหรับ responsive
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)
        main_frame.rowconfigure(4, weight=1)
        
        # สไตล์ปุ่ม
        style = ttk.Style()
        style.configure("Start.TButton", foreground="green")
        style.configure("Emergency.TButton", foreground="red")
    
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
        
        if mt5_connection.connect_to_mt5():
            self.connection_status.set("Connected ✓")
            self.log_message("✓ Connected to MT5 successfully")
            
            # เปลี่ยนสีสถานะ
            for widget in self.root.winfo_children():
                self._update_label_color(widget, "green")
        else:
            self.connection_status.set("Connection Failed ✗")
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
        self.log_message("Disconnected from MT5")
    
    def save_settings(self):
        """บันทึกการตั้งค่า"""
        try:
            # อัพเดทค่าใน config
            config.update_grid_settings(
                grid_distance=self.grid_distance_var.get(),
                direction=self.direction_var.get(),
                lot_size=self.lot_size_var.get(),
                take_profit=self.tp_var.get()
            )
            
            config.update_hg_settings(
                hg_distance=self.hg_distance_var.get(),
                hg_sl_trigger=self.hg_sl_trigger_var.get(),
                sl_buffer=self.sl_buffer_var.get(),
                hg_multiplier=self.hg_multiplier_var.get()
            )
            
            # บันทึกลงไฟล์
            config.save_to_file()
            
            self.log_message("✓ Settings saved")
            messagebox.showinfo("Success", "Settings saved successfully!")
            
        except Exception as e:
            self.log_message(f"✗ Error saving settings: {e}")
            messagebox.showerror("Error", f"Failed to save settings: {e}")
    
    def load_settings_to_gui(self):
        """โหลดการตั้งค่าจาก config มาแสดงใน GUI"""
        self.grid_distance_var.set(config.grid.grid_distance)
        self.direction_var.set(config.grid.direction)
        self.lot_size_var.set(config.grid.lot_size)
        self.tp_var.set(config.grid.take_profit)
        
        self.hg_distance_var.set(config.hg.hg_distance)
        self.hg_sl_trigger_var.set(config.hg.hg_sl_trigger)
        self.sl_buffer_var.set(config.hg.sl_buffer)
        self.hg_multiplier_var.set(config.hg.hg_multiplier)
    
    def start_trading(self):
        """เริ่มต้นระบบเทรด"""
        if not mt5_connection.connected:
            messagebox.showerror("Error", "Please connect to MT5 first!")
            return
        
        # บันทึกการตั้งค่าก่อนเริ่ม
        self.save_settings()
        
        # ดึงราคาปัจจุบัน
        price_info = mt5_connection.get_current_price()
        if not price_info:
            messagebox.showerror("Error", "Cannot get current price!")
            return
        
        current_price = price_info['bid']
        
        # เริ่ม Grid System
        if grid_manager.start_grid_trading():
            self.log_message(f"✓ Grid Trading started at {current_price:.2f}")
        else:
            messagebox.showerror("Error", "Failed to start Grid Trading")
            return
        
        # เริ่ม HG System
        hg_manager.start_hg_system(current_price)
        self.log_message(f"✓ HG System started")
        
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
        response = messagebox.askyesno("Confirm", 
                                       "Stop trading?\n\nPositions will remain open.\nUse Emergency Stop to close all positions.")
        if not response:
            return
        
        self.is_running = False
        self.stop_monitoring = True
        
        grid_manager.stop_grid_trading(close_positions=False)
        hg_manager.stop_hg_system(close_positions=False)
        
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
        hg_manager.stop_hg_system(close_positions=False)
        
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        
        self.log_message(f"🛑 Emergency Stop: Closed {closed} positions")
        messagebox.showinfo("Emergency Stop", f"Closed {closed} positions")
    
    def refresh_status(self):
        """รีเฟรชสถานะทั้งหมด"""
        self.update_display()
        self.log_message("🔄 Status refreshed")
    
    def monitoring_loop(self):
        """
        Loop หลักสำหรับ monitoring ระบบ
        ทำงานใน background thread
        """
        while not self.stop_monitoring and self.is_running:
            try:
                # อัพเดท Grid
                grid_manager.update_grid_status()
                
                # อัพเดท HG
                hg_manager.manage_multiple_hg()
                
                # อัพเดท positions
                position_monitor.update_all_positions()
                
                # ตรวจสอบความเสี่ยง
                position_monitor.send_alerts()
                
                # อัพเดท GUI
                self.root.after(0, self.update_display)
                
                # รอ 1 วินาที
                threading.Event().wait(1.0)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                self.root.after(0, lambda: self.log_message(f"✗ Error: {e}"))
    
    def update_display(self):
        """อัพเดทการแสดงผลใน GUI"""
        try:
            # อัพเดท Grid status
            grid_status = grid_manager.get_grid_status()
            self.grid_levels_var.set(f"{grid_status['active_levels']} levels")
            
            # อัพเดท HG status
            hg_status = hg_manager.get_hg_status()
            self.hg_positions_var.set(f"{hg_status['total_hg']} positions")
            
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
            self.margin_var.set(f"{summary['margin_usage']:.1f}%")
            
            # Grid Exposure
            self.grid_exposure_var.set(f"{summary['grid_net_volume']:.2f} lots")
            
            # Current Price
            price_info = mt5_connection.get_current_price()
            if price_info:
                self.price_var.set(f"{price_info['bid']:.2f}")
            
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

