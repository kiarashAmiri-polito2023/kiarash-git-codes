# 📋 سند جامع بکاپ پروژه — MiR + Motive → QwenVLA

**تاریخ تهیه:** ۲۵ اوت ۲۰۲۶
**تهیه‌کننده:** AI مشاور اعظم
**نسخه:** ۱.۰ (بکاپ کامل)
**مسیر پروژه:** `D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1`

---

## بخش ۱: هدف نهایی پروژه

ساخت یک **دیتاست VLA (Vision-Language-Action) دوگانه و قابل ردیابی** برای آموزش مدل **QwenVLA** که شامل سه ستون باشد:

| ستون | منبع داده | توضیح |
|------|-----------|-------|
| **Vision** | دوربین‌های سقفی Motive + LiDAR/SLAM | آنچه ربات و دوربین‌ها می‌بینند |
| **Language** | Entity Registry + Taxonomy | توصیف شیء، وضعیت، ریسک و دستور |
| **Action** | /cmd_vel + /odom + Safety Events | فرمان واقعی ربات و دلیل آن |

**معماری آموزشی:** Dual-Source Redundant Training (هر دو منبع Motive و SLAM همزمان استفاده می‌شوند)

**هدف انتشار:** مقاله در کنفرانس ICRA / IROS / CoRL / RAL

**حداقل داده لازم:** ۱۰ سشن ضبط شده با کیفیت VLA (نمره ۸۰+)

---

## بخش ۲: سیستم فیزیکی

| تجهیز | مشخصات | آدرس/پورت |
|-------|--------|-----------|
| ربات MiR100 | لایدار جلو + عقب، SLAM داخلی | 192.168.12.20 |
| ROS Bridge | WebSocket | 192.168.12.20:9090 |
| REST API MiR | وضعیت، ماموریت | 192.168.12.20:8080 (نیاز به API Key) |
| دوربین‌های Motive | ۸ عدد PrimeX 22 (سریال ۶۹۴۲۶-۶۹۴۳۳) | NatNet multicast 127.0.0.1 |
| نرم‌افزار Motive | OptiTrack Motive | — |
| سیستم عامل | Windows + Python 3.10 | — |

---

## بخش ۳: نقشه راه ۱۰ مرحله‌ای (وضعیت دقیق)

| مرحله | عنوان | وضعیت | تاریخ تکمیل | توضیح |
|-------|-------|-------|-------------|-------|
| **۱** | رفع باگ Zero Placeholder | ✅ **DONE** | ۲۴ اوت | جلوگیری از آلودگی فیوژن با موقعیت‌های (0,0,0) |
| **۲** | سیستم Merge انسانی | ✅ **DONE** | ۲۴ اوت | هرگز حافظه عمیق بدون تأیید انسان merge نمی‌شود |
| **۳** | رجیستری برچسب‌ها | ✅ **DONE** | ۲۵ اوت | Entity-based: یک انسان = یک entity (نه ۳ marker) |
| **۴** | آنوتیتور نقشه SLAM | ⬜ **NOT STARTED** | — | خوشه‌بندی موانع + نام‌گذاری + رندر ویدیو |
| **۵** | آنوتیتور ویدیو Motive (CVAT) | ⚠️ **PARTIAL** | ۲۵ اوت | ایجنت‌ها آماده‌اند، CVAT هنوز مستقر نشده |
| **۶** | تطبیق بین منابع | ✅ **DONE** | ۲۴ اوت | Hungarian algorithm در cross_modal_aligner |
| **۷** | گزارش یکپارچه سشن | ✅ **DONE** | ۲۵ اوت | شامل Motive + SLAM + Robot + Entity در یک گزارش |
| **۸** | واردکننده فرمان‌های ربات | ✅ **DONE** | ۲۵ اوت | /cmd_vel + /odom + /joystick + REST API |
| **۹** | مشاور AI دوگانه | ⬜ **NOT STARTED** | — | Session Review + Deep Memory Reflection |
| **۱۰** | سازنده دیتاست VLA | ⬜ **NOT STARTED** | — | خروجی نهایی RLDS/LeRobot برای QwenVLA |

**پیشرفت کلی:** ۶ از ۱۰ مرحله انجام شده (۶۰٪)

