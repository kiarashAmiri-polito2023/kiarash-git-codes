import os,sys,json,time,urllib.request,urllib.error
from datetime import datetime

ROOT = r"D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1"
print("="*60)
print("R41.2 DEEP SOTA SCAN - 50 repos, deep structure")
print("="*60)

token = ""
tkp = os.path.join(ROOT, ".secrets", "github.key")
if os.path.exists(tkp):
    with open(tkp, "r", encoding="utf-8-sig") as f:
        token = f.read().strip()

def gh(url):
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("User-Agent", "MiR100-Audit")
    if token:
        req.add_header("Authorization", "token " + token)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))
    except:
        return None

# 50 real repos across 8 categories
REPOS = [
    # VLA / Robot Learning
    "octo-models/octo", "OpenVLA/openvla", "lerobot/lerobot",
    "google-deepmind/rt-1", "google-deepmind/rt-2",
    "Physical-Intelligence/openpi", "rail-berkeley/bridge_data_v2",
    "facebookresearch/rlr3m",
    # Navigation / SLAM
    "ros-planning/navigation2", "cartographer-project/cartographer",
    "SteveMacenski/slam_toolbox", "MIT-SPARK/Kimera-VIO",
    "nvidia-isaac-ros/isaac_ros_visual_slam",
    "TixiaoShan/LIO-SAM", "hku-mars/FAST-LIO",
    "HKUST-Aerial-Robotics/VINS-Mono",
    # Simulation
    "facebookresearch/habitat-lab", "ARISE-Initiative/robosuite",
    "google-deepmind/mujoco", "NVIDIA-Omniverse/IsaacGymEnvs",
    "openai/gymnasium", "Farama-Foundation/Minigrid",
    # Vision / Perception
    "facebookresearch/detr", "ultralytics/ultralytics",
    "open-mmlab/mmdetection", "open-mmlab/mmsegmentation",
    "facebookresearch/segment-anything",
    "WongKinYiu/yolov7", "Megvii-BaseDetection/YOLOX",
    # ROS / Integration
    "ros2/ros2", "ros/ros_comm",
    "nvidia-isaac-ros/isaac_ros_common",
    "roboticsgroup/roboticsgroup_upatras_gazebo_plugins",
    # Safety / Verification
    "safe-ai/safe-rl", "DAGABO98/safe-control-gym",
    "utiasDSL/safe-control-gym",
    # LLM / Inference
    "huggingface/transformers", "vllm-project/vllm",
    "lm-sys/FastChat", "oobabooga/text-generation-webui",
    "ggerganov/llama.cpp", "ggml-org/whisper.cpp",
    # Dataset / Training
    "huggingface/datasets", "pytorch/pytorch",
    "lightning-AI/pytorch-lightning",
    "huggingface/peft", "huggingface/trl",
    # Mobile Robot
    "MobileRoboticsSkoltech/mtm_localization",
    "cra-ros-pkg/robot_localization",
]

all_dims = set()
results = []
ok_count = 0

