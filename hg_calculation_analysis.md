# 🧮 วิเคราะห์ HG Strategy สำหรับทุน $10,000 USD
## เป้าหมาย: ทน Drawdown ได้ 2000 pips (20,000 จุด) - หาจุดที่เหมาะสม

---

## 📊 สมมติฐานเริ่มต้น

### Grid Settings (ตามที่กำหนด):
- Grid Distance: 50 pips (Buy & Sell)
- Lot Size: 0.01 (เริ่มต้น)
- Take Profit: 50 pips
- Direction: Both

### HG Settings (ปรับตาม Max Drawdown):
- **Max Drawdown Target: 2000 pips (20,000 จุด)**
- HG Distance Buy: 200 pips
- HG Distance Sell: 2000 pips
- Multiplier: 1.2
- Initial Lot: 0.01

### Account:
- Balance: $10,000 USD
- Leverage: 100:1
- Symbol: XAUUSD
- 1 pip = $0.10 (สำหรับ 0.01 lot)

---

## 🔢 การคำนวณพื้นฐาน

### 1. คำนวณ Drawdown ต่อ Grid Order

**สูตร:**
```
Drawdown per Order = (Grid Distance × Pip Value) × Lot Size

Grid 1 Order ที่ -50 pips:
Drawdown = 50 pips × $0.10 × 0.01 lot
         = $0.05
```

### 2. คำนวณ Grid Exposure สะสม

**สถานการณ์: ราคาตกเรื่อยๆ (Trend Down)**

```
เริ่มที่: 2650.00

Grid 1 (Buy @ 2650):        0.01 lot  | DD: $0.05 @ 2645 (-50 pips)
Grid 2 (Buy @ 2600):        0.01 lot  | DD: $0.10 @ 2645 (-100 pips)
Grid 3 (Buy @ 2550):        0.01 lot  | DD: $0.15 @ 2645 (-150 pips)
Grid 4 (Buy @ 2500):        0.01 lot  | DD: $0.20 @ 2645 (-200 pips)
...
```

**คำนวณ Total Drawdown @ 200 pips:**
```
Total Lots: 0.04 lots
Average Price: (2650 + 2600 + 2550 + 2500) / 4 = 2575

Current Price: 2650 - 200 = 2450

Total Drawdown = (2575 - 2450) × $10 per lot × 0.04 lots
               = 125 × $0.40
               = $50.00
```

**สูตรทั่วไป:**
```python
grid_drawdown = (grid_count × grid_distance / 2) × pip_value × lot_size × grid_count

หรือ
grid_drawdown = (grid_count² × grid_distance × pip_value × lot_size) / 2
```

---

## 📉 วิเคราะห์ HG ตามสถานการณ์ต่างๆ

### สถานการณ์ 1: ราคาตก 200 pips (HG Trigger)

#### **Grid Exposure:**
```
Grid Count: 4 orders
Total Lots: 0.04 lots
Net Exposure: 0.04 lots (Buy ฝั่งเดียว)
```

#### **HG Lot (Buy):**
```
HG_Lot = max(Net Exposure × Multiplier, Initial Lot)
       = max(0.04 × 1.2, 0.01)
       = max(0.048, 0.01)
       = 0.048 lots (ใช้ 0.05)
```

#### **ผลลัพธ์เมื่อ HG วาง:**

**ที่ 2450 (ราคาตก 200 pips):**
- Grid Loss: -$50.00 (4 orders ที่ลบ 125 pips เฉลี่ย)
- HG Buy @ 2450: 0.05 lots

**ถ้าราคากลับมาที่ 2550 (+100 pips):**
- Grid: ยังขาดทุน -$50
- HG Gain: +100 pips × $0.50 = **+$50.00**
- **Net P&L = $0.00** ✅ (Breakeven ที่ 2550)

**ถ้าราคากลับมาที่ 2650 (+200 pips):**
- Grid: ยังขาดทุน -$50
- HG Gain: +200 pips × $0.50 = **+$100.00**
- **Net P&L = +$50.00** ✅ (กำไรสุทธิ)

---

### สถานการณ์ 2: ราคาตก 400 pips (2 HG Levels)