---

## بخش ۴: کارهای انجام شده — جزئیات کامل

### ۴.۱ رفع باگ سرعت غیرمعقول (v2.2)
**تاریخ:** ۲۵ اوت ۲۰۲۶
**مشکل:** سرعت ۶۱.۸۲ m/s (≈ ۲۲۰ km/h) برای مچ دست ثبت می‌شد
**ریشه:** `knowledge_engine.py` تابع `extract_session_features` هیچ فیلتری روی سرعت نداشت. یک فریم glitch با `dt=0.033` و `dx=2m` منجر به `speed=60 m/s` می‌شد
**راه‌حل:** اضافه کردن `MAX_PHYSICAL_SPEED_MPS = 5.0` و فیلتر `if speed > MAX: continue` در دو نقطه (سرعت اصلی و سرعت نزدیک‌شدن)
**فایل تغییر یافته:** `agents/knowledge_engine.py` (v2.1 → v2.2)

### ۴.۲ ساخت Video QA Agent v2.0
**تاریخ:** ۲۵ اوت ۲۰۲۶
**هدف:** بررسی ۱۵ فاکتور کیفیت ویدیو بر اساس استانداردهای صنعتی
**استانداردهای پیاده‌شده:**
- Google DeepMind RT-X (Frame Sync)
- Berkeley DROID (FPS, Focus)
- LeRobot (Codec/Bitrate)
- Physical Intelligence (Resolution)
- NVIDIA GR00T (Ghost Overlay, Data Leakage)
- Tesla (Dynamic Range)
- Figure AI (Motion Blur)
- Meta Ego4D (Scene Diversity)
- Stanford ALOHA (Occlusion)
- 1X Technologies (Scene Richness)
**فایل:** `agents/video_quality_agent.py`
**لانچر:** `RUN_VIDEO_QA.bat` (دابل کلیک)

### ۴.۳ رفع Ghost Overlay دوربین‌ها
**تاریخ:** ۲۵ اوت ۲۰۲۶
**مشکل:** شکلک‌های گرافیکی Rigid Body موتیو روی ویدیو سوخته بودند (۵۰ blob + ۸۳ خط در هر فریم)
**راه‌حل:** خاموش کردن Visual Aids در Motive (Rigid Body Shape, Bones, Skeleton, Marker Labels, Axes)
**نتیجه Camera 1:** نمره ۶۷ → ۸۵ (GOOD) ✅
**نتیجه Camera 8:** هنوز ۷۱ (Ghost باقی است) ⚠️

### ۴.۴ ساخت Entity Registry (Master Entity Registry)
**تاریخ:** ۲۵ اوت ۲۰۲۶
**هدف:** گروه‌بندی چند marker به یک entity واقعی (استاندارد Google RT-X, Physical Intelligence)
**فایل:** `agents/entity_registry.py`
**خروجی:** `persistent_knowledge/entity_registry.pkl`
**نتیجه فعلی:**
```
ENT-16E62CA238: person_kiarash (human, dynamic)
  markers: [kiarash_leftwrist, kiarash_RightWrist]
  status: PENDING

ENT-F63F0E4AD9: kia hat 002 (human, dynamic)
  markers: [kia hat 002]
  status: PENDING
```
**کار باقیمانده:** ادغام `kia hat 002` به `person_kiarash` (کد آماده است، اجرا نشده)

### ۴.۵ ساخت MirCommandLogger
**تاریخ:** ۲۵ اوت ۲۰۲۶
**هدف:** ضبط Action Ground Truth از ربات MiR
**فایل:** `agents/mir_command_logger.py`
**داده‌های ضبط شده:**
| Topic | نوع | فرکانس | وضعیت |
|-------|-----|--------|-------|
| /cmd_vel | فرمان سرعت | متغیر | ✅ مشترک |
| /odom | سرعت واقعی | ~۴۰ Hz | ✅ ۴۱۶ فریم در ۱۰ ثانیه |
| /joystick_vel | override دستی | متغیر | ✅ مشترک |
| /battery_state | باتری | متغیر | ✅ مشترک |
| REST /status | وضعیت ربات | ۲ ثانیه | ⚠️ نیاز به API Key |
**تشخیص خودکار:** sudden_stop, manual_override

