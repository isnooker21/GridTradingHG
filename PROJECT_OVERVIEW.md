# Grid Trading System with HG - Project Overview

## 📊 ภาพรวมโปรเจค

ระบบเทรด Grid แบบอัตโนมัติพร้อม Hedge (HG) สำหรับ XAUUSD บน MetaTrader 5

```
┌─────────────────────────────────────────────────────────────┐
│          Grid Trading System with HG - XAUUSD              │
│                    DEMO Trading Only                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
         ┌────────────────────────────────────┐
         │           main.py                  │
         │   (Entry Point & Logging)          │
         └────────────────────────────────────┘
                              │
                              ▼
         ┌────────────────────────────────────┐
         │           gui.py                   │
         │   (User Interface - tkinter)       │
         └────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
              ▼               ▼               ▼
    ┌─────────────┐  ┌──────────────┐  ┌──────────────┐
    │grid_manager │  │ hg_manager   │  │position_     │
    │    .py      │  │    .py       │  │monitor.py    │
    └─────────────┘  └──────────────┘  └──────────────┘
              │               │               │
              └───────────────┼───────────────┘
                              │
                              ▼
                   ┌──────────────────┐
                   │ mt5_connection   │
                   │      .py         │
                   │ (MT5 API Calls)  │
                   └──────────────────┘
                              │
                              ▼
                   ┌──────────────────┐
                   │   config.py      │
                   │  (Settings)      │
                   └──────────────────┘
                              │
                              ▼
                      [settings.ini]
```

## 🗂️ โครงสร้างไฟล์

### Core Files (ไฟล์หลัก)

| ไฟล์ | บรรทัด | หน้าที่ |
|------|--------|---------|
| `main.py` | ~60 | จุดเริ่มต้นโปรแกรม, logging setup |
| `gui.py` | ~600+ | User Interface, แสดงผลและรับ input |
| `config.py` | ~200 | จัดการการตั้งค่า, load/save settings |
| `mt5_connection.py` | ~400 | เชื่อมต่อ MT5, ส่งคำสั่ง buy/sell |
| `grid_manager.py` | ~300 | ระบบ Grid Trading |
| `hg_manager.py` | ~350 | ระบบ Hedge (HG) |
| `position_monitor.py` | ~300 | ติดตาม positions, P&L, margin |

### Configuration Files (ไฟล์การตั้งค่า)

| ไฟล์ | หน้าที่ |
|------|---------|
| `settings.ini` | ไฟล์การตั้งค่าหลัก (ถูกสร้างจาก GUI) |
| `requirements.txt` | Dependencies ที่ต้องติดตั้ง |

### Documentation Files (เอกสาร)

| ไฟล์ | หน้าที่ |
|------|---------|
| `README.md` | คู่มือใช้งานฉบับเต็ม (ภาษาไทย) |
| `INSTALL.md` | คู่มือติดตั้งแบบละเอียด |
| `PROJECT_OVERVIEW.md` | เอกสารนี้ - ภาพรวมโปรเจค |

## 🔄 Flow การทำงาน

### 1. การเริ่มต้นโปรแกรม

```
User runs main.py
    │
    ├─> Initialize logging
    ├─> Load config from settings.ini
    └─> Launch GUI (gui.py)
```

### 2. การเชื่อมต่อ MT5

```
User clicks "Connect MT5"
    │
    ├─> mt5_connection.connect_to_mt5()
    ├─> Check MT5 running
    ├─> Verify XAUUSD symbol
    └─> Display connection status
```

### 3. การเริ่ม Trading

```
User clicks "Start Trading"
    │
    ├─> Save current settings
    ├─> Get current price
    │
    ├─> grid_manager.start_grid_trading()
    │   ├─> Calculate grid levels
    │   └─> Monitor price for grid triggers
    │
    ├─> hg_manager.start_hg_system()
    │   ├─> Monitor for HG triggers
    │   └─> Calculate HG lot sizes
    │
    └─> Start monitoring_loop()
        ├─> Update positions every 1 sec
        ├─> Check TP/SL conditions
        ├─> Monitor risk limits
        └─> Update GUI display
```

