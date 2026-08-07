# قوانین پروژه پایان‌نامه — مرجع کامل Laws 0-78

## قوانین پایه (0-10)

| # | نام | خلاصه | مثال نقض |
|---|-----|-------|----------|
| 0 | گردش کار اجباری | هر تغییری باید به ترتیب Diagnostic→بکاپ→تغییر→تست→ثبت انجام شود و هیچ مرحله‌ای حذف نشود. | تغییر مستقیم بدون بکاپ |
| 1 | بدون Diagnostic تغییر نکن | قبل از هر تغییری، وضعیت موجود باید با تست real تأیید شود نه با حدس. | ویرایش کور بدون خواندن فایل |
| 2 | هرگز فرض نکن | هر ادعایی باید با تست واقعی تأیید شود؛ «احتمالاً هست» پذیرفته نمی‌شود. | گفتن «فایل هست» بدون بررسی وجود |
| 3 | ASCII در PowerShell | استفاده از emoji در کد PowerShell ممنوع است چون باعث خطای parse می‌شود. | قرار دادن ✅ در متن PS |
| 4 | Heredoc تک‌کوتیشن | هنگام نوشتن اسکریپت پایتون در PowerShell، از Here-String `'... '@` استفاده شود تا متغیرهای PS expand نشوند. | استفاده از `@"..."@` وقتی نیازی به متغیر نیست |
| 5 | بکاپ قبل از تغییر | قبل از هر تغییر فایل، باید بکاپ timestamped با MD5 باینری گرفته شود. | ویرایش بدون بکاپ |
| 6 | py_compile و AST | قبل و بعد از هر تغییر، فایل پایتون باید با ast.parse و py_compile اعتبارسنجی شود. | رد شدن از بررسی سینتکس |
| 7 | BOM خواندن و نوشتن | خواندن فایل‌های UTF-8 با BOM باید با utf-8-sig باشد و نوشتن باید utf-8 بدون BOM انجام شود. | خواندن با utf-8 ساده وقتی BOM وجود دارد |
| 8 | import بالای فایل | تمام importها باید در بالاترین سطح فایل باشند نه داخل توابع؛ import داخل تابع فقط با دلیل موجه مجاز است. | import کردن داخل یک تابع بی‌دلیل |
| 9 | پاسخ ساختاریافته | هر پاسخ باید شامل بخش فارسی توضیحی، جدول داده، کد اجرایی و verdict نهایی باشد. | پاسخ فقط متنی بدون ساختار |
| 10 | فایل حیاتی بدون اجازه ممنوع | هیچ فایل حیاتی (مثل A18_verifier) بدون تأیید صریح اپراتور تغییر داده نشود. | تغییر خودسرانه A18 |

## قوانین اعتبارسنجی (11-20)

| # | نام | خلاصه | مثال نقض |
|---|-----|-------|----------|
| 11 | عدم قطعیت = تست بیشتر | هر بار که uncertainty وجود دارد، باید تست‌های بیشتری انجام شود نه اینکه از کنارش رد شود. | نادیده گرفتن UNCERTAIN |
| 12 | Cross-Validation | خروجی هر AI باید توسط AI دیگر یا تست مستقل ارزیابی مجدد شود. | اعتماد کامل به خروجی اول |
| 13 | Trust but Verify | حرف اپراتور هم باید تست شود؛ اطلاعات نادرست ممکن است از اپراتور هم بیاید. | پذیرش بدون بررسی |
| 14 | هوشمندی ایجنت | وجود فایل به معنای هوشمندی نیست؛ فایل باید رفتار واقعی داشته باشد نه فقط وجود داشته باشد. | «فایل هست پس کار می‌کند.» |
| 15 | Verify قبل/بعد ۱۰۰٪ | قبل و بعد از هر تغییر باید verify 100٪ انجام شود. | فقط بعد verify کردن |
| 16 | Master Report Law | پایان هر فاز = تولید Dossier جامع شامل تمام تغییرات و نتایج. | تمام کردن فاز بدون گزارش |
| 17 | No New Agent Law | ساخت ایجنت جدید بدون اجازه صریح اپراتور ممنوع است. | ساخت A42 بدون اجازه |
| 18 | Triple-Verification | هر تغییر باید سه‌بار اعتبارسنجی شود: ساختاری (AST)، عملکردی (تست واقعی)، رفتاری (اجرای واقعی). | فقط AST |
| 19 | Backup Organization | بکاپ‌ها باید در پوشه backups/[name]/ با timestamp و log سازماندهی شوند. | بکاپ بی‌ساختار |
| 20 | Functional Redundancy | قبل از ساخت چیز جدید، موجود بودن قابلیت بررسی شود. | duplicate ساختن |