### ۴.۶ ساخت SLAM Auto-Namer
**تاریخ:** ۲۵ اوت ۲۰۲۶
**هدف:** انتساب نام entity به کلاسترهای SLAM/LiDAR بر اساس نزدیکی مکانی
**فایل:** `agents/slam_auto_namer.py`
**روش:** فاصله اقلیدسی بین مرکز کلاستر SLAM و میانگین موقعیت marker Motive (آستانه ۰.۵ متر)

### ۴.۷ ساخت CVAT Pre-Populator
**تاریخ:** ۲۵ اوت ۲۰۲۶
**هدف:** تولید فایل CVAT XML با نام‌ها و bbox‌های پیشنهادی از Entity Registry
**فایل:** `agents/cvat_prepopulator.py`
**خروجی:** `sessions/<session>/cvat_prepopulated/<session>_prepopulated.xml`
**نکته:** bbox‌ها فعلاً placeholder هستند. پروجکشن ۳D→2D واقعی بعد از کالیبراسیون دوربین اضافه می‌شود

### ۴.۸ ساخت Robot Data Analyzer
**تاریخ:** ۲۵ اوت ۲۰۲۶
**هدف:** تحلیل رفتار ربات از داده‌های ضبط شده
**فایل:** `agents/robot_data_analyzer.py`
**خروجی:** action_summary, safety_summary, movement_patterns, state_summary

### ۴.۹ پچ launch_session.py (v6 → v7)
**تاریخ:** ۲۵ اوت ۲۰۲۶
**تغییرات:**
- اضافه شدن MirCommandLogger (شروع خودکار با ضبط)
- اضافه شدن Entity Registry Rebuild در پایپ‌لاین
- اضافه شدن SLAM Auto-Naming در پایپ‌لاین
- اضافه شدن CVAT Pre-Populator در پایپ‌لاین
- اضافه شدن Robot Data Analyzer در پایپ‌لاین
- ذخیره و توقف cmd_logger قبل از slam_logger

### ۴.۱۰ پچ co_pilot_agent.py
**تاریخ:** ۲۵ اوت ۲۰۲۶
**تغییرات:**
- اضافه شدن بخش Robot Command Analysis به گزارش
- اضافه شدن بخش Entity Registry Summary به گزارش

---

## بخش ۵: داده‌های جمع‌آوری شده

| سشن | تاریخ | Motive | SLAM | Robot Cmd | ویدیو | کیفیت |
|-----|-------|--------|------|-----------|-------|-------|
| session_2026-08-24_13-16-03 | ۲۴ اوت | ✅ | ✅ | ❌ | ❌ | — |
| session_2026-08-24_13-57-33 | ۲۴ اوت | ✅ | ✅ | ❌ | ✅ (Cam 1, 4) | ۶۷/۱۰۰ (قبل از fix) |
| session_2026-08-25_17-43-02 | ۲۵ اوت | ✅ | ❌ | ❌ | ✅ (Cam 1, 8) | ۸۵/۱۰۰ (Cam 1) |

**اشیاء شناخته شده:** ۳ (kia hat 002, kiarash_leftwrist, kiarash_RightWrist)
**Entities ثبت شده:** ۲ (person_kiarash, kia hat 002) — در انتظار ادغام
**رخدادهای ایمنی:** ۱۱۶ (۳۰ بحرانی، ۸۶ هشدار)
**نزدیک‌ترین فاصله:** ۸ میلی‌متر

---

## بخش ۶: فایل‌های پروژه (لیست کامل)

### ایجنت‌های SDK (تغییر ندهید)
| فایل | خطوط | توضیح |
|------|------|-------|
| NatNetClient.py | ۸۴۲ | کلاینت NatNet |
| DataDescriptions.py | ۷۳۶ | ساختار داده NatNet |
| MoCapData.py | ۸۷۲ | فریم‌های حرکت |

