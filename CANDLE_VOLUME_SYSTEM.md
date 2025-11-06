# 🚀 CANDLE + VOLUME DETECTION SYSTEM

## ✅ สิ่งที่เปลี่ยนแปลง

### ❌ ระบบเดิม (EMA Trend Detection)
- ใช้ EMA(20) และ EMA(50)
- ตรวจจับ Trend แบบ Crossover
- ไฟล์: `trend_detector.py` → **ลบทิ้งแล้ว**

### ✅ ระบบใหม่ (Candle + Volume Detection)
- ใช้ **แท่งเทียนที่ปิดแล้ว** (Closed Candle)
- ใช้ **Volume** เทียบกับ Volume MA(20)
- ไฟล์: `candle_volume_detector.py` → **สร้างใหม่**

---

## 📊 Detection Logic

### 1. วิเคราะห์แท่งเทียน (Candle Analysis)

**ประเภทแท่ง:**
- **BULLISH:** Close > Open (แท่งเขียว)
- **BEARISH:** Close < Open (แท่งแดง)
- **DOJI:** Close = Open (แท่งกากบาท)

**ความแข็งแรง (Strength):**
```python
Body Ratio = Body Size / Full Range

STRONG:   Body Ratio >= 70%  (ตัวเทียนใหญ่)
MODERATE: Body Ratio 40-70%  (ตัวเทียนปานกลาง)
WEAK:     Body Ratio < 40%   (ตัวเทียนเล็ก, หางยาว)
```

### 2. วิเคราะห์ Volume (Volume Analysis)

**Volume Levels:**
```python
Volume Ratio = Current Volume / Volume MA(20)

VERY HIGH:  Ratio >= 2.0x
HIGH:       Ratio >= 1.5x
MODERATE:   Ratio >= 1.2x
LOW:        Ratio < 1.2x
```

### 3. ตัดสินใจทิศทาง (Direction Decision)

**🟢 BUY Signal (HIGH Confidence):**
```
✅ Bullish Candle (STRONG/MODERATE)
✅ Volume VERY HIGH หรือ HIGH
→ Direction = "buy"
```

**🔴 SELL Signal (HIGH Confidence):**
```
✅ Bearish Candle (STRONG/MODERATE)
✅ Volume VERY HIGH หรือ HIGH
→ Direction = "sell"
```

**🔵 BOTH Signal (MODERATE Confidence):**
```
⚠️ Bullish/Bearish + Volume MODERATE
→ Direction = "buy"/"sell" (MODERATE)
```

**⚪ BOTH Signal (LOW Confidence):**
```
❌ WEAK Candle
❌ LOW Volume
❌ DOJI
→ Direction = "both"
```

---

## 🎯 ตัวอย่างการทำงาน

### Example 1: Strong BUY Signal

```
Last Closed Candle:
├─ Open:  2645.50
├─ Close: 2652.80  (+7.30 = 73 pips) 🟢
├─ High:  2653.00
├─ Low:   2645.00
└─ Range: 8.00 (80 pips)

Body = 73 pips / 80 pips = 91% → STRONG

Volume:
├─ Current: 2,500
├─ MA(20):  1,200
└─ Ratio:   2.08x → VERY HIGH

Result:
→ Direction: BUY (HIGH)
→ Reason: Bullish Candle (73.0p) + VERY HIGH Vol (2.08x)
```

### Example 2: Weak Signal (Sideways)

```
Last Closed Candle:
├─ Open:  2650.00
├─ Close: 2651.50  (+1.50 = 15 pips)
├─ High:  2655.00
├─ Low:   2648.00
└─ Range: 7.00 (70 pips)

Body = 15 pips / 70 pips = 21% → WEAK

Volume:
├─ Current: 950
├─ MA(20):  1,200
└─ Ratio:   0.79x → LOW

Result:
→ Direction: BOTH (LOW)
→ Reason: Weak: BULLISH WEAK + LOW Vol
```