### 4. Grid Trading Logic

```
Price reaches Grid Level
    │
    ├─> Place market order (buy/sell)
    ├─> Set Take Profit (+100 pips)
    └─> Monitor position
        │
        └─> Position hits TP
            ├─> MT5 closes automatically
            └─> Reset grid level (ready for new order)
```

### 5. HG System Logic

```
Price moves 2000 pips from start
    │
    ├─> Calculate Grid Exposure
    ├─> Calculate HG Lot = Exposure × 1.2
    ├─> Place HG order (opposite direction)
    └─> Monitor HG profit
        │
        └─> HG profits 1000 pips
            ├─> Set SL to breakeven (+20 pips buffer)
            └─> Continue monitoring
```

## 🎯 Key Functions (ฟังก์ชันสำคัญ)

### mt5_connection.py
```python
connect_to_mt5()          # เชื่อมต่อ MT5
get_current_price()       # ดึงราคา XAUUSD
place_order()             # วาง Buy/Sell order
modify_order()            # แก้ไข SL/TP
close_order()             # ปิด position
get_all_positions()       # ดึงข้อมูล positions ทั้งหมด
close_all_positions()     # Emergency stop
```

### grid_manager.py
```python
calculate_grid_levels()   # คำนวณตำแหน่ง Grid
monitor_grid_levels()     # ตรวจสอบและวาง Grid
monitor_grid_tp()         # ตรวจสอบ TP
update_grid_status()      # อัพเดทสถานะทั้งหมด
```

### hg_manager.py
```python
check_hg_trigger()        # ตรวจสอบเงื่อนไขวาง HG
calculate_hg_lot()        # คำนวณ HG lot size
place_hg_order()          # วาง HG order
monitor_hg_profit()       # ติดตาม profit
set_hg_breakeven_sl()     # ตั้ง SL breakeven
manage_multiple_hg()      # จัดการ HG หลายระดับ
```

### position_monitor.py
```python
update_all_positions()    # อัพเดท positions จาก MT5
calculate_total_pnl()     # คำนวณกำไร/ขาดทุน
get_net_grid_exposure()   # คำนวณ Grid exposure
check_margin_usage()      # ตรวจสอบ margin
monitor_risk_limits()     # ตรวจสอบความเสี่ยง
```

### gui.py
```python
create_widgets()          # สร้าง GUI components
start_trading()           # เริ่มระบบเทรด
stop_trading()            # หยุดระบบเทรด
emergency_stop()          # ปิด positions ทั้งหมด
monitoring_loop()         # Loop อัพเดทสถานะ
update_display()          # อัพเดท GUI real-time
```

## 📐 การออกแบบระบบ

### Modular Design (แยกหน้าที่ชัดเจน)

```
┌─────────────────────────────────────────────┐
│  Presentation Layer (gui.py)                │
│  - User Interface                           │
│  - Display Data                             │
└─────────────────────────────────────────────┘
                    │
┌─────────────────────────────────────────────┐
│  Business Logic Layer                       │
│  - grid_manager.py                          │
│  - hg_manager.py                           │
│  - position_monitor.py                      │
└─────────────────────────────────────────────┘
                    │
┌─────────────────────────────────────────────┐
│  Data Access Layer (mt5_connection.py)      │
│  - MT5 API Calls                            │
│  - Order Management                         │
└─────────────────────────────────────────────┘
                    │
┌─────────────────────────────────────────────┐
│  Configuration Layer (config.py)            │
│  - Settings Management                      │
│  - Data Classes                             │
└─────────────────────────────────────────────┘
```

### Thread Management

```
Main Thread (GUI)
    │
    └─> monitoring_thread (Background)
        ├─> Updates every 1 second
        ├─> Non-blocking
        └─> Updates GUI via root.after()
```

## 🔐 การจัดการความปลอดภัย

### Magic Number System
- แต่ละ bot ใช้ magic number เฉพาะ (123456)
- แยก orders ของ bot จาก manual orders
- ป้องกันการปิด orders ผิด

### Comment System
- Grid orders: "GridBot_..."
- HG orders: "HG_..."
- ติดตามและจัดการแยกกันได้

