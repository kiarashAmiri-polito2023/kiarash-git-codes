# اهداف پروژه پایان‌نامه — Thesis Goals Registry

**آخرین بروزرسانی:** 2026-09-24 Step 43
**اپراتور:** Kiarash Amiri (s322803) | **سرپرست:** Prof. Dario Antonelli
**ددلاین:** 2026-10-22 (~28 روز)

---

## هدف نهایی (End Goal)

ربات **MiR100** باید بتونه با دریافت فرمان صوتی فارسی از اپراتور، محیط رو درک کنه (دوربین + SLAM + MoCap)، مانع‌ها و انسان‌ها رو تشخیص بده، و سیاست حرکتی هوشمند داشته باشه.

### فاز فعلی: آموزش مدل VLA
- تمرکز روی **ساخت dataset باکیفیت** و **آموزش Qwen3-VL** (LoRA) روی سیستم 5090
- Inference زنده روی ربات فعلاً اولویت نیست — هدف اینه وقتی داده‌ها به LLM محلی داده بشن، مدل محیط رو کامل درک کنه
- پس از قابل‌اعتماد شدن JSON files → دادن به AI محلی (qwen3.6-27b) برای تولید فرمان حرکت

---

## اهداف اصلی (Primary Goals)

| # | هدف | اولویت | وضعیت | توضیح |
|---|-----|--------|-------|------|
| G1 | **Dataset Quality** | 🔴 بحرانی | در حال کار | ساخت dataset VLA باکیفیت از session‌های ضبط‌شده (حداقل 3 session کامل، >1000 نمونه) |
| G2 | **Pipeline Reliability** | 🔴 بحرانی | باگ‌دار | pipeline ایجنت‌ها باید بدون خطا و قابل‌اعتماد کار کنه — تست‌های 100/200 جانبه اجباری |
| G3 | **VLA Model Training** | 🟡 بالا | آماده آموزش | Qwen3-VL-2B با LoRA روی dataset ساخته‌شده (6 epochs, loss=0.0856) |
| G4 | **Semantic Environment Understanding** | 🟡 بالا | در حال توسعه | محیط باید کاملاً قابل‌درک باشه: BEV map + object detection + semantic labels |
| G5 | **JSON Output to LLM** | 🟢 متوسط | طراحی شده | فایل JSON نهایی شامل وضعیت محیط، تشخیص اشیاء، و پیشنهاد حرکت → به qwen3.6-27b |

---

## اهداف فرعی (Secondary Goals)

| # | هدف | اولویت | وضعیت | توضیح |
|---|-----|--------|-------|------|
| G6 | **Persian Voice Control** | 🟢 متوسط | طراحی شده | پردازش فرمان صوتی فارسی توسط LLM محلی |
| G7 | **Human-Aware Obstacle Detection** | 🟡 بالا | BUG-EE | YOLO + GroundingDINO (پکیج‌ها نصب نیستن) |
| G8 | **SLAM/Motive Fusion** | 🔴 بحرانی | باگ‌دار | همگام‌سازی داده‌های SLAM و OptiTrack MoCap (BUG-DX/EF, EC) |
| G9 | **HITL (Human-in-the-Loop)** | 🟡 بالا | BUG-ED | تأیید انسانی cross-modal matches انجام نشده |
| G10 | **Multi-Session Recording** | 🔴 بحرانی | نیاز به ضبط | حداقل 3 session کامل با score 100% برای Q1 paper |

---

## لایه‌های سیستم (System Layers)

```
┌─────────────────────────────────────────────┐
│ LAYER 5: اپراتور ← صدای فارسی               │ G6
└──────────┬──────────────────────────────────┘
           ▼
┌─────────────────────────────────────────────┐
│ LAYER 4: LLM محلی (qwen3.6-27b)             │ G5
│ ← JSON فرمان حرکت (velocity, angular vel)   │
└──────────┬──────────────────────────────────┘
           ▼
┌─────────────────────────────────────────────┐
│ LAYER 3: VLA Model (Qwen3-VL-2B LoRA)       │ G3
│ ← Vision-Language-Action Policy              │
└──────────┬──────────────────────────────────┘
           ▼
┌─────────────────────────────────────────────┐
│ LAYER 2: Semantic Perception                │ G4, G7
│ BEV Map + Object Detection (YOLO) + Events   │
└──────────┬──────────────────────────────────┘
           ▼
┌─────────────────────────────────────────────┐
│ LAYER 1: Data Acquisition                   │ G8, G10
│ SLAM + MoCap (OptiTrack) + Cameras + Videos  │
└─────────────────────────────────────────────┘
```

---

## معیارهای موفقیت (Success Criteria)

| معیار | هدف | وضعیت فعلی | شکاف |
|------|-----|-----------|------|
| Session‌های کامل (score 100%) | ≥3 | 1 | نیاز به 2 session بیشتر |
| Dataset samples | ≥1000 | 344 (275 train + 69 val) | نیاز به ~656 نمونه بیشتر |
| BEV frames | تمام فریم‌ها | 344 از 621 (55%) | BUG-EC محدودیت داره |
| Cross-modal sync | دقیق با real timestamps | ساختگی (BUG-DX) | نیاز به fix |
| HITL confirmation | ≥80% matches تأیید شده | 0% | BUG-ED |
| Object detection | YOLO فعال | ultralytics نصب نیست | BUG-EE |

---

## ترتیب اولویت‌بندی (Priority Order)

1. **رفع باگ‌های pipeline** (DX, EG, EC, EA/EB) → بدون این بقیه معنا نداره
2. **نصب پکیج‌ها** (ultralytics, groundingdino) → G7 فعال میشه
3. **ضبط session‌های جدید** → G10 → G1
4. **HITL activation** → G9
5. **JSON pipeline به LLM** → G5
6. **VLA training با dataset کامل** → G3
7. **Voice control integration** → G6

---

## یادداشت‌های اپراتور

- دو AI موازی روی پروژه کار می‌کنن — تمام promptها و نتایج اینجا ثبت میشه
- هر گزارش جدید باید حافظه‌ها رو آپدیت کنه
- تست‌های 100/200 جانبه سختگیرانه اجباری پیش از هر تغییر