---

## 🔧 ไฟล์ที่เปลี่ยนแปลง

### 1. ❌ ลบไฟล์
- `trend_detector.py` → **ลบทิ้งแล้ว**

### 2. ✅ สร้างไฟล์ใหม่
- `candle_volume_detector.py` → **ระบบตรวจจับใหม่**

### 3. ✅ แก้ไขไฟล์เดิม

**`config.py`:**
```python
comment_auto: str = "Full_AutoAI"  # 🆕 Comment สำหรับ Auto Mode
```

**`auto_config_manager.py`:**
```python
# เปลี่ยนจาก:
from trend_detector import trend_detector

# เป็น:
from candle_volume_detector import candle_volume_detector
```

**`grid_manager.py`:**
```python
# เปลี่ยน comment ตาม mode
comment = config.mt5.comment_auto if config.grid.auto_mode else config.mt5.comment_grid

# แก้ไข recovery logic
# Manual Mode: เฉพาะ "both"
# Auto Mode: ทุก direction (buy/sell/both)
```

**`hg_manager.py`:**
```python
# เปลี่ยน comment ตาม mode
comment = config.mt5.comment_auto if config.grid.auto_mode else config.mt5.comment_hg
```

**`gui.py`:**
```python
# เปลี่ยน UI จาก EMA → Candle + Volume
Direction:    BUY (HIGH)         # แทน Trend
ATR(14):      85.3 pips
Candle:       BULLISH (STRONG)   # 🆕 แทน EMA(20)
Volume:       VERY HIGH (2.08x)  # 🆕 แทน EMA(50)
Size:         73.0 pips          # 🆕
Vol Ratio:    2.08x              # 🆕
```

---

## 🎮 การใช้งาน

### 1. เปิด Auto Mode
```
1. Connect MT5
2. เลือก 🤖 Full Auto Mode
3. เลือก Risk Profile
4. กด 🔄 Refresh Analysis
```

### 2. ดูข้อมูล Market Analysis
```
Direction:    BUY (HIGH)          ← ทิศทางที่แนะนำ
ATR(14):      85.3 pips           ← ความผันผวน
Candle:       BULLISH (STRONG)    ← แท่งเทียนล่าสุด
Volume:       VERY HIGH (2.08x)   ← ระดับ Volume
Size:         73.0 pips           ← ขนาดแท่งเทียน
Vol Ratio:    2.08x               ← Volume เทียบค่าเฉลี่ย
```

### 3. ระบบจะวางไม้ตาม Direction
- **Direction = BUY** → วางแค่ Buy orders (comment: Full_AutoAI)
- **Direction = SELL** → วางแค่ Sell orders (comment: Full_AutoAI)
- **Direction = BOTH** → วางทั้ง Buy และ Sell (comment: Full_AutoAI)

### 4. ระบบจะแก้ไม้อัตโนมัติ
- **BUY Mode + ราคาลง** → วาง Buy เพิ่ม (เฉลี่ยราคา)
- **SELL Mode + ราคาขึ้น** → วาง Sell เพิ่ม (เฉลี่ยราคา)
- **BOTH Mode** → แก้ไม้ทั้ง 2 ฝั่ง

---

## 📈 ตัวอย่างสถานการณ์

### Scenario 1: Bullish Market (Strong BUY Signal)

**Market Condition:**
```
แท่งเทียนล่าสุด: BULLISH (STRONG) - 73 pips
Volume: VERY HIGH (2.08x)
ATR: 85 pips
```

**Auto Mode Decision:**
```
Direction: BUY (HIGH Confidence)
Grid Distance: 85 pips
HG Distance: 255 pips
```

**การทำงาน:**
```
1. วางแค่ Buy orders
2. ไม่วาง Sell (เพราะ signal แนะนำ BUY)
3. ถ้าราคาลง → วาง Buy เพิ่ม (recovery)
4. HG Sell @ -255 pips เพื่อป้องกัน
```