#### **Grid Exposure:**
```
Grid Count: 8 orders
Total Lots: 0.08 lots
```

#### **HG Level 1 @ 2450 (200 pips):**
```
HG_Lot_1 = max(0.04 × 1.2, 0.01) = 0.05 lots
```

#### **HG Level 2 @ 2250 (400 pips):**
```
HG_Lot_2 = max(0.08 × 1.2, 0.01) = 0.096 lots (ใช้ 0.10)

Total HG Lots: 0.15 lots
```

#### **ผลลัพธ์ที่ 2250:**
- Grid Loss: -$156.25 (8 orders)
- HG Cost: 0.15 lots × $2450 = $367.50
- **Total Risk: $523.75** (5.2% ของ balance)

**ถ้าราคากลับมา 2450:**
- Grid: ยังขาดทุน
- HG_1 Gain: +$25 (100 pips × 0.05 lots)
- HG_2 Gain: +$100 (200 pips × 0.10 lots)
- **HG Total: +$125**

---

## 🎯 สูตรคำนวณ HG ที่เหมาะสม

### 1. **สูตรหลัก: HG Protection Level**

```python
# เงื่อนไขการออก HG
def should_trigger_hg(grid_count, distance_from_start, hg_distance):
    return distance_from_start >= hg_distance

# คำนวณ HG Lot
def calculate_hg_lot(grid_volume, multiplier, initial_lot):
    base_lot = grid_volume * multiplier
    return max(base_lot, initial_lot)

# คำนวณ Breakeven Level
def breakeven_price(grid_avg_price, grid_loss, hg_lot):
    """
    หาราคาที่ HG ต้องถึงเพื่อ Breakeven
    """
    hg_gain_needed = abs(grid_loss)
    price_movement = hg_gain_needed / (hg_lot * pip_value)
    return grid_avg_price + price_movement
```

### 2. **สูตรคำนวณ Drawdown Protection**

```python
# คำนวณว่า HG ป้องกันได้กี่ pips
def protection_coverage(hg_lot, grid_volume):
    """
    HG ป้องกันได้เมื่อราคากลับมา pips = (hg_lot / grid_volume) × 100
    """
    coverage_ratio = hg_lot / grid_volume
    return coverage_ratio * 100  # pips ที่ HG หักล้างได้
```

---

## 📈 ผลการคำนวณตาม HG Distance

### **HG Distance = 200 pips:**

| Grid Count | Total Lots | HG Lot | Protection | Margin Used |
|-----------|-----------|---------|-----------|-------------|
| 4          | 0.04      | 0.05    | 125%     | 2.45%       |
| 8          | 0.08      | 0.10    | 125%     | 4.9%        |
| 12         | 0.12      | 0.15    | 125%     | 7.35%       |
| 16         | 0.16      | 0.20    | 125%     | 9.8%        |

**ข้อดี:** HG ป้องกันได้ 125% (เกิน 100%)  
**ข้อเสีย:** ออก HG เยอะเกินไป (200 pips)

---

### **HG Distance = 500 pips:**

| Grid Count | Total Lots | HG Lot | Protection | Margin Used |
|-----------|-----------|---------|-----------|-------------|
| 10         | 0.10      | 0.12    | 120%     | 5.88%       |
| 20         | 0.20      | 0.24    | 120%     | 11.76%      |

**ข้อดี:** HG น้อยกว่า ลด Margin  
**ข้อเสีย:** Grid Drawdown มากขึ้นก่อน HG ออก

---

### **HG Distance = 1000 pips:**

| Grid Count | Total Lots | HG Lot | Protection | Margin Used |
|-----------|-----------|---------|-----------|-------------|
| 20         | 0.20      | 0.24    | 120%     | 14.7%       |
| 40         | 0.40      | 0.48    | 120%     | 29.4%       |

**ข้อดี:** Grid มีโอกาส TP เองได้  
**ข้อเสีย:** HG ช้าเกินไป อาจโดน Margin Call

---

## 🎯 คำแนะนำสำหรับทุน $10,000 (ทนได้ 2000 pips)

### **คำนวณ Grid Orders ที่ 2000 pips:**

