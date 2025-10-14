# Grid Trading System with Hedge (HG) for XAUUSD

ระบบเทรด Grid แบบอัตโนมัติพร้อม Hedge (HG) สำหรับ XAUUSD บน MetaTrader 5

## 📋 คุณสมบัติ

### Grid Trading System
- วาง Grid orders อัตโนมัติตามระยะที่กำหนด (default: 200 pips)
- รองรับการเทรด 3 แบบ: Buy Only, Sell Only, หรือ Both
- ปิด position อัตโนมัติเมื่อถึง Take Profit
- ติดตาม Grid levels แบบ real-time

### Hedge (HG) System
- วาง HG อัตโนมัติทุกๆ 2000 pips (ปรับได้)
- คำนวณ HG lot size อัตโนมัติ: `HG Lot = Grid Exposure × 1.2`
- ตั้ง Stop Loss แบบ breakeven เมื่อ HG กำไรถึง 1000 pips
- รองรับ HG หลายระดับ

### Risk Management
- แสดง P&L แบบ real-time
- ติดตาม Margin Usage
- แจ้งเตือนเมื่อเกินขีดจำกัดความเสี่ยง
- Emergency Stop สำหรับปิด positions ทั้งหมด

### GUI Interface
- Interface ที่ใช้งานง่ายด้วย tkinter
- แสดงสถานะระบบแบบ real-time
- Activity log สำหรับติดตามการทำงาน
- ปรับการตั้งค่าได้ง่าย

## 🚀 การติดตั้ง

### ความต้องการของระบบ
- Python 3.8 หรือสูงกว่า
- MetaTrader 5
- Windows, macOS, หรือ Linux

### ขั้นตอนการติดตั้ง

1. **Clone หรือ Download โปรเจค**
```bash
# หรือ download ZIP แล้ว extract
```

2. **ติดตั้ง Dependencies**
```bash
cd GridTradingHG
pip install -r requirements.txt
```

หมายเหตุ: สำหรับ macOS/Linux อาจต้องใช้ `pip3` แทน `pip`

3. **ติดตั้ง tkinter (ถ้ายังไม่มี)**

tkinter มักมาพร้อมกับ Python แล้ว แต่ถ้าไม่มี:

**Ubuntu/Debian:**
```bash
sudo apt-get install python3-tk
```

**macOS:**
- tkinter มาพร้อมกับ Python จาก python.org

**Windows:**
- tkinter มาพร้อมกับ Python installer

4. **ตรวจสอบการติดตั้ง**
```bash
python -c "import MetaTrader5; import tkinter; print('All dependencies OK!')"
```

## ⚙️ การตั้งค่า

### 1. ตั้งค่า MetaTrader 5

1. เปิด MetaTrader 5
2. Login เข้า **DEMO Account**
3. ไปที่ `Tools > Options > Expert Advisors`
4. เปิดใช้งาน:
   - ✅ Allow algorithmic trading
   - ✅ Allow DLL imports
   - ✅ Allow WebRequest

### 2. ตั้งค่าโปรแกรม

แก้ไขไฟล์ `settings.ini` ตามต้องการ:

```ini
[Grid]
grid_distance = 200      # ระยะห่าง Grid (pips)
direction = buy          # buy, sell, both
lot_size = 0.01          # ขนาด lot ต่อ Grid
take_profit = 100        # TP (pips)

[HG]
hg_distance = 2000       # ระยะห่าง HG (pips)
hg_sl_trigger = 1000     # ระยะตั้ง SL breakeven (pips)
sl_buffer = 20           # Buffer สำหรับ SL (pips)
hg_multiplier = 1.2      # ตัวคูณ HG lot

[Risk]
max_margin_usage = 80.0  # Margin สูงสุด (%)
max_drawdown = 1000.0    # Drawdown สูงสุด ($)
```

## 🎮 วิธีใช้งาน

### การรันโปรแกรม

```bash
python main.py
```

### ขั้นตอนการใช้งาน

1. **เชื่อมต่อ MT5**
   - คลิก "Connect MT5"
   - ตรวจสอบว่าสถานะเป็น "Connected ✓"

2. **ตั้งค่าการเทรด**
   - ปรับค่า Grid Settings ตามต้องการ
   - ปรับค่า HG Settings ตามต้องการ
   - คลิก "Save Settings" เพื่อบันทึก

3. **เริ่มเทรด**
   - คลิก "▶ Start Trading"
   - ระบบจะเริ่มวาง Grid และติดตาม HG อัตโนมัติ

4. **ติดตามสถานะ**
   - ดู Active Grid Levels
   - ดู Active HG Positions
   - ติดตาม Total P&L และ Margin Usage
   - ตรวจสอบ Activity Log

5. **หยุดเทรด**
   - **Stop Trading**: หยุดวาง orders ใหม่ (positions เดิมยังเปิดอยู่)
   - **Emergency Stop**: ปิด positions ทั้งหมดทันที

## 📁 โครงสร้างโปรเจค

```
GridTradingHG/
│
├── main.py                 # ไฟล์หลักสำหรับรันโปรแกรม
├── gui.py                  # GUI Interface
├── config.py               # การจัดการ configuration
├── mt5_connection.py       # การเชื่อมต่อและคำสั่ง MT5
├── grid_manager.py         # ระบบ Grid Trading
├── hg_manager.py          # ระบบ Hedge (HG)
├── position_monitor.py     # ติดตาม positions และ P&L
│
├── settings.ini            # ไฟล์การตั้งค่า (สร้างอัตโนมัติ)
├── requirements.txt        # Dependencies
├── README.md              # เอกสารนี้
└── trading_bot.log        # Log file (สร้างอัตโนมัติ)
```