### Scenario 2: Weak Signal (Sideways)

**Market Condition:**
```
แท่งเทียนล่าสุด: DOJI (WEAK) - 15 pips
Volume: LOW (0.79x)
ATR: 45 pips
```

**Auto Mode Decision:**
```
Direction: BOTH (LOW Confidence)
Grid Distance: 45 pips
HG Distance: 135 pips
```

**การทำงาน:**
```
1. วางทั้ง Buy และ Sell
2. ตลาดไม่ชัด ให้วางครบทั้ง 2 ฝั่ง
3. รอให้ตลาดชัดเจนขึ้นในรอบถัดไป (15 นาที)
```

---

## ⚙️ Technical Details

### Cache System:
- **Candle + Volume Analysis:** cache 60 วินาที
- **ATR Calculation:** cache 60 วินาที
- ลด MT5 API calls → เร็วขึ้น

### Update Frequency:
- **Auto Settings:** ทุก 15 นาที
- **UI Display (Light):** ทุก 60 วินาที
- **Survivability:** On-demand (กดปุ่ม Refresh)

### Timeframe:
- **M15** สำหรับทั้ง Candle และ Volume analysis

---

## ⚠️ ข้อควรระวัง

### 1. Market Conditions
- ตลาด **ผันผวนสูง** + **Volume สูง** → Signal ชัดเจน
- ตลาด **เงียบ** + **Volume ต่ำ** → Signal อ่อน (both)

### 2. False Signals
- แท่งเทียนเดี่ยวอาจไม่แม่นเสมอ
- ระบบจะปรับทุก 15 นาที ตามแท่งใหม่

### 3. Recovery System
- ✅ ทำงานทุก direction ใน Auto Mode
- ✅ ป้องกัน drawdown มากเกินไป

---

## 📝 Comparison: EMA vs Candle+Volume

| Feature | EMA System (เก่า) | Candle+Volume (ใหม่) |
|---------|-------------------|----------------------|
| **Input** | EMA(20), EMA(50) | Last Candle + Volume |
| **Speed** | ช้า (คำนวณ EMA 2 ครั้ง) | เร็ว (อ่านแท่งเดียว) |
| **Reaction** | ช้า (ใช้ข้อมูลหลายแท่ง) | เร็ว (อ่านแท่งปิดล่าสุด) |
| **Signal** | Smooth (ช้า) | Sharp (เร็ว) |
| **Volume** | ❌ ไม่ใช้ | ✅ ใช้ |
| **Recovery** | ❌ เฉพาะ "both" | ✅ ทุก direction |
| **Comment** | Grid_AI | Full_AutoAI |

---

## 🎯 สรุป

### ✅ ข้อดีของระบบใหม่
1. ✅ **เร็วกว่า** - อ่านแท่งเดียวแทนคำนวณ EMA
2. ✅ **ตอบสนองเร็ว** - ใช้แท่งปิดล่าสุด
3. ✅ **มี Volume** - เพิ่มความมั่นใจ
4. ✅ **แก้ไม้ทุก direction** - ไม่เฉพาะ "both"
5. ✅ **Comment ชัดเจน** - "Full_AutoAI"
6. ✅ **UI กระชับ** - 2 columns, ใช้พื้นที่ดี

### ⚠️ ข้อควรระวัง
1. ⚠️ Signal เร็ว = เปลี่ยนถี่
2. ⚠️ False signal เป็นไปได้
3. ⚠️ ควรใช้กับ Risk Profile ที่เหมาะสม

---

## 🚀 พร้อมใช้งาน!

```bash
python main.py
# หรือ
python gui.py
```

**Features:**
- ✅ Candle + Volume Detection
- ✅ Auto Mode Comment: Full_AutoAI
- ✅ Recovery ทุก direction
- ✅ UI กระชับเหมาะสม
- ✅ Performance Optimized

---

**Updated:** 2025-11-06
**Version:** 2.0 (Candle + Volume System)