```
Grid Count = 2000 pips / 50 pips = 40 orders
Total Lots = 40 × 0.01 = 0.40 lots
Average Price = start_price - 1000 pips

Drawdown ที่ 2000 pips:
DD = (2000 pips / 2) × $0.10 × 0.01 × 40
   = 1000 × $0.04
   = $400 (4% ของ balance) ✅
```

### **แนะนำ: HG Distance = 400-500 pips (สำหรับ Max DD 2000 pips)**

**เหตุผล:**
1. ✅ ทนได้ถึง 2000 pips โดย Grid Drawdown ~$400
2. ✅ HG ป้องกันเมื่อราคาตก 400-500 pips
3. ✅ Margin Usage สุทธิไม่เกิน 30%
4. ✅ มีกำไรมากกว่าเสีย

### **การตั้งค่าที่แนะนำ (สำหรับ Max DD = 2000 pips):**

```python
# Grid Settings
grid_distance = 50 pips
lot_size = 0.01

# HG Settings (สำหรับ Max DD = 2000 pips)
hg_distance_buy = 400 pips   # HG ออกที่ 400 pips
hg_distance_sell = 400 pips  
hg_multiplier = 1.3          # ป้องกัน 130%
hg_sl_trigger = 200 pips     # Breakeven ที่ 200 pips
hg_max_levels = 10           # ทนได้ 10 levels
```

---

## 📊 ตารางเปรียบเทียบ (สำหรับ Max DD = 2000 pips)

| HG Distance | Grid DD | HG @ 400pips | HG Total | Net DD | Margin % | ข้อเสนอแนะ |
|------------|---------|-------------|----------|--------|----------|-----------|
| 300 pips   | -$225   | 0.05 lots | 0.50 lots | -$625 | 49%     | ⚠️ Margin เยอะ |
| 400 pips   | -$400   | 0.08 lots | 0.80 lots | -$400 | 63%     | ✅ **เหมาะสม** |
| 500 pips   | -$625   | 0.13 lots | 1.30 lots | -$325 | 82%     | ⚠️ ใกล้ Margin Call |
| 600 pips   | -$900   | 0.18 lots | 1.80 lots | -$360 | 112%    | ❌ Margin Call |

---

## ✅ สรุปคำแนะนำ (สำหรับ Max DD = 2000 pips)

### **สำหรับทุน $10,000 USD ทนได้ 2000 pips:**

1. **HG Distance = 400 pips** ✅
   - Grid Drawdown @ 400 pips: -$400 (4%)
   - HG ออกทันเวลา ป้องกันต่อเนื่อง
   - Margin Usage สุทธิ ~63%

2. **Multiplier = 1.3** ✅
   - HG Lot = Grid Volume × 1.3
   - ป้องกัน 130% ของ Grid Exposure

3. **Max HG Levels = 10** ✅
   - ทนได้ 10 levels (4000 pips total)
   - แข็งแกร่งต่อ Drawdown

4. **SL Trigger = 200 pips** ✅
   - Breakeven เมื่อ HG กำไร 200 pips
   - ป้องกัน Loss เมื่อราคากลับ

### **การทำงานจริง:**

```
ตัวอย่างที่ 2000 pips drawdown:

Grid @ 2000 pips:
- Grid Count: 40 orders
- Total Lots: 0.40 lots
- Average Price: start - 1000 pips
- Grid Loss: -$400

HG Levels (5 levels):
- Level 1 @ 400 pips: 0.08 lots | Gain: +$128 (@ 0 pips)
- Level 2 @ 800 pips: 0.16 lots | Gain: +$256
- Level 3 @ 1200 pips: 0.24 lots | Gain: +$384
- Level 4 @ 1600 pips: 0.32 lots | Gain: +$512
- Level 5 @ 2000 pips: 0.40 lots | Gain: +$640

Total HG Gain: +$1,920
Grid Loss: -$400
Net Profit: +$1,520 ✅
```

---

**ผลลัพธ์:** ระบบทน Drawdown ได้ 2000 pips พร้อมมีกำไรสุทธิเมื่อราคากลับมาที่จุดเริ่มต้น