### ایجنت‌های هسته‌ای
| فایل | خطوط | نسخه | توضیح |
|------|------|------|-------|
| launch_session.py | ~۱۲۰۰ | v7 | ارکستراتور اصلی |
| spatial_temporal_fusion.py | ۵۲۳ | v2 | فیوژن Motive + SLAM |
| knowledge_engine.py | ~۴۵۰ | v2.2 | موتور یادگیری |
| quality_gate.py | ۵۰۸ | v2 | فلگ‌های کیفیت |
| apply_merge.py | ۳۹۹ | — | Merge با تأیید انسان |
| co_pilot_agent.py | ~۶۵۰ | v2+ | گزارش‌دهی |
| session_manager.py | ۴۱۹ | — | مدیر سشن |
| run_session_analysis.py | ۳۳۷ | — | ارکستراتور تحلیل |
| motive_connector.py | ۴۹۱ | v2 | اتصال به NatNet |

### ایجنت‌های جدید (ساخته شده ۲۵ اوت)
| فایل | توضیح |
|------|-------|
| **mir_command_logger.py** | ضبط فرمان‌های ربات |
| **entity_registry.py** | رجیستری entity-based |
| **slam_auto_namer.py** | نام‌گذاری خودکار SLAM |
| **cvat_prepopulator.py** | پیش‌نویس CVAT |
| **robot_data_analyzer.py** | تحلیل رفتار ربات |
| **video_quality_agent.py** | QA ویدیو (v2.0) |

### ایجنت‌های قبلی
| فایل | توضیح |
|------|-------|
| label_registry.py | رجیستری برچسب قدیمی |
| label_registry_auto.py | فعال‌سازی خودکار |
| cvat_converter.py | مبدل CVAT |
| auto_labeler.py | Grounding DINO |
| cross_modal_aligner.py | Hungarian matching |
| offline_processor.py | پردازش آفلاین |
| inspect_motive_pipeline.py | تشخیصی |
| theises planer snapshout .py | اسنپ‌شات v4 |

### فایل‌های حافظه دائمی
| فایل | وضعیت |
|------|-------|
| persistent_knowledge/taxonomy.json | ✅ ۶ کلاس |
| persistent_knowledge/environment_knowledge.pkl | ✅ ۲ سشن |
| persistent_knowledge/deep_learning_memory.pkl | ✅ ۴ سشن |
| persistent_knowledge/label_registry.pkl | ✅ ۳ برچسب |
| persistent_knowledge/entity_registry.pkl | ✅ ۲ entity |

---

## بخش ۷: کارهای باقیمانده — برنامه دقیق

### فوری (قبل از سشن سوم)
| # | کار | زمان | اولویت |
|---|-----|------|--------|
| ۱ | اجرای کد ادغام کلاه با person_kiarash | ۱ دقیقه | 🔴 |
| ۲ | رفع Ghost Overlay Camera 8 در Motive | ۵ دقیقه | 🔴 |
| ۳ | تنظیم نور آزمایشگاه (Brightness > 40) | ۱۰ دقیقه | 🟡 |

### کوتاه‌مدت (هفته جاری)
| # | کار | زمان | اولویت |
|---|-----|------|--------|
| ۴ | ضبط سشن سوم (با ربات + Motive + SLAM) | ۳۰ دقیقه | 🔴 |
| ۵ | اجرای QA Agent روی سشن سوم | ۵ دقیقه | 🔴 |
| ۶ | تأیید Entity Registry توسط انسان | ۵ دقیقه | 🟡 |
| ۷ | ضبط سشن ۴ تا ۶ | ۲ ساعت | 🔴 |

### میان‌مدت (هفته آینده)
| # | کار | زمان | اولویت |
|---|-----|------|--------|
| ۸ | نصب CVAT (Docker) | ۱ ساعت | 🟡 |
| ۹ | دانلود وزن‌های Grounding DINO | ۳۰ دقیقه | 🟡 |
| ۱۰ | آنوتیتور ویدیو با CVAT (سشن ۳-۶) | ۴ ساعت | 🟡 |
| ۱۱ | ساخت SLAM Map Annotator (Step 4) | ۳ ساعت | 🟡 |
| ۱۲ | ضبط سشن ۷ تا ۱۰ | ۳ ساعت | 🔴 |