## 🔧 การทำงานของระบบ

### Grid System

1. คำนวณ Grid levels จากราคาเริ่มต้น
2. วาง Grid orders เมื่อราคาถึงแต่ละ level
3. ตั้ง Take Profit สำหรับแต่ละ Grid
4. ปิด position อัตโนมัติเมื่อถึง TP
5. วาง Grid ใหม่ที่ level เดิมเมื่อ Grid ถูกปิด

### HG System

1. ตรวจสอบว่าราคาเคลื่อนที่ถึงระยะ HG (2000 pips) หรือยัง
2. คำนวณ Grid Exposure รวม
3. คำนวณ HG lot: `HG Lot = Grid Exposure × 1.2`
4. วาง HG order ตรงข้ามกับ Grid exposure
5. ติดตามกำไรของ HG
6. เมื่อ HG กำไร 1000 pips → ตั้ง SL breakeven (+ buffer)
7. รองรับ HG หลายระดับ

### Risk Management

- ตรวจสอบ Margin Usage real-time
- แจ้งเตือนเมื่อเกิน 80%
- ตรวจสอบ Drawdown
- แจ้งเตือนเมื่อขาดทุนเกินกำหนด

## ⚠️ ข้อควรระวัง

1. **ใช้กับ DEMO Account เท่านั้น**
   - ระบบนี้ออกแบบสำหรับ demo trading
   - ทดสอบให้มั่นใจก่อนใช้กับ real account

2. **ตรวจสอบการตั้งค่า**
   - ตรวจสอบ lot size ให้เหมาะสมกับ account balance
   - ตรวจสอบ margin requirement

3. **เน็ตเวิร์ค**
   - ต้องมี internet connection ตลอดเวลา
   - MT5 ต้องเปิดอยู่ตลอดเวลา

4. **Margin**
   - Grid trading ใช้ margin สูง
   - ตรวจสอบ margin level สม่ำเสมอ

5. **Market Conditions**
   - ระบบทำงานได้ดีในตลาด ranging
   - ระวังในตลาด strong trend

## 🐛 การแก้ไขปัญหา

### ไม่สามารถเชื่อมต่อ MT5

```python
# ตรวจสอบว่า MT5 เปิดอยู่
# ตรวจสอบว่า login อยู่ใน account
# ตรวจสอบการตั้งค่า Expert Advisors
```

### Import Error

```bash
# ติดตั้ง dependencies ใหม่
pip install --upgrade -r requirements.txt
```

### GUI ไม่แสดง

```bash
# ตรวจสอบ tkinter
python -m tkinter

# ถ้าไม่ได้ ให้ติดตั้ง tkinter
# Ubuntu: sudo apt-get install python3-tk
```

### Orders ไม่ทำงาน

```python
# ตรวจสอบ:
# 1. Account เป็น Demo
# 2. Symbol XAUUSD มีอยู่
# 3. Market เปิดอยู่
# 4. Margin เพียงพอ
# 5. Allow algorithmic trading เปิดอยู่
```

## 📊 ตัวอย่างการตั้งค่า

### Conservative (ระมัดระวัง)
```ini
grid_distance = 300
lot_size = 0.01
hg_distance = 3000
max_margin_usage = 60.0
```

### Moderate (ปานกลาง)
```ini
grid_distance = 200
lot_size = 0.01
hg_distance = 2000
max_margin_usage = 70.0
```

### Aggressive (ก้าวร้าว)
```ini
grid_distance = 100
lot_size = 0.02
hg_distance = 1000
max_margin_usage = 80.0
```

## 📝 Log Files

โปรแกรมจะสร้างไฟล์ log อัตโนมัติ:

- `trading_bot.log` - บันทึกการทำงานของระบบ
- สามารถเปิดดูเพื่อ debug ได้

## 🔐 ความปลอดภัย

- โปรแกรมไม่เก็บ password
- ใช้ Magic Number เพื่อแยก orders
- ทำงานเฉพาะกับ account ที่ login อยู่ใน MT5

## 📞 Support

หากพบปัญหาหรือมีคำถาม:

1. ตรวจสอบ README.md (ไฟล์นี้)
2. ดู log file (`trading_bot.log`)
3. ตรวจสอบ Activity Log ใน GUI

## ⚖️ Disclaimer

**คำเตือน:** 
- ระบบนี้เป็นเพียงเครื่องมือช่วยในการเทรด
- ผู้ใช้ต้องรับผิดชอบความเสี่ยงเอง
- แนะนำให้ทดสอบบน demo account อย่างเต็มที่ก่อนใช้จริง
- การเทรด forex และ gold มีความเสี่ยงสูง

## 📜 License

โปรเจคนี้เป็น open source สำหรับการศึกษาและพัฒนา

---

## 🎯 Quick Start

```bash
# 1. ติดตั้ง
pip install -r requirements.txt

# 2. เปิด MT5 และ login demo account

# 3. รันโปรแกรม
python main.py

# 4. คลิก "Connect MT5"

# 5. ตั้งค่าและคลิก "Start Trading"
```

---

**สร้างโดย:** Grid Trading Bot Development Team  
**เวอร์ชัน:** 1.0  
**อัพเดทล่าสุด:** October 2025