### Risk Controls
- Max Margin Usage: 80%
- Max Drawdown: $1000
- Real-time monitoring
- Alert system

## 📈 การคำนวณ

### Grid Calculations

```python
# Grid Level Price
level_price = current_price ± (grid_distance × pip_value × level_number)

# Take Profit
tp_price = entry_price ± (take_profit × pip_value)

# For XAUUSD: 1 pip = 0.1
# Example: 200 pips = 20.0 price units
```

### HG Calculations

```python
# Grid Exposure
net_volume = |buy_volume - sell_volume|

# HG Lot Size
hg_lot = net_volume × hg_multiplier (default 1.2)

# Breakeven SL
sl_price = entry_price ± (sl_buffer × pip_value)
```

## 🎨 GUI Layout

```
┌─────────────────────────────────────────────────────┐
│  📡 Connection Status                               │
│  [Connect MT5] [Disconnect]                         │
├──────────────────────┬──────────────────────────────┤
│  📊 Grid Settings    │  🛡️ HG Settings              │
│  - Distance          │  - HG Distance                │
│  - Direction         │  - SL Trigger                 │
│  - Lot Size          │  - SL Buffer                  │
│  - Take Profit       │  - Multiplier                 │
├──────────────────────┴──────────────────────────────┤
│  🎮 Controls                                        │
│  [▶ Start] [⏸ Stop] [🛑 Emergency] [💾 Save]       │
├─────────────────────────────────────────────────────┤
│  📈 Status Display                                  │
│  Grid Levels: X  │  Total P&L: $XXX                 │
│  HG Positions: X │  Margin: XX%                     │
├─────────────────────────────────────────────────────┤
│  📝 Activity Log                                    │
│  [Scrollable log area]                              │
└─────────────────────────────────────────────────────┘
```

## 🛠️ Dependencies

```
MetaTrader5 >= 5.0.45  # MT5 Python API
tkinter                 # GUI (built-in)
configparser           # Config files (built-in)
threading              # Background tasks (built-in)
logging                # Logging system (built-in)
```

## 📝 Logging System

### Log Levels
- INFO: การทำงานปกติ
- WARNING: การแจ้งเตือนความเสี่ยง
- ERROR: ข้อผิดพลาด

### Log Destinations
- `trading_bot.log` (file)
- Console output
- GUI Activity Log

## 🎓 สำหรับนักพัฒนา

### การเพิ่มฟีเจอร์ใหม่

1. **เพิ่มการตั้งค่าใหม่**
   - แก้ไข `config.py` (เพิ่ม dataclass field)
   - แก้ไข `gui.py` (เพิ่ม GUI widget)
   - แก้ไข `settings.ini` (เพิ่มค่า default)

2. **เพิ่ม Trading Strategy**
   - สร้างไฟล์ใหม่ เช่น `strategy_manager.py`
   - Import และใช้ `mt5_connection` สำหรับ orders
   - เรียกใช้ใน `monitoring_loop()`

3. **เพิ่ม Indicator**
   - สร้างฟังก์ชันใน `position_monitor.py`
   - แสดงผลใน `gui.py`

### Code Style
- Thai comments สำหรับอธิบายฟังก์ชัน
- Type hints สำหรับ parameters
- Docstrings สำหรับ functions
- Logging สำหรับ important events

## 📊 Performance

### Update Frequency
- Position monitoring: 1 second
- GUI updates: 1 second (after monitoring)
- Price updates: Real-time from MT5

### Resource Usage
- CPU: Low (< 5% on modern systems)
- Memory: ~50-100 MB
- Network: Minimal (MT5 connection only)

## 🔮 Future Enhancements

- [ ] Multiple symbol support
- [ ] Advanced TP/SL strategies
- [ ] Performance analytics
- [ ] Trade history export
- [ ] Email/SMS notifications
- [ ] Cloud backup settings
- [ ] Mobile app companion

---

**Version:** 1.0  
**Last Updated:** October 2025  
**Total Lines of Code:** ~2,500+  
**Files:** 10 Python files + 3 Documentation files