for i, repo in enumerate(REPOS):
    print("[{}/{}] {} ...".format(i+1, len(REPOS), repo), end=" ")
    time.sleep(1.2)
    
    info = gh("https://api.github.com/repos/" + repo)
    if not info or "message" in info:
        print("SKIP")
        continue
    
    ok_count += 1
    stars = info.get("stargazers_count", 0)
    lang = info.get("language", "?")
    desc = (info.get("description") or "")[:60]
    
    # Deep scan: root + key subdirs
    tree = gh("https://api.github.com/repos/" + repo + "/git/trees/HEAD?recursive=1")
    all_paths = []
    if tree and "tree" in tree:
        all_paths = [t["path"] for t in tree["tree"][:500]]
    
    paths_lower = str(all_paths).lower()
    
    # 40 deep dimensions
    d = {}
    d["d01_stars_gt_1k"] = stars > 1000
    d["d02_stars_gt_10k"] = stars > 10000
    d["d03_python"] = lang == "Python"
    d["d04_cpp"] = lang in ["C++", "C"]
    d["d05_dockerfile"] = any("dockerfile" in p.lower() for p in all_paths)
    d["d06_ci_github"] = any(".github/workflows" in p for p in all_paths)
    d["d07_tests_dir"] = any(p.startswith("test") for p in all_paths[:50])
    d["d08_docs_dir"] = any(p.startswith("doc") for p in all_paths[:50])
    d["d09_license"] = any("license" in p.lower() for p in all_paths[:20])
    d["d10_readme"] = any("readme" in p.lower() for p in all_paths[:20])
    d["d11_requirements"] = any("requirements" in p.lower() for p in all_paths[:30])
    d["d12_setup_py"] = any("setup.py" in p for p in all_paths[:30])
    d["d13_pyproject"] = any("pyproject" in p for p in all_paths[:30])
    d["d14_models_dir"] = any("model" in p.lower() for p in all_paths[:50])
    d["d15_data_dir"] = any("data" in p.lower() for p in all_paths[:50])
    d["d16_config_yaml"] = any(p.endswith(".yaml") for p in all_paths[:100])
    d["d17_config_json"] = any(p.endswith(".json") for p in all_paths[:100])
    d["d18_ros_launch"] = any(".launch" in p for p in all_paths)
    d["d19_ros_urdf"] = any(".urdf" in p for p in all_paths)
    d["d20_ros_msg"] = any(".msg" in p for p in all_paths)
    d["d21_cmake"] = any("CMakeLists" in p for p in all_paths[:50])
    d["d22_ros_package"] = any("package.xml" in p for p in all_paths[:50])
    d["d23_training_script"] = any("train" in p.lower() for p in all_paths[:100])
    d["d24_eval_script"] = any("eval" in p.lower() for p in all_paths[:100])
    d["d25_inference"] = any("infer" in p.lower() for p in all_paths[:100])
    d["d26_pretrained"] = any("pretrained" in p.lower() or "checkpoint" in p.lower() for p in all_paths[:100])
    d["d27_onnx_export"] = any(".onnx" in p.lower() for p in all_paths)
    d["d28_tensorrt"] = any("tensorrt" in p.lower() or "trt" in p.lower() for p in all_paths[:100])
    d["d29_safety_module"] = any("safe" in p.lower() for p in all_paths[:100])
    d["d30_collision"] = any("collision" in p.lower() for p in all_paths)
    d["d31_planning"] = any("planner" in p.lower() or "planning" in p.lower() for p in all_paths[:100])
    d["d32_localization"] = any("locali" in p.lower() for p in all_paths[:100])
    d["d33_mapping"] = any("map" in p.lower() for p in all_paths[:100])
    d["d34_perception"] = any("percept" in p.lower() for p in all_paths[:100])
    d["d35_detection"] = any("detect" in p.lower() for p in all_paths[:100])
    d["d36_segmentation"] = any("segment" in p.lower() for p in all_paths[:100])
    d["d37_lidar"] = any("lidar" in p.lower() for p in all_paths)
    d["d38_camera"] = any("camera" in p.lower() or "image" in p.lower() for p in all_paths[:100])
    d["d39_imu"] = any("imu" in p.lower() for p in all_paths)
    d["d40_odometry"] = any("odom" in p.lower() for p in all_paths)
    
    active = [k for k, v in d.items() if v]
    all_dims.update(active)
    
    results.append({
        "repo": repo, "stars": stars, "lang": lang,
        "desc": desc, "dims": active, "count": len(active),
        "paths_scanned": len(all_paths)
    })
    print("OK stars={} dims={}/40".format(stars, len(active)))

print("\n" + "="*60)
print("DEEP SCAN SUMMARY")
print("="*60)
print("Repos OK: {}/{}".format(ok_count, len(REPOS)))
print("Unique dimensions: {}/40".format(len(all_dims)))
print("Dimensions: " + str(sorted(all_dims)))

rp = os.path.join(ROOT, "R41_2_deep_sota_scan.json")
with open(rp, "w", encoding="utf-8") as f:
    json.dump({"repos": results, "dims": sorted(all_dims), "count": ok_count, "ts": datetime.now().isoformat()}, f, indent=2)
print("SAVED: " + rp)