## قوانین عملیاتی (21-35)

| # | نام | خلاصه | مثال نقض |
|---|-----|-------|----------|
| 21 | Mandatory Temp Cleanup | هر فایل موقت باید پس از استفاده حذف شود و خود اسکریپت هم پاک شود. | رها کردن chk.py روی Desktop |
| 24 | Architecture Organization | هر فایل باید در پوشه معماری مناسب خود باشد؛ فایل orphan ممنوع. | فایل بدون مکان |
| 25 | Backup Integrity | بکاپ باید هم MD5 و هم محتوای خوانا داشته باشد. | بکاپ خراب یا فقط فایل |
| 26 | Research Alignment | هر اقدام باید به هدف نهایی پروژه (Q1/MiR100) کمک کند. | کار نامرتبط |
| 27 | صداقت مطلق | اغراق، تخمین بیش از حد یا heuristic را جای تست واقعی جا نزن. | ادعای ۱۰۰۰ ریپو بدون شمارش |
| 28 | ۱۰x Precision | MD5 باید binary باشد نه متنی؛ تغییرات خطی باشند نه سراسری. | sed کور روی کل فایل |
| 29 | Delete/Archive Safety | قبل از حذف فایل، تست شود و فایل به بکاپ منتقل شود نه delete مستقیم. | حذف بدون تست |
| 30 | Multi-Domain Testing | هر تست باید حداقل ۵ دامنه مختلف را پوشش دهد. | فقط یک دامنه |
| 31 | Behavioral-First | compile شدن فایل به معنای کارکرد صحیح نیست؛ رفتار واقعی اولویت دارد. | «AST OK پس کار می‌کند.» |
| 32 | Temp-File Execution | استفاده از python -c تو در تو در PowerShell ممنوع است؛ فایل کمکی ASCII جداگانه استفاده شود. | inline کد پایتون در PS |
| 33 | Test-the-Test | هر تست قبل از اجرا باید خودش اعتبارسنجی شود (parse شود). | JSON خالی را parse کردن |
| 34 | Binary MD5 | Get-FileHash یا open(rb) استفاده شود نه hash متنی. | hash با متن |
| 35 | Hard-Timeout | هر فراخوانی API حداکثر ۱۸۰ ثانیه و هر اسکریپت حداکثر ۱۲۰ ثانیه timeout داشته باشد. | بدون timeout |

## قوانین تصمیم‌گیری (36-47)

| # | نام | خلاصه | مثال نقض |
|---|-----|-------|----------|
| 36 | Goal Tracking | تمام اهداف باید شفاف و قابل ردیابی باشند. | اهداف گمشده |
| 37 | نقد بی‌رحمانه | هر ایده قبل از پذیرش باید از ۵ فیلتر نقد بگذرد. | پذیرش کور ایده |
| 38 | قرنطینه ۴مرحله‌ای | هر ایده بزرگ باید ۴ مرحله قرنطینه را طی کند: ارائه، مناظره، PoC، تصمیم. | اجرای فوری ایده بزرگ |
| 39 | Vault SOTA Protocol | تمام ریپوهای SOTA باید در github_curation_vault با گزارش مستند شوند. | ریپوی بدون گزارش |
| 40 | ماتریس چندجهتی | تصمیمات بر اساس تحلیل چندبعدی گرفته شوند نه تک‌بعدی. | تصمیم عجولانه |
| 41 | Pre-Test Research Gate | قبل از هر تست، ابعاد و منابع باید منبع‌دار و مستند باشند نه اختراعی. | شروع تست بدون تحقیق |
| 42 | Batched Diagnostic | چند سؤال همزمان در یک اسکریپت پرسیده شود نه تک‌تک. | یک سؤال per script |
| 43 | Systemic Impact Gate | هر تغییر باید تأثیرش روی تمام ایجنت‌ها بررسی شود. | تغییر بدون بررسی سیستمی |
| 44 | Tesla FSD Parallel | عملکرد باید با SOTA صنعتی مقایسه شود. | نادیده گرفتن رقبا |
| 45 | Existence-First | وجود هر فایل و ابزار قبل از استفاده تأیید شود. | فرض وجود فایل |
| 46 | Bug Full-Name | هر باگ با کد + توضیح فارسی ثبت شود نه فقط کد. | BUG-CO بدون توضیح |
| 47 | TDAE | هر FAIL باید شامل ارتباط به Q1، دلیل و اقدام fix یا reject باشد. | سکوت بعد از FAIL |

