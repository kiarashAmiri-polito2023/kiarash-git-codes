import os, sys
project_root = "D:\\kiarash\\kiarash git codes\\MirMap&Motive_HeavyPhase_IntermediateV1"
sys.path.insert(0, os.path.join(project_root, "agents"))
from entity_registry import EntityRegistry

reg = EntityRegistry(root_path=project_root)

person_id = None
hat_id = None

# ۱. پیدا کردن ID های دقیق
for eid, data in list(reg.entities.items()):
    name = data.get("canonical_name", "")
    if name == "person_kiarash":
        person_id = eid
    elif name == "kia hat 002":
        hat_id = eid

# ۲. ادغام مارکرها و تایید نهایی
if person_id:
    current_markers = set(reg.entities[person_id].get("motive_markers", []))
    current_markers.update(["kia hat 002", "kiarash_leftwrist", "kiarash_RightWrist"])
    
    reg.entities[person_id]["motive_markers"] = sorted(list(current_markers))
    reg.entities[person_id]["status"] = "CONFIRMED"  # تایید رسمی انسان
    reg.entities[person_id]["object_type"] = "human"
    reg.entities[person_id]["is_dynamic"] = True
    
    # حذف انتیتی تکراری کلاه
    if hat_id and hat_id in reg.entities and hat_id != person_id:
        del reg.entities[hat_id]
        print(f"Removed duplicate entity: {hat_id} (kia hat 002)")

    reg.save()
    print("\n🎉 SURGERY SUCCESSFUL! Master Entity Registry Updated & CONFIRMED.")
else:
    # اگر به هر دلیلی نبود، از صفر تمیز می‌سازیم
    print("Creating person_kiarash from scratch...")
    reg.create_entity(
        canonical_name="person_kiarash",
        object_type="human",
        is_dynamic=True,
        motive_markers=["kia hat 002", "kiarash_leftwrist", "kiarash_RightWrist"]
    )
    # تایید کردن
    for eid, data in reg.entities.items():
        if data.get("canonical_name") == "person_kiarash":
            data["status"] = "CONFIRMED"
    reg.save()
    print("\n🎉 CREATED & CONFIRMED Master Entity!")

print("\n==================================================")
print(" FINAL ENTITY REGISTRY STATE (PAPER-READY)")
print("==================================================")
for k, v in reg.entities.items():
    print(f"  ID: {k}")
    print(f"  Name: {v.get('canonical_name')}")
    print(f"  Status: {v.get('status')} ✅")
    print(f"  Markers: {v.get('motive_markers')}")
    print("--------------------------------------------------")