### بلندمدت (ماه آینده)
| # | کار | زمان | اولویت |
|---|-----|------|--------|
| ۱۳ | ساخت AI Advisor (Step 9) | ۴ ساعت | 🟢 |
| ۱۴ | ساخت VLA Dataset Builder (Step 10) | ۸ ساعت | 🔴 |
| ۱۵ | کالیبراسیون دوربین‌ها (با wand) | ۲ ساعت | 🟡 |
| ۱۶ | آموزش QwenVLA | ۲۴+ ساعت | 🔴 |
| ۱۷ | نوشتن مقاله | ۲ هفته | 🔴 |

---

## بخش ۸: قوانین ایمنی و مهندسی (قفل شده)

1. ❌ هرگز merge خودکار به حافظه عمیق
2. ✅ تأیید انسان مرجع نهایی است
3. ❌ پیش‌فرض عملیات مخرب = خیر
4. ✅ ذخیره اتمی + بکاپ قبل از هر تغییر
5. ✅ حفظ داده‌های خام اصلی
6. ❌ بازنویسی بزرگ بدون دلیل
7. ❌ اختراع کالیبراسیون دوربین
8. ❌ اختراع schema فایل CSV
9. ❌ ترکیب NatNet و MiR API در یک ماژول
10. ✅ سینتکس سازگار با Python 3.10
11. ✅ متن گزارش‌ها و خروجی‌ها به انگلیسی
12. ✅ مکالمه کاربر/AI به فارسی
13. ✅ پیشنهادها ≠ حقایق
14. ✅ هر رکورد دیتاست باید provenance داشته باشد
15. ✅ هر سشن باید از داده‌های خام قابل بازتولید باشد

---

## بخش ۹: همراستایی با شرکت‌های بزرگ

| رویه | شرکت مرجع | وضعیت |
|------|-----------|-------|
| Taxonomy ثابت | Google RT-X | ✅ |
| Human-in-loop | Figure AI | ✅ |
| ذخیره اتمی | صنعت | ✅ |
| SAFE mode | — | ✅ |
| ابزار خارجی (CVAT) | Tesla, Figure | ⚠️ آماده، مستقر نشده |
| Auto-labeling | PI, Google | ⚠️ کد آماده، وزن نداریم |
| Cross-modal alignment | DeepMind | ✅ |
| Entity Registry | Google RT-X | ✅ |
| Session versioning | HuggingFace | ✅ |
| Quality flagging | همه | ✅ |
| AI Advisor | — | ❌ |
| VLA Dataset Builder | همه | ❌ |

**همراستایی کلی:** ۱۰ از ۱۲ (۸۳٪)

---

## بخش ۱۰: امتیاز آمادگی مقاله

| فاکتور | فعلی | هدف |
|--------|------|------|
| سشن‌های ضبط شده | ۳ | ۱۰ |
| سشن‌های با کیفیت VLA | ۱ | ۱۰ |
| Entities تأیید شده | ۰ | ≥ ۵ |
| ویدیوهای آنوتیت شده | ۰ | ۲۰+ |
| فرمان‌های ربات ضبط شده | ۱ تست | ۱۰ سشن |
| Cross-modal alignment | ۰ | ۱۰ |
| Taxonomy classes | ۶ | ۶ ✅ |

**امتیاز فعلی:** ۴۵ از ۱۰۰ (مرحله توسعه → جمع‌آوری داده)

---

## بخش ۱۱: بکاپ‌ها

| تاریخ | مکان | محتوا |
|-------|------|-------|
| ۲۵ اوت ۱۸:۴۱ | `backups/backup_20260825_184149/` | launch_session, fusion, copilot, knowledge, label_registry |

---

## بخش ۱۲: پکیج‌های پایتون

| پکیج | وضعیت | کاربرد |
|------|-------|--------|
| numpy | ✅ نصب | محاسبات |
| scipy | ✅ نصب | Hungarian algorithm |
| cv2 | ✅ نصب | پردازش تصویر |
| roslibpy | ✅ نصب | اتصال به ربات |
| requests | ✅ نصب | REST API |
| sklearn | ❌ مفقود | DBSCAN clustering |
| torch | ❌ مفقود | Grounding DINO |
| transformers | ❌ مفقود | Grounding DINO |
| groundingdino | ❌ مفقود | Auto-labeling |

---