## قوانین محیطی (48-65)

| # | نام | خلاصه | مثال نقض |
|---|-----|-------|----------|
| 48 | LLM Governance | qwen3.6-27b فقط ممیز کد است نه فرمان‌دهنده ربات؛ qwen3-vl فقط برای تصویر نه کد. | VL روی کد |
| 50 | Machine Profile Law | هرگز اطلاعات سه سیستم (5090/3090/Laptop) قاطی نشود؛ IP و مسیر هر کدام مستقل است. | IP 3090 برای 5090 |
| 51 | SOTA Multi-Dimensional Mandatory | قبل از هر مرحله عملیاتی جدید، ۱۰۰ تا ۲۰۰ جنبه از GitHub SOTA تست و مستند شود. | شروع بدون بنچمارک |
| 52 | AST-First / No-Truncated-Code Audit | ادعای SyntaxError توسط مدل بدون تأیید با ast.parse روی کل فایل پذیرفته نیست. | پذیرش FAIL مدل |
| 53 | Clipboard-Short-Output | خروجی PowerShell کوتاه باشد؛ فقط یک خط خلاصه در کلیپ‌بورد. | چاپ کل JSON |
| 54 | Full-File Reading | ممیزی روی کل فایل نه ۴۵۰۰ کاراکتر اول. | truncate به ۴۵۰۰c |
| 55 | Package-Dependency | پکیج‌های وابسته قبل از اجرا چک شوند و اگر MISSING بودند fallback ایمن وجود داشته باشد. | صدا زدن stub خالی |
| 56 | UTF-8 No BOM Write | نوشتن پایتون فقط با UTF8Encoding $false]. | BOM پیش‌فرض |
| 57 | LMS JSON Hygiene | max_tokens≥3500 و قبل از parse کردن JSON، تگ‌های ```json حذف شوند. | parse فایل ۵ بایتی |
| 58 | Confidence Scale | confidence مدل معمولاً ۰.۹۵ یعنی ۹۵٪ است نه ۰.۹۵٪؛ اعداد نرمال شوند. | تفسیر ۰.۹۵ به‌عنوان ۰.۹۵٪ |
| 59 | Stale Artifact Exclusion | شمارش نتایج فقط فایل‌های همین راند نه فایل‌های کهنه قدیمی. | شمردن A_T* و B_T* |
| 60 | Agent Change Log | برای هر ایجنت یک لاگ تغییرات جداگانه نگهداری شود شامل تاریخ، نوع تغییر، دلیل، MD5 قبل/بعد و نتیجه تست. هیچ تغییری بدون ثبت در این لاگ مجاز نیست. | تغییر بدون ثبت لاگ |
| 61 | SOTA-Driven Multi-Aspect Testing | تست چندجانبه یعنی برای هر باگ/ایجنت: ریپوهای مرتبط GitHub شناسایی و کلون شود (۲۰ تا ۴۰ ریپو)، از کد و مستندات آنها جنبه‌های تست استخراج شود، اجرا شود، نتیجه ثبت شود. عدد ۱۰۰ یا ۲۰۰ = تعداد جنبه‌ها نه تعداد فایل. | گفتن «۱۰۰ تست» بدون مشخص کردن جنبه‌ها از ریپو واقعی |
| 62 | Hermes Delegation Protocol | Hermes Agent وظایف read-only را اجرا می‌کند: نتیجه به اپراتور فرستاده شود برای تأیید، سپس تست بعدی. هیچ write/تغییر فایلی مجاز نیست مگر با اجازه صریح. | بدون تأیید فایل بنویسد |
| 63 | Multi-Round Thinking | برای هر باگ کشف‌شده، ۳ تا ۴ راند فکر مستقل: شناسایی، تأیید/رد، تأثیر سیستمی، راه‌حل نهایی. | نوشتن «باگ است» بدون ۴ راند فکر |
| 64 | Hermes-to-Desktop Report Chain | پس از اتمام تمام تست‌ها یک گزارش JSON نهایی تولید و در مسیر Desktop/HermesReports/ ذخیره می‌شود، اپراتور محتوا را در چت پیست می‌کند تا در Dossier ثبت شود. | گزارش را مستقیم ننوشتن |
| 65 | Complete Sentence Law Recording | هر قانون باید به صورت کامل و منسجم ثبت شود؛ هیچ قانونی خلاصه یا کلمه‌ای نباشد. هر قانون شامل نام، شماره، شرح کامل و مثال نقض باشد. | نوشتن فقط «۶۵: کامل بنویس» بدون توضیح |

## LAW78 — پروتکل تست چندجانبه اجباری

قبل از هر رفع باگ:
1. **۵ دسته تست ≥۱۰۰ جانبه** اجرا شود (Role+Existence, Structural+Deps, Behavioral, Temporal, SOTA Comparison, Systemic Impact)
2. معیارها از GitHub SOTA استخراج شوند نه اختراع
3. نتایج خام در چت نوشته شود — هرگز fabrication
4. مشخصات ایجنت با تاریخ در MEMORY ثبت شود
5. هیچ fix بدون پروتکل مجاز نیست

## قوانین اضافی (66-78)

| # | نام | خلاصه | مثال نقض |
|---|-----|-------|----------|
| 67 | Explain PS1 in Farsi | قبل از هر کد PowerShell، توضیح فارسی داده شود | اجرای PS بدون توضیح |
| 68 | Goal-First | اول هدف تعریف شود بعد اقدام؛ بدون هدف مشخص عمل نکن | شروع کار بدون تعریف هدف |
| 69 | No-Guess Policy | هرگز حدس نزن؛ فقط شواهد خام behavioral | حدس زدن نتیجه تست |
| 70 | 8-Stage Decision | role→existence→structural→behavioral→temporal→SOTA→systemic→decision | تصمیم بدون ۸ مرحله |
| 71 | Anti-Hallucination | AST PASS != correctness; فقط شواهد behavioral واقعی معتبر است | «AST OK پس کار می‌کند» |
| 72 | SOTA Source Real | منبع SOTA باید از GitHub واقعی باشد نه ساخته شده | اختراع ریپو SOTA |
| 73 | Claim Citation | هر ادعا = (قانون توجیه‌کننده + شاهد خام + شماره Step) بدون این سه چیز ادعا پذیرفته نیست | گفتن «باگ است» بدون منبع |
| 74 | Agent Dossier Protocol | برای هر ایجنت: مشخصات، تاریخچه تست‌ها، باگ‌های شناخته‌شده و رفع‌شده، و اقدامات انجام‌شده در MEMORY ثبت شود | کار روی ایجنت بدون ثبت مشخصات |
| 75 | Read-Only Until Approved | هیچ تغییری در کدبیس تا تأیید صریح اپراتور مجاز نیست؛ حالت پیش‌فرض read-only است | تغییر خودکار فایل |
| 76 | Test Results In Chat | نتایج هر تست باید به صورت خام و کامل در متن چت نوشته شود نه فقط خلاصه | نوشتن «همه OK» بدون جزئیات |
| 77 | Multi-Aspect Before Fix | قبل از هر fix، حداقل ۵ دسته تست چندجانبه اجرا و نتیجه ثبت شود | fix بدون تست پیش‌نیاز |
| 78 | LAW78 Agent Spec Logging | مشخصات هر ایجنت (نام، نقش، باگ‌ها، تاریخچه تست‌ها، وضعیت فعلی) با timestamp در MEMORY ذخیره شود و قبل از هر اقدام لود گردد | کار روی ایجنت بدون بارگذاری dossier |
| 79 | Agent Dossier Auto-Update | هر بار که کد ایجنت تغییر کند یا تست جدید اجرا شود، dossier آن ایجنت در Agent_Architecture.md به‌روز شود: امضای توابع (AST)، ورودی/خروجی، وابستگی‌ها، باگ‌های شناخته‌شده و نتیجه آخرین تست. این آپدیت خودکار قبل از پایان Step انجام می‌شود. تغییر بدون آپدیت dossier = نقض LAW0 |

## پروتکل اجرایی LAW78 — چک‌لیست پیش از هر جراحی

1. **L45 Existence-First:** وجود فایل هدف تأیید شود
2. **L0 Diagnostic:** وضعیت فعلی با تست read-only اسکن شود (حداقل ۱۰ جنبه)
3. **L5 Backup:** بکاپ timestamped + MD5 binary گرفته شود
4. **L68 Goal-First:** هدف این جراحی صراحتاً تعریف شود
5. **L70 8-Stage:** هر ۸ مرحله بررسی شود
6. **L51 SOTA Multi-Dimensional:** معیارهای تست از GitHub SOTA استخراج شوند
7. **L73 Claim Citation:** هر ادعا با (قانون + شاهد خام + Step#) مستند شود
8. **L62 Read-Only Until Approved:** تا تأیید اپراتور، هیچ write انجام نشود
9. **L18 Triple-Verification:** پس از fix: AST → functional test → behavioral test
10. **L74 Agent Dossier:** نتیجه در MEMORY با تاریخ ثبت شود

## وضعیت فعلی پروژه (Step 42 — 2026-09-24)

### باگ‌های بحرانی شناخته‌شده
| کد | توصیف | فایل/خط | وضعیت |
|----|-------|---------|--------|
| BUG-DX/EF | timestamp ساختگی | slam_to_bev.py خط ۴۸, video_event_extractor.py خط ۵۱ | تأیید شده |
| BUG-EG | cross_modal_aligner orphaned + ImportError خاموش | launch_session.py خط ۸۰۹ | تأیید شده |
| BUG-EC | محدودیت فریم ۳۴۴ vs ۶۲۱ واقعی | bev_image_renderer.py خط ۱۷۷ | تأیید شده |
| BUG-EA/EB | مسیرهای هاردکد D:\ (سیستم 3090) | لایه داده/پیکربندی | شناسایی شده |
| BUG-ED | HITL انجام نشده — همه human_confirmed=false | cross_modal_matches | تأیید شده |
| BUG-EE | yolo_detections.json هست ولی ultralytics نصب نیست | محیط openvla | شناسایی شده |
| BUG-DA | GPU TdrDelay تنظیم نشده | سیستم 5090 | باز |
| BUG-DC | مدل‌های ممنوع LMS باید unload شوند | localhost:1234 | باز |

### اهداف (Goals)
| کد | توصیف |
|----|-------|
| G49 | تست جامع پس از رفع باگ‌ها |
| G50 | همگام‌سازی BEV |
| G51 | HITL فعال‌سازی |
| G52/G53 | Identity verification + JSON pipeline |
| G54 | VLA integration |
| G55 | App deployment + MiR100 |

### ترتیب رفع باگ (پس از Step 42)
fix DX/EG → EC → EA/EB → install packages → G49 test → HITL G52/G53 → JSON G54 → VLA G55 → app+MiR100 parallel BUG-DA+article PD-01

### اطلاعات سیستم
- GPU: RTX 5090 (WSR95090A, IP: 10.10.220.112) — 32GB VRAM
- CPU: AMD 9950X3D, RAM: 125GB
- Root: C:/Users/Admin/kiarash works/kiarash git codes/MirMap&Motive_HeavyPhase_IntermediateV1
- Env: miniconda3/envs/openvla
- LMS: localhost:1234 — مدل مجاز: qwen3.6-27b
- A18 MD5: 5b881b6e86a4755347b732c0fa3f0f8d — **NEVER TOUCH**
|- Golden session: 621 robot_states, real timestamps, slam_data.pkl healthy
|- پکیج‌های گم‌شده: groundingdino, ultralytics

## LAW79 - حافظه عمیق ایجنت‌ها (Agent Deep Memory)
| # | نام | خلاصه | مثال نقض |
|---|-----|-------|----------|
| 79 | Agent Deep Memory Auto-Update | پس از هر تغییر کد یا اجرای تست، باید Agent_Deep_Memory.md با اسکن کامل AST تمام ایجنت‌ها به‌روز شود؛ شامل: نام، دسته‌بندی (از ۱۰ دسته زیر)، تعداد خطوط، کلاس‌ها/توابع اصلی، docstring، ورودی/خروجی‌ها، وابستگی‌های import بین ایجنت‌ها، و نقش مستقیم در اهداف تز. این فایل مرجع زنده است و هر بار قبل از اقدام عملیاتی مرور می‌شود. | تغییر کد بدون به‌روزرسانی حافظه ایجنت‌ها |

### ۱۰ دسته‌بندی ایجنت‌ها (طبق LAW79)
1. **INFRASTRUCTURE** (3): DataDescriptions, MoCapData, NatNetClient — زیرساخت داده و ارتباط شبکه
2. **DATA_ACQUISITION** (2): motive_connector, mir_command_logger — ضبط داده زنده
3. **FUSION_ALIGNMENT** (4): spatial_temporal_fusion, cross_modal_aligner, semantic_slam_fusion, slam_auto_namer — هم‌ترازی چندوجهی
4. **ANALYSIS_INSIGHT** (7): robot_data_analyzer, session_worthiness_analyzer, video_quality_agent, video_event_extractor, video_learning_agent, vla_scenario_validator, quality_gate — تحلیل و بینش
5. **VLA_DATASET** (3): qwen_dataset_formatter, vla_dataset_builder, video_narrator — ساخت دیتاست VLA
6. **KNOWLEDGE_MEMORY** (4): knowledge_engine, session_manager, entity_registry, apply_merge — حافظه یادگیری عمیق
7. **AUDIT_ANALYZER** (4): A15_referee_ai_loop, A16_agent_deep_analyzer, A18_deep_agent_verifier, project_snapshot — داور هوش مصنوعی
8. **LABELING_DETECTION** (5): auto_labeler, cvat_converter, label_registry, label_registry_auto, scene_object_detector — تشخیص و برچسب‌گذاری
9. **BEV_RENDERING** (3): slam_to_bev, bev_image_renderer, slam_map_annotator — رندر نمای بالا
10. **ORCHESTRATION** (3): launch_session, run_session_analysis, offline_processor — هماهنگی پایپ‌لاین

### نقشه وابستگی فراخوانی (Call Graph)
- `launch_session.py` → video_narrator, motive_connector, co_pilot_agent, spatial_temporal_fusion, cross_modal_aligner, knowledge_engine, label_registry_auto, slam_map_annotator, session_manager, slam_to_bev, mir_command_logger
- `run_session_analysis.py` → quality_gate, knowledge_engine, spatial_temporal_fusion
- `motive_connector.py` → NatNetClient
- `co_pilot_agent.py` → robot_data_analyzer, session_manager, entity_registry, knowledge_engine
- `vla_dataset_builder.py` → robot_data_analyzer
- `project_snapshot.py` → scene_object_detector, video_learning_agent, slam_to_bev
- `apply_merge.py` → knowledge_engine
- `quality_gate.py` → knowledge_engine
- `slam_auto_namer.py` → entity_registry
- `vla_supervisor_agent.py` → vla_scenario_validator
|- `label_registry_auto.py` → label_registry
|- `NatNetClient.py` → DataDescriptions, MoCapData

---

## WSL Orchestrator Laws (LAW80-92)

### LAW80 — Evidence-Based Verification Criteria
هر اقدام باید معیارهای موفقیت ماشین‌خوان داشته باشد:
```json
{
  "exit_code": 0,
  "file_exists": true,
  "content_check": {"contains": "string", "regex": "pattern"},
  "file_size_min_bytes": 1024,
  "line_count_min": 10
}
```
Verifier هر نتیجه را با این معیارها بررسی می‌کند. اگر PASS نشد، شواهد خام (stdout, stderr, exit_code) به Hermes برمی‌گردد.

### LAW81 — Bridge Protocol (ارتباط فایل‌محور WSL ↔ Hermes)
- WSL Orchestrator هرگز مستقیم به LM Studio وصل نمی‌شود.
- تمام ارتباط از طریق پوشه `AUTO_GOAL_ORCHESTRATOR/bridge/` انجام می‌شود:
  - `request.json`: دستور از Hermes → WSL (command, goal_id, success_criteria)
  - `response.json`: نتیجه از WSL → Hermes (exit_code, stdout, stderr, evidence, verdict)
- Hermes هر بار response.json را می‌خواند، تحلیل می‌کند و تصمیم بعدی را در request.json می‌نویسد.

### LAW82 — Adaptive Loop (حلقه تطبیقی)
- حداکثر تلاش برای هر اقدام: 5 بار
- اگر پس از 3 شکست متوالی با همان استراتژی، Orchestrator باید استراتژی را تغییر دهد (مثلاً پارامترهای مختلف، مسیر جایگزین).
- شرط توقف: VERIFIED موفقیت یا رسیدن به حد 5 تلاش.
- در هر حالت، گزارش کامل با timestamp ثبت می‌شود.

### LAW83 — Crash Resume (ادامه بعد از کرش)
- Orchestrator وضعیت فعلی را هر 30 ثانیه در `AUTO_GOAL_ORCHESTRATOR/state/progress.json` ذخیره می‌کند:
```json
{
  "current_goal": "G49",
  "iteration": 12,
  "last_action": "train_vla_epoch_5",
  "timestamp": "YYYY-MM-DD HH:MM:SS"
}
```
- بعد از ریست، Orchestrator این فایل را می‌خواند و از آخرین نقطه ادامه می‌دهد.

### LAW84 — Goals Queue (صف اهداف پویا)
- هدف جدید حین اجرای Loop قابل اضافه شدن است بدون توقف.
- هدف به انتهای صف اضافه شده و پس از تکمیل هدف فعلی، پردازش می‌شود.
- اولویت: G49 > G50 > ... > G55 (طبق Thesis_Goals.md).

### LAW85 — Post-Success Advisory (پیشنهاد قدم بعدی)
- بعد از هر موفقیت VERIFIED، Orchestrator یک پیشنهاد برای اقدام بعدی تولید می‌کند.
- Hermes این پیشنهاد را تأیید یا اصلاح می‌کند.
- ثبت در `AUTO_GOAL_ORCHESTRATOR/state/advisory_log.json`.

### LAW86 — Memory Map (نقشه حافظه‌ها)
لیست دقیق تمام فایل‌های حافظه پروژه:

| # | فایل | آدرس کامل | نقش |
|---|------|----------|-----|
| 1 | MEMORY.md | `C:\Users\Admin\AppData\Local\hermes\memories\MEMORY.md` | حافظه شخصی Hermes — قوانین، باگ‌ها، وضعیت پروژه |
| 2 | USER.md | `C:\Users\Admin\AppData\Local\hermes\memories\USER.md` | پروفایل کاربر — نام، تز، سیستم، ترجیحات |
| 3 | Laws_Reference.md | `...\MirMap&Motive_HeavyPhase_IntermediateV1\Laws_Reference.md` | مرجع تمام قوانین + اهداف تز |
| 4 | Actions_Memory.md | `...\MirMap&Motive_HeavyPhase_IntermediateV1\Actions_Memory.md` | ثبت اقدامات، تست‌ها، نتایج هر Step |
| 5 | Agent_Deep_Memory.md | `...\agents\Agent_Deep_Memory.md` | رجیستری کامل ۴۱ ایجنت (LAW79) |
| 6 | deep_learning_memory.pkl | `...\persistent_knowledge\deep_learning_memory.pkl` | حافظه تجمعی knowledge_engine |
| 7 | environment_knowledge.pkl | `...\persistent_knowledge\environment_knowledge.pkl` | دانش محیط/سناریوهای فیزیکی |
| 8 | Agent_Architecture.md | `...\MirMap&Motive_HeavyPhase_IntermediateV1\Agent_Architecture.md` | مستندات معماری سیستم |
| 9 | Thesis_Goals.md | `...\MirMap&Motive_HeavyPhase_IntermediateV1\Thesis_Goals.md` | اهداف نهایی پایان‌نامه G49-G55 |

### LAW87 — Hardware Safety (ایمنی سخت‌افزار)
- هرگز بیش از 90% VRAM RTX 5090 استفاده نشود.
- دمای GPU بالای 85°C → کاهش خودکار batch size.
- A18.py هرگز تغییر نمی‌کند (MD5: `5b881b6e86a4755347b732c0fa3f0f8d`).

### LAW88 — Logging Protocol (پروتکل ثبت وقایع)
- تمام اقدامات با timestamp دقیق `YYYY-MM-DD HH:MM:SS` ثبت می‌شوند.
- فایل لاگ: `AUTO_GOAL_ORCHESTRATOR/logs/action_log.jsonl`
- هر خط شامل: timestamp, goal_id, action, result, evidence_summary

### LAW89 — Anti-Hallucination Enforcement (اجرای صفر توهم)
- هیچ نتیجه‌ای بدون شواهد خام قابل قبول نیست.
- AST parse ≠ correctness. فقط behavioral evidence (خروجی واقعی اجرا) ملاک است.
- اگر داده‌ای در دسترس نیست، `NEEDS_CONFIRMATION_FROM_KIARASH` ثبت شود.

---

## LAW92 — Auto Self-Throttling (ایمنی سخت‌افزار بعد از کرش)

### مسئله
اگر سیستم به دلیل بار سنگین GPU/CPU خودش ریست شد یا کرش کرد، دلیلش این است که تنظیمات فعلی برای این حجم کار سنگین بوده. اگر بعد از روشن شدن دقیقاً همان تنظیمات دوباره اعمال شود و همان کار سنگین دوباره اجرا شود، دوباره ریست می‌کند. این چرخه می‌تواند به سخت‌افزار آسیب برساند.

### قانون
بعد از هر ریست غیرمنتظره، تنظیمات LM Studio به صورت خودکار کاهش می‌یابد.

#### مقادیر پایه (Baseline — Level 0)
| پارامتر | مقدار |
|---------|-------|
| GPU Offload Layers | 62 |
| CPU Thread Pool | 16 |
| Context Length | 65536 |

#### Throttle Levels
| Level | GPU Offload | CPU Threads | Context Length | توضیح |
|-------|-----------|-------------|----------------|-------|
| 0 (Baseline) | 62 | 16 | 65536 | حالت عادی |
| 1 | 58 (-4) | 14 (-2) | 65536 | بعد از ریست اول |
| 2 | 54 (-8) | 12 (-4) | 49152 | بعد از ریست دوم |
| 3 (Max Safety) | 48 (-14) | 10 (-6) | 32768 | حداکثر ایمنی |

اگر بعد از Level 3 باز هم ریست شد: **توقف کامل**. گزارش: "سخت‌افزار در وضعیت پایدار نیست. نیاز به بررسی دستی اپراتور." هیچ کار سنگینی اجرا نمی‌شود.

#### بازگشت تدریجی به Baseline
اگر سیستم بعد از Throttle به مدت 24 ساعت پایدار کار کرد، به تدریج (هر 6 ساعت یک پله) به Baseline برمی‌گردد.

#### فایل وضعیت Throttle
مسیر: `AUTO_GOAL_ORCHESTRATOR/state/throttle_state.json`
```json
{
  "current_level": 0,
  "last_crash_timestamp": null,
  "crash_count_total": 0,
  "crash_count_current_session": 0,
  "last_stable_hours": 0,
  "current_settings": {
    "gpu_offload": 62,
    "cpu_thread_pool": 16,
    "context_length": 65536
  },
  "baseline_settings": {
    "gpu_offload": 62,
    "cpu_thread_pool": 16,
    "context_length": 65536
  }
}
```

#### تشخیص ریست غیرمنتظره (Heartbeat)
- Orchestrator هر 30 ثانیه heartbeat در `AUTO_GOAL_ORCHESTRATOR/state/heartbeat.json` می‌نویسد.
- وقتی سیستم دوباره روشن شد، اسکریپت Boot این فایل را چک می‌کند:
  - اگر heartbeat کمتر از 2 دقیقه قبل بود → ریست غیرمنتظره تشخیص داده می‌شود.
  - Throttle Level یک درجه افزایش می‌یابد.
  - تنظیمات جدید در throttle_state.json ذخیره و اعمال می‌شود.
  - در `AUTO_GOAL_ORCHESTRATOR/logs/action_log.jsonl` ثبت می‌شود.

