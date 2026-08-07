import os, sys, inspect
project_root = "D:\\kiarash\\kiarash git codes\\MirMap&Motive_HeavyPhase_IntermediateV1"
sys.path.insert(0, os.path.join(project_root, "agents"))
from entity_registry import EntityRegistry

# ۱. راه‌اندازی با مسیر روت پروژه
reg = EntityRegistry(root_path=project_root)

# ۲. بررسی هوشمند امضای متد در کامپیوتر لب
sig = inspect.signature(reg.suggest_grouping)
params = list(sig.parameters.keys())
print(f"Detected Method Signature: suggest_grouping{sig}")

# ۳. مپ کردن هوشمند آرگومان‌ها بر اساس ترتیب پارامترها
# پارامتر اول: نام انتیتی (person_kiarash)
# پارامتر دوم: کلاس انتیتی (human)
# پارامتر سوم: لیست مارکرها
args = {}
args[params[0]] = 'person_kiarash'
args[params[1]] = 'human'
args[params[2]] = ['kia hat 002', 'kiarash_leftwrist', 'kiarash_RightWrist']

print(f"Mapping arguments dynamically: {args}")

# ۴. اجرای متد با آرگومان‌های مپ شده
reg.suggest_grouping(**args)
reg.save()

print("\n🎉 SUCCESS: Dynamic Entity Merge Completed!")
print("--------------------------------------------------")
for k, v in reg.entities.items():
    print(f"  {k}: {v.get('canonical_name', v.get('name'))} -> {v.get('motive_markers')}")