# คู่มือติดตั้งและเริ่มต้นใช้งาน Grid Trading System

## 📦 ติดตั้งแบบรวดเร็ว (Quick Install)

### สำหรับ Windows

1. **ติดตั้ง Python** (ถ้ายังไม่มี)
   - ดาวน์โหลดจาก https://www.python.org/downloads/
   - ติ๊กถูก "Add Python to PATH" ตอนติดตั้ง

2. **ติดตั้ง MetaTrader 5**
   - ดาวน์โหลดจาก https://www.metatrader5.com/
   - เปิด Demo Account

3. **ติดตั้งโปรแกรม**
   ```cmd
   cd GridTradingHG
   pip install -r requirements.txt
   ```

4. **รันโปรแกรม**
   ```cmd
   python main.py
   ```

### สำหรับ macOS

1. **ติดตั้ง Python** (ถ้ายังไม่มี)
   ```bash
   # ใช้ Homebrew
   brew install python
   ```

2. **ติดตั้ง MetaTrader 5**
   - ดาวน์โหลดจาก https://www.metatrader5.com/
   - เปิด Demo Account

3. **ติดตั้งโปรแกรม**
   ```bash
   cd GridTradingHG
   pip3 install -r requirements.txt
   ```

4. **รันโปรแกรม**
   ```bash
   python3 main.py
   ```

### สำหรับ Linux (Ubuntu/Debian)

1. **ติดตั้ง Python และ tkinter**
   ```bash
   sudo apt update
   sudo apt install python3 python3-pip python3-tk
   ```

2. **ติดตั้ง MetaTrader 5**
   - ใช้ Wine หรือ
   - ใช้ Windows VM

3. **ติดตั้งโปรแกรม**
   ```bash
   cd GridTradingHG
   pip3 install -r requirements.txt
   ```

4. **รันโปรแกรม**
   ```bash
   python3 main.py
   ```

## ✅ ตรวจสอบการติดตั้ง

รันคำสั่งนี้เพื่อตรวจสอบว่าติดตั้งครบถ้วน:

```bash
python -c "import MetaTrader5 as mt5; import tkinter as tk; print('✓ ติดตั้งสำเร็จ!')"
```

ถ้าไม่มี error แสดงว่าพร้อมใช้งาน!

## 🎮 การใช้งานครั้งแรก

### 1. เปิด MetaTrader 5
- เปิดโปรแกรม MT5
- Login เข้า **Demo Account**

### 2. ตั้งค่า MT5
1. ไปที่ `Tools > Options > Expert Advisors`
2. เปิดใช้งาน:
   - ✅ Allow algorithmic trading
   - ✅ Allow DLL imports
   - ✅ Allow WebRequest
3. คลิก OK

### 3. รันโปรแกรม
```bash
python main.py
```

### 4. เชื่อมต่อ MT5
- คลิกปุ่ม "Connect MT5" ใน GUI
- รอจนกว่าสถานะจะเป็น "Connected ✓"

### 5. เริ่มเทรด
- ตรวจสอบการตั้งค่า Grid และ HG
- คลิก "Save Settings" เพื่อบันทึก
- คลิก "▶ Start Trading"

## 🔧 แก้ไขปัญหาที่พบบ่อย

### ❌ ModuleNotFoundError: No module named 'MetaTrader5'

**วิธีแก้:**
```bash
pip install MetaTrader5
```

### ❌ ModuleNotFoundError: No module named '_tkinter'

**Windows:**
- ติดตั้ง Python ใหม่จาก python.org

**macOS:**
```bash
brew install python-tk
```

**Linux:**
```bash
sudo apt-get install python3-tk
```

### ❌ Cannot connect to MT5

**ตรวจสอบ:**
1. MT5 เปิดอยู่หรือไม่
2. Login อยู่ใน account หรือไม่
3. เปิด "Allow algorithmic trading" หรือยัง

### ❌ Orders ไม่ทำงาน

**ตรวจสอบ:**
1. ใช้ Demo Account (ห้ามใช้ Real Account)
2. XAUUSD มีใน Market Watch
3. Market เปิดอยู่
4. Margin เพียงพอ

## 📱 การอัพเดท

เมื่อมีเวอร์ชันใหม่:

```bash
cd GridTradingHG
git pull  # ถ้าใช้ git
pip install -r requirements.txt --upgrade
```

## 💾 Backup การตั้งค่า

ไฟล์สำคัญที่ควร backup:
- `settings.ini` - การตั้งค่าของคุณ

## 🆘 ขอความช่วยเหลือ

ถ้ายังมีปัญหา:

1. ดู `README.md` สำหรับข้อมูลละเอียด
2. ตรวจสอบไฟล์ `trading_bot.log`
3. ดู Activity Log ใน GUI

## ⚠️ คำเตือนสำคัญ

- ⚠️ **ใช้กับ DEMO Account เท่านั้น**
- ⚠️ **ห้ามใช้กับเงินจริงก่อนทดสอบ**
- ⚠️ **ติดตามสถานะอยู่เสมอ**
- ⚠️ **ต้องมี internet ตลอดเวลา**

---

## 🎯 เริ่มต้นเลย!

```bash
# 1. เปิด MT5
# 2. Login Demo Account
# 3. รันคำสั่ง:
python main.py
```

**Happy Trading! 🚀**